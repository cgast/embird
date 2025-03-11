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
    """Generate UMAP visualization data for news items."""
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

        # Extract embeddings and create UMAP input
        embeddings = []
        valid_items = []
        for item in news_items:
            try:
                vector = np.array(item.embedding, dtype=np.float32)
                if vector.shape != (settings.VECTOR_DIMENSIONS,):
                    logger.error(f"Invalid vector shape for news item {item.id}: {vector.shape}")
                    continue
                embeddings.append(vector)
                valid_items.append(item)
            except Exception as e:
                logger.error(f"Error processing embedding for news item {item.id}: {str(e)}")
                continue
                
        if not embeddings:
            logger.warning("No valid embeddings found for UMAP visualization")
            return []
        
        # Perform UMAP dimensionality reduction
        # Use n_jobs=-1 for parallel processing, remove random_state for better performance
        try:
            reducer = umap.UMAP(
                n_components=2,
                n_jobs=-1,  # Use all available CPU cores
                min_dist=0.1,  # Slightly increase minimum distance for better spread
                n_neighbors=15  # Default value, but explicitly set for clarity
            )
            umap_result = reducer.fit_transform(embeddings)
        except Exception as e:
            logger.error(f"UMAP reduction error: {str(e)}\n{traceback.format_exc()}")
            raise
        
        # Calculate time-based opacity using timezone-aware UTC times
        one_hour_ago = now - timedelta(hours=1)
        yesterday = now - timedelta(days=1)
        
        # Combine UMAP coordinates with news items
        visualization_data = []
        for i, news_item in enumerate(valid_items):
            try:
                # Calculate opacity based on age
                last_seen = news_item.last_seen_at
                if not last_seen.tzinfo:
                    # If the timestamp is naive, assume it's UTC
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                
                if last_seen >= one_hour_ago:
                    opacity = 0.8
                elif last_seen <= yesterday:
                    opacity = 0.2
                else:
                    # Linear interpolation between 0.8 and 0.2 for items between 1 hour and 1 day old
                    hours_old = (now - last_seen).total_seconds() / 3600
                    opacity = 0.8 - (0.6 * (hours_old - 1) / 23)  # 23 = 24 - 1
                
                visualization_data.append({
                    "id": news_item.id,
                    "title": news_item.title,
                    "url": news_item.url,
                    "source_url": news_item.source_url,
                    "last_seen_at": news_item.last_seen_at.isoformat() if news_item.last_seen_at else None,
                    "x": float(umap_result[i][0]),
                    "y": float(umap_result[i][1]),
                    "cluster_id": item_to_cluster.get(news_item.id),
                    "opacity": opacity
                })
            except Exception as e:
                logger.error(f"Error creating visualization data for news item {news_item.id}: {str(e)}")
                continue
        
        logger.info(f"Generated UMAP visualization with {len(visualization_data)} points")
        return visualization_data
        
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
