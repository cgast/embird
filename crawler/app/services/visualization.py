"""Shared visualization service for generating clusters and UMAP visualizations."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import umap
from sqlalchemy import select, text, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem, NewsClusters, NewsUMAP

logger = logging.getLogger(__name__)

async def generate_clusters(
    db: AsyncSession,
    hours: int = 24,
    min_similarity: float = 0.2
) -> Dict[int, List[dict]]:
    """Generate news clusters based on vector similarity."""
    try:
        # Get news items from the last n hours
        time_filter = datetime.utcnow() - timedelta(hours=hours)
        
        # Get all news items with embeddings from the specified time period
        stmt = select(NewsItem).filter(
            NewsItem.last_seen_at >= time_filter,
            NewsItem.embedding.is_not(None)
        ).order_by(NewsItem.last_seen_at.desc())
        
        result = await db.execute(stmt)
        news_items = result.scalars().all()
        
        # Initialize clusters
        clusters: Dict[int, List[Tuple[NewsItem, float]]] = {}  # Store (NewsItem, similarity) pairs
        cluster_vectors: Dict[int, List[float]] = {}
        next_cluster_id = 0
        
        # Helper function to calculate average vector
        def average_vectors(vectors: List[List[float]]) -> List[float]:
            if not vectors:
                return []
            return [sum(x) / len(vectors) for x in zip(*vectors)]
        
        logger.info("Processing news items %s", len(news_items))

        # Process each news item
        for news_item in news_items:
            item_vector = news_item.embedding
            assigned_cluster = None
            
            # Check similarity with existing clusters
            for cluster_id, cluster_vector in cluster_vectors.items():
                # Calculate cosine similarity using PostgreSQL's function
                similarity_stmt = text(
                    "SELECT (1 - cosine_distance(cast(:vec1 as vector(1024)), cast(:vec2 as vector(1024)))) as similarity"
                )
                similarity_result = await db.execute(
                    similarity_stmt,
                    {
                        "vec1": f"[{','.join(str(x) for x in item_vector)}]",
                        "vec2": f"[{','.join(str(x) for x in cluster_vector)}]"
                    }
                )
                similarity = similarity_result.scalar()
                
                if similarity >= min_similarity:
                    assigned_cluster = cluster_id
                    # Update cluster vector with new average
                    cluster_items = [item for item, _ in clusters[cluster_id]]
                    all_vectors = [item.embedding for item in cluster_items] + [item_vector]
                    cluster_vectors[cluster_id] = average_vectors(all_vectors)
                    clusters[cluster_id].append((news_item, similarity))
                    break
            
            # If no similar cluster found, create new cluster
            if assigned_cluster is None:
                clusters[next_cluster_id] = [(news_item, 1.0)]  # Center item has perfect similarity
                cluster_vectors[next_cluster_id] = item_vector
                next_cluster_id += 1
        
        # Convert to response format
        response_clusters: Dict[int, List[dict]] = {}
        for cluster_id, items in clusters.items():
            # Sort items by similarity
            sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
            
            # Convert to dictionary format with serializable dates
            response_items = []
            for item, similarity in sorted_items:
                response_items.append({
                    "id": item.id,
                    "title": item.title,
                    "summary": item.summary,
                    "url": item.url,
                    "source_url": item.source_url,
                    "first_seen_at": item.first_seen_at.isoformat() if item.first_seen_at else None,
                    "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
                    "hit_count": item.hit_count,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                    "similarity": float(similarity)  # Ensure similarity is a float
                })
            
            response_clusters[cluster_id] = response_items
        
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
        
        # Combine UMAP coordinates with news items
        visualization_data = []
        for i, news_item in enumerate(news_items):
            visualization_data.append({
                "id": news_item.id,
                "title": news_item.title,
                "url": news_item.url,
                "source_url": news_item.source_url,
                "last_seen_at": news_item.last_seen_at.isoformat() if news_item.last_seen_at else None,
                "x": float(umap_result[i][0]),
                "y": float(umap_result[i][1])
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
        similarities = [0.6]  # 60% similarity
        
        for hours in time_ranges:
            # Generate UMAP visualization
            umap_data = await generate_umap_visualization(db, hours)
            
            # Check if UMAP visualization exists
            stmt = select(NewsUMAP).filter(NewsUMAP.hours == hours)
            result = await db.execute(stmt)
            existing_umap = result.scalar_one_or_none()
            
            if existing_umap:
                # Update existing visualization
                stmt = update(NewsUMAP).where(NewsUMAP.hours == hours).values(
                    visualization=umap_data,
                    created_at=func.now()
                )
                await db.execute(stmt)
            else:
                # Create new visualization
                umap_viz = NewsUMAP(
                    hours=hours,
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
