"""Shared visualization service for generating clusters and UMAP visualizations."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import logging
import traceback
import umap
import numpy as np
from sqlalchemy import select, text, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem, NewsClusters, NewsUMAP
from app.models.preference_vector import PreferenceVector
from app.services.faiss_service import get_faiss_service
from app.config import settings

logger = logging.getLogger(__name__)

async def generate_clusters(db: AsyncSession, hours: int, min_similarity: float) -> Dict[int, List[dict]]:
    """Generate news clusters using FAISS vector similarity."""
    try:
        # Get FAISS service
        faiss_service = get_faiss_service()
        
        # Generate clusters using FAISS
        clusters = await faiss_service.get_clusters(db, hours, min_similarity)
        
        if not clusters:
            logger.warning("No clusters found")
            return {}
            
        # Enrich cluster data with additional news item details from database
        enriched_clusters: Dict[int, List[dict]] = {}
        
        for cluster_id, items in clusters.items():
            try:
                # Get all news IDs in this cluster
                news_ids = [item['id'] for item in items]
                
                # Get full news items from database
                stmt = select(NewsItem).filter(NewsItem.id.in_(news_ids))
                result = await db.execute(stmt)
                news_items = {item.id: item for item in result.scalars().all()}
                
                if not news_items:
                    logger.warning(f"No news items found for cluster {cluster_id}")
                    continue
                
                # Create enriched items
                enriched_items = []
                for item in items:
                    news_item = news_items.get(item['id'])
                    if news_item:
                        enriched_items.append({
                            "id": news_item.id,
                            "title": news_item.title,
                            "summary": news_item.summary,
                            "url": news_item.url,
                            "source_url": news_item.source_url,
                            "first_seen_at": news_item.first_seen_at.isoformat() if news_item.first_seen_at else None,
                            "last_seen_at": news_item.last_seen_at.isoformat() if news_item.last_seen_at else None,
                            "hit_count": news_item.hit_count,
                            "created_at": news_item.created_at.isoformat() if news_item.created_at else None,
                            "updated_at": news_item.updated_at.isoformat() if news_item.updated_at else None,
                            "similarity": item['similarity'],
                            "cluster_id": cluster_id
                        })
                
                if enriched_items:
                    enriched_clusters[cluster_id] = enriched_items
                    
            except Exception as e:
                logger.error(f"Error enriching cluster {cluster_id}: {str(e)}\n{traceback.format_exc()}")
                continue
        
        logger.info(f"Generated {len(enriched_clusters)} enriched clusters")
        return enriched_clusters
        
    except Exception as e:
        logger.error(f"Clustering error: {str(e)}\n{traceback.format_exc()}")
        raise

async def generate_umap_visualization(db: AsyncSession, hours: int, min_similarity: float) -> List[dict]:
    """Generate UMAP visualization data."""
    try:
        # First generate clusters to get cluster assignments
        clusters = await generate_clusters(db, hours, min_similarity)
        
        # Create a mapping of news item ID to cluster ID
        item_to_cluster = {}
        for cluster_id, items in clusters.items():
            for item in items:
                item_to_cluster[item['id']] = cluster_id

        # Get news items from the last n hours - use timezone-aware UTC time
        now = datetime.now(timezone.utc)
        time_filter = now - timedelta(hours=hours)
        
        # Get all news items with embeddings from the specified time period
        stmt = select(NewsItem).filter(
            NewsItem.last_seen_at >= time_filter,
            NewsItem.embedding.is_not(None)
        ).order_by(NewsItem.last_seen_at.desc())
        
        result = await db.execute(stmt)
        news_items = result.scalars().all()
        
        if not news_items:
            logger.warning("No news items found for UMAP visualization")
            return []

        # Get preference vectors from PostgreSQL
        stmt = select(PreferenceVector).filter(PreferenceVector.embedding.is_not(None))
        result = await db.execute(stmt)
        preference_vectors = result.scalars().all()
        logger.info(f"Found {len(preference_vectors)} preference vectors in PostgreSQL")
        
        # Process all embeddings together
        all_embeddings = []
        all_items = []
        is_pref_vector = []  # Track which items are preference vectors

        # Add news item embeddings
        for item in news_items:
            try:
                # Convert pgvector to numpy array
                vector = np.array(item.embedding.tolist(), dtype=np.float32)
                if vector.shape != (settings.VECTOR_DIMENSIONS,):
                    logger.error(f"Invalid vector shape for news item {item.id}: {vector.shape}")
                    continue
                all_embeddings.append(vector)
                all_items.append(item)
                is_pref_vector.append(False)
            except Exception as e:
                logger.error(f"Error processing embedding for news item {item.id}: {str(e)}")
                continue

        # Add preference vector embeddings
        for vector in preference_vectors:
            if vector.embedding is not None:
                try:
                    # Convert pgvector to numpy array
                    pref_vector = np.array(vector.embedding.tolist(), dtype=np.float32)
                    if pref_vector.shape != (settings.VECTOR_DIMENSIONS,):
                        logger.error(f"Invalid vector shape for preference vector {vector.id}: {pref_vector.shape}")
                        continue
                    all_embeddings.append(pref_vector)
                    all_items.append(vector)
                    is_pref_vector.append(True)
                    logger.info(f"Added preference vector {vector.id} ({vector.title}) to UMAP input")
                except Exception as e:
                    logger.error(f"Error processing embedding for preference vector {vector.id}: {str(e)}")
                    continue

        if not all_embeddings:
            logger.warning("No valid embeddings found for UMAP visualization")
            return []

        try:
            # Create UMAP reducer
            reducer = umap.UMAP(
                n_components=2,
                random_state=42,
                metric='cosine',
                min_dist=0.1,
                n_neighbors=15
            )

            # Convert to numpy array and get UMAP coordinates for all points together
            embeddings_array = np.array(all_embeddings)
            umap_result = reducer.fit_transform(embeddings_array)
            
            # Create visualization data
            visualization_data = []
            
            # Process all points
            for i, (item, is_pref) in enumerate(zip(all_items, is_pref_vector)):
                try:
                    if is_pref:
                        # Add preference vector
                        visualization_data.append({
                            "id": f"pref_{item.id}",
                            "title": item.title,
                            "description": item.description,
                            "x": float(umap_result[i][0]),
                            "y": float(umap_result[i][1]),
                            "type": "preference_vector",
                            "opacity": 1.0
                        })
                        logger.info(f"Added preference vector {item.id} to visualization data at ({float(umap_result[i][0])}, {float(umap_result[i][1])})")
                    else:
                        # Add news item
                        last_seen = item.last_seen_at
                        if not last_seen.tzinfo:
                            last_seen = last_seen.replace(tzinfo=timezone.utc)
                        
                        if last_seen >= now - timedelta(hours=1):
                            opacity = 0.8
                        elif last_seen <= now - timedelta(days=1):
                            opacity = 0.2
                        else:
                            hours_old = (now - last_seen).total_seconds() / 3600
                            opacity = 0.8 - (0.6 * (hours_old - 1) / 23)
                        
                        visualization_data.append({
                            "id": item.id,
                            "title": item.title,
                            "url": item.url,
                            "source_url": item.source_url,
                            "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
                            "x": float(umap_result[i][0]),
                            "y": float(umap_result[i][1]),
                            "cluster_id": item_to_cluster.get(item.id),
                            "type": "news_item",
                            "opacity": opacity
                        })
                except Exception as e:
                    logger.error(f"Error creating visualization data for item {i}: {str(e)}")
                    continue
            
            logger.info(f"Generated UMAP visualization with {len(visualization_data)} points")
            return visualization_data
            
        except Exception as e:
            logger.error(f"UMAP reduction error: {str(e)}\n{traceback.format_exc()}")
            raise
        
    except Exception as e:
        logger.error(f"UMAP visualization error: {str(e)}\n{traceback.format_exc()}")
        raise

async def update_visualizations(db: AsyncSession):
    """Update pre-generated visualizations using settings from config."""
    try:
        # Use settings from config
        hours = settings.VISUALIZATION_TIME_RANGE
        min_similarity = settings.VISUALIZATION_SIMILARITY
        
        try:
            # Generate UMAP visualization
            umap_data = await generate_umap_visualization(db, hours, min_similarity)
            
            # Check if UMAP visualization exists
            stmt = select(NewsUMAP).filter(
                NewsUMAP.hours == hours,
                NewsUMAP.min_similarity == min_similarity
            )
            result = await db.execute(stmt)
            existing_umap = result.scalar_one_or_none()
            
            if existing_umap:
                # Update existing visualization
                stmt = update(NewsUMAP).where(
                    NewsUMAP.hours == hours,
                    NewsUMAP.min_similarity == min_similarity
                ).values(
                    visualization=umap_data,
                    created_at=func.now()
                )
                await db.execute(stmt)
            else:
                # Create new visualization
                umap_viz = NewsUMAP(
                    hours=hours,
                    min_similarity=min_similarity,
                    visualization=umap_data
                )
                db.add(umap_viz)
            
            # Generate and store clusters
            clusters_data = await generate_clusters(db, hours, min_similarity)
            
            # Check if clusters exist
            stmt = select(NewsClusters).filter(
                NewsClusters.hours == hours,
                NewsClusters.min_similarity == min_similarity
            )
            result = await db.execute(stmt)
            existing_clusters = result.scalar_one_or_none()
            
            if existing_clusters:
                # Update existing clusters
                stmt = update(NewsClusters).where(
                    NewsClusters.hours == hours,
                    NewsClusters.min_similarity == min_similarity
                ).values(
                    clusters=clusters_data,
                    created_at=func.now()
                )
                await db.execute(stmt)
            else:
                # Create new clusters
                clusters = NewsClusters(
                    hours=hours,
                    min_similarity=min_similarity,
                    clusters=clusters_data
                )
                db.add(clusters)
                
        except Exception as e:
            logger.error(f"Error updating visualizations for {hours}h and {min_similarity} similarity: {str(e)}\n{traceback.format_exc()}")
            raise
        
        await db.commit()
        logger.info("Successfully updated all visualizations")
        
    except Exception as e:
        logger.error(f"Error updating visualizations: {str(e)}\n{traceback.format_exc()}")
        await db.rollback()
        raise
