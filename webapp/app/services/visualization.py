"""Shared visualization service for generating clusters and UMAP visualizations."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import umap
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from app.models.news import NewsItem, NewsItemSimilarity
from app.config import settings

# Import Redis client
from app.services.redis_client import get_redis_client, RedisClientContextManager

logger = logging.getLogger(__name__)

async def generate_clusters(
    db: AsyncSession,
    hours: int = 24,
    min_similarity: float = 0.2
) -> Dict[int, List[NewsItemSimilarity]]:
    """Generate news clusters based on vector similarity using Redis."""
    try:
        # Try to use Redis for cluster generation
        try:
            # Get Redis client
            async with RedisClientContextManager() as redis_client:
                # Generate clusters using Redis
                redis_clusters = await redis_client.get_clusters(hours, min_similarity)
                
                if redis_clusters:
                    # Convert Redis clusters to the expected format
                    response_clusters = {}
                    
                    for cluster_id, items in redis_clusters.items():
                        # Try to get news items from the database for additional info
                        item_ids = [item["id"] for item in items]
                        stmt = select(NewsItem).filter(NewsItem.id.in_(item_ids))
                        result = await db.execute(stmt)
                        db_items = {item.id: item for item in result.scalars().all()}
                        
                        # Create NewsItemSimilarity objects
                        response_items = []
                        for item in items:
                            # First try to create from database items for complete data
                            if item["id"] in db_items:
                                db_item = db_items[item["id"]]
                                item_data = {
                                    'id': db_item.id,
                                    'title': db_item.title,
                                    'summary': db_item.summary,
                                    'url': db_item.url,
                                    'source_url': db_item.source_url,
                                    'first_seen_at': db_item.first_seen_at,
                                    'last_seen_at': db_item.last_seen_at,
                                    'hit_count': db_item.hit_count,
                                    'created_at': db_item.created_at,
                                    'updated_at': db_item.updated_at,
                                    'similarity': item["similarity"]
                                }
                            else:
                                # Item not in database, use Redis data with defaults for missing fields
                                item_data = {
                                    'id': item["id"],
                                    'title': item.get("title", "Unknown Title"),
                                    'summary': item.get("summary", None),
                                    'url': item.get("url", ""),
                                    'source_url': item.get("source_url", ""),
                                    'similarity': item.get("similarity", 0.5),
                                    'first_seen_at': datetime.now(),
                                    'last_seen_at': datetime.now(),
                                    'hit_count': 1,
                                    'created_at': datetime.now(),
                                    'updated_at': datetime.now()
                                }
                            
                            try:
                                # Add any missing required fields as a fallback
                                if "summary" not in item_data:
                                    item_data["summary"] = None
                                if "first_seen_at" not in item_data:
                                    item_data["first_seen_at"] = datetime.now()
                                if "last_seen_at" not in item_data:
                                    item_data["last_seen_at"] = datetime.now()
                                if "hit_count" not in item_data:
                                    item_data["hit_count"] = 1
                                if "created_at" not in item_data:
                                    item_data["created_at"] = datetime.now()
                                if "updated_at" not in item_data:
                                    item_data["updated_at"] = datetime.now()
                                    
                                response_item = NewsItemSimilarity.model_validate(item_data)
                                response_items.append(response_item)
                            except Exception as model_error:
                                print(f"Error creating NewsItemSimilarity model: {model_error}, data: {item_data}")
                        
                        if response_items:
                            response_clusters[cluster_id] = sorted(
                                response_items, 
                                key=lambda x: x.similarity, 
                                reverse=True
                            )
                    
                    logger.info(f"Generated {len(response_clusters)} clusters using Redis")
                    return response_clusters
        
        except Exception as e:
            logger.warning(f"Failed to generate clusters using Redis: {str(e)}")
            logger.warning("Falling back to database clustering")
            
        # If Redis clustering failed or returned no results, fall back to database
        # Get news items from the last n hours
        time_filter = datetime.utcnow() - timedelta(hours=hours)
        
        # Get all news items with embeddings from the specified time period
        stmt = select(NewsItem).filter(
            NewsItem.last_seen_at >= time_filter,
            NewsItem.embedding.is_not(None)
        ).order_by(NewsItem.last_seen_at.desc())
        
        result = await db.execute(stmt)
        news_items = result.scalars().all()
        
        if not news_items:
            return {}
            
        # Use direct SQL for faster clustering
        # This generates clusters in a single query using PostgreSQL's vector operations
        cluster_query = text("""
            WITH items AS (
                SELECT id, title, summary, url, source_url, first_seen_at, last_seen_at, 
                       hit_count, created_at, updated_at, embedding
                FROM news
                WHERE last_seen_at >= :time_filter AND embedding IS NOT NULL
                ORDER BY last_seen_at DESC
            ),
            similarities AS (
                SELECT 
                    a.id AS item_id,
                    b.id AS related_id,
                    1 - cosine_distance(a.embedding, b.embedding) AS similarity
                FROM items a
                JOIN items b ON a.id <> b.id
                WHERE 1 - cosine_distance(a.embedding, b.embedding) >= :min_similarity
            ),
            clusters AS (
                SELECT 
                    item_id,
                    ARRAY_AGG(related_id ORDER BY similarity DESC) AS related_ids,
                    ARRAY_AGG(similarity ORDER BY similarity DESC) AS similarities
                FROM similarities
                GROUP BY item_id
            )
            SELECT 
                c.item_id,
                c.related_ids,
                c.similarities,
                i.title,
                i.summary,
                i.url,
                i.source_url,
                i.first_seen_at,
                i.last_seen_at,
                i.hit_count,
                i.created_at,
                i.updated_at
            FROM clusters c
            JOIN items i ON c.item_id = i.id
            ORDER BY i.last_seen_at DESC
        """)
        
        # Execute the query
        result = await db.execute(cluster_query, {
            "time_filter": time_filter,
            "min_similarity": min_similarity
        })
        
        # Process results into clusters
        response_clusters = {}
        cluster_id = 0
        processed_ids = set()
        
        for row in result:
            # Skip items that are already in a cluster
            if row.item_id in processed_ids:
                continue
                
            # Create a new cluster
            cluster = []
            
            # Add the center item with similarity 1.0
            center_item_data = {
                'id': row.item_id,
                'title': row.title,
                'summary': row.summary,
                'url': row.url,
                'source_url': row.source_url,
                'first_seen_at': row.first_seen_at,
                'last_seen_at': row.last_seen_at,
                'hit_count': row.hit_count,
                'created_at': row.created_at,
                'updated_at': row.updated_at,
                'similarity': 1.0
            }
            center_item = NewsItemSimilarity.model_validate(center_item_data)
            cluster.append(center_item)
            
            # Add related items
            for i, related_id in enumerate(row.related_ids):
                # Skip already processed items
                if related_id in processed_ids:
                    continue
                    
                # Get similarity
                similarity = row.similarities[i]
                
                # Get related item details
                related_result = await db.execute(select(NewsItem).filter(NewsItem.id == related_id))
                related_item = related_result.scalars().first()
                
                if related_item:
                    related_item_data = {
                        'id': related_item.id,
                        'title': related_item.title,
                        'summary': related_item.summary,
                        'url': related_item.url,
                        'source_url': related_item.source_url,
                        'first_seen_at': related_item.first_seen_at,
                        'last_seen_at': related_item.last_seen_at,
                        'hit_count': related_item.hit_count,
                        'created_at': related_item.created_at,
                        'updated_at': related_item.updated_at,
                        'similarity': similarity
                    }
                    related_item_obj = NewsItemSimilarity.model_validate(related_item_data)
                    cluster.append(related_item_obj)
                    
                    # Mark as processed
                    processed_ids.add(related_id)
            
            # Add the cluster if it has items
            if cluster:
                response_clusters[cluster_id] = cluster
                cluster_id += 1
                
                # Mark center item as processed
                processed_ids.add(row.item_id)
        
        return response_clusters
        
    except Exception as e:
        logger.error(f"Clustering error: {str(e)}")
        raise

async def generate_umap_visualization(
    db: AsyncSession,
    hours: int = 24
) -> List[dict]:
    """Generate UMAP visualization data for news items."""
    try:
        # Get news items from the last n hours
        time_filter = datetime.utcnow() - timedelta(hours=hours)
        
        # Get all news items with embeddings from the specified time period
        stmt = select(NewsItem).filter(
            NewsItem.last_seen_at >= time_filter,
            NewsItem.embedding.is_not(None)
        ).order_by(NewsItem.last_seen_at.desc()).limit(1000)  # Limit to 1000 items for performance
        
        result = await db.execute(stmt)
        news_items = result.scalars().all()
        
        if not news_items:
            return []

        # Extract embeddings and create UMAP input
        embeddings = [item.embedding for item in news_items]
        
        # Perform UMAP dimensionality reduction
        reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15)
        umap_result = reducer.fit_transform(embeddings)
        
        # Combine UMAP coordinates with news items
        visualization_data = []
        for i, news_item in enumerate(news_items):
            visualization_data.append({
                "id": news_item.id,
                "title": news_item.title,
                "url": news_item.url,
                "source_url": news_item.source_url,
                "last_seen_at": news_item.last_seen_at.isoformat(),
                "x": float(umap_result[i][0]),
                "y": float(umap_result[i][1])
            })
        
        return visualization_data
        
    except Exception as e:
        logger.error(f"UMAP visualization error: {str(e)}")
        raise
