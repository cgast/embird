"""Shared visualization service for generating clusters and UMAP visualizations."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import umap
from sqlalchemy import select, text, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.news import NewsItem, NewsClusters, NewsUMAP  # Updated import
from app.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)

async def generate_clusters(
    db: AsyncSession,
    hours: int = 48,
    min_similarity: float = 0.6  # Restored to 0.6
) -> Dict[int, List[dict]]:
    """Generate news clusters using Redis vector similarity."""
    try:
        # Get Redis client
        redis_client = await get_redis_client()
        
        # Generate clusters using Redis
        clusters = await redis_client.get_clusters(hours, min_similarity)
        
        if not clusters:
            logger.warning("No clusters found in Redis")
            return {}
            
        # Enrich cluster data with additional news item details from database
        enriched_clusters: Dict[int, List[dict]] = {}
        
        for cluster_id, items in clusters.items():
            # Get all news IDs in this cluster
            news_ids = [item['id'] for item in items]
            
            # Get full news items from database
            stmt = select(NewsItem).filter(NewsItem.id.in_(news_ids))
            result = await db.execute(stmt)
            news_items = {item.id: item for item in result.scalars().all()}
            
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
        
        return enriched_clusters
        
    except Exception as e:
        logger.error(f"Clustering error: {str(e)}")
        raise

async def generate_umap_visualization(
    db: AsyncSession,
    hours: int = 48,
    min_similarity: float = 0.6  # Restored to 0.6
) -> List[dict]:
    """Generate UMAP visualization data for news items."""
    try:
        # First generate clusters to get cluster assignments
        clusters = await generate_clusters(db, hours, min_similarity)
        
        # Create a mapping of news item ID to cluster ID
        item_to_cluster = {}
        for cluster_id, items in clusters.items():
            for item in items:
                item_to_cluster[item['id']] = cluster_id

        # Get news items from the last n hours
        time_filter = datetime.utcnow().replace(tzinfo=None)  # Ensure naive datetime for comparison
        time_filter = time_filter - timedelta(hours=hours)
        
        # Get all news items with embeddings from the specified time period
        stmt = select(NewsItem).filter(
            NewsItem.last_seen_at >= time_filter,
            NewsItem.embedding.is_not(None)
        ).order_by(NewsItem.last_seen_at.desc())
        
        result = await db.execute(stmt)
        news_items = result.scalars().all()
        
        if not news_items:
            return []

        # Extract embeddings and create UMAP input
        embeddings = [item.embedding for item in news_items]
        
        # Perform UMAP dimensionality reduction
        reducer = umap.UMAP(n_components=2, random_state=42)
        umap_result = reducer.fit_transform(embeddings)
        
        # Calculate time-based opacity
        now = datetime.utcnow().replace(tzinfo=None)  # Ensure naive datetime
        one_hour_ago = now - timedelta(hours=1)
        yesterday = now - timedelta(days=1)
        
        # Combine UMAP coordinates with news items
        visualization_data = []
        for i, news_item in enumerate(news_items):
            # Convert last_seen_at to naive datetime for comparison if it has timezone info
            last_seen = news_item.last_seen_at
            if last_seen and last_seen.tzinfo:
                last_seen = last_seen.replace(tzinfo=None)
            
            # Calculate opacity based on age
            if last_seen and last_seen >= one_hour_ago:
                opacity = 0.8
            elif last_seen and last_seen <= yesterday:
                opacity = 0.2
            else:
                # Linear interpolation between 0.8 and 0.2 for items between 1 hour and 1 day old
                hours_old = (now - last_seen).total_seconds() / 3600 if last_seen else 24
                opacity = 0.8 - (0.6 * (hours_old - 1) / 23)  # 23 = 24 - 1
            
            visualization_data.append({
                "id": news_item.id,
                "title": news_item.title,
                "url": news_item.url,
                "source_url": news_item.source_url,
                "last_seen_at": news_item.last_seen_at.isoformat() if news_item.last_seen_at else None,
                "x": float(umap_result[i][0]),
                "y": float(umap_result[i][1]),
                "cluster_id": item_to_cluster.get(news_item.id),  # Add cluster ID
                "opacity": opacity  # Add opacity
            })
        
        return visualization_data
        
    except Exception as e:
        logger.error(f"UMAP visualization error: {str(e)}")
        raise

async def update_visualizations(db: AsyncSession):
    """Update all pre-generated visualizations."""
    try:
        # Generate clusters for different time ranges and similarities
        time_ranges = [48]  # 48 hours
        similarities = [0.6]  # Restored to 0.6
        
        for hours in time_ranges:
            # Generate UMAP visualization
            umap_data = await generate_umap_visualization(db, hours, similarities[0])
            
            # For each similarity value, generate and store UMAP visualization
            for min_similarity in similarities:
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
            
            # Generate and store clusters for different similarities
            for min_similarity in similarities:
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
        
        await db.commit()
        logger.info("Successfully updated all visualizations")
        
    except Exception as e:
        logger.error(f"Error updating visualizations: {str(e)}")
        await db.rollback()
        raise
