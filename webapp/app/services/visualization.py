"""Shared visualization service for generating clusters and UMAP visualizations."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import umap
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from app.models.news import NewsItem, NewsItemSimilarity
from app.config import settings

logger = logging.getLogger(__name__)

async def generate_clusters(
    db: AsyncSession,
    hours: int = 24,
    min_similarity: float = 0.2
) -> Dict[int, List[dict]]:
    """Generate news clusters based on vector similarity using PostgreSQL."""
    try:
        # Get news items from the last n hours
        time_filter = datetime.utcnow() - timedelta(hours=hours)
        
        # First, get all the recent news items with embeddings
        items_query = select(NewsItem).filter(
            NewsItem.last_seen_at >= time_filter,
            NewsItem.embedding.is_not(None)
        ).order_by(NewsItem.last_seen_at.desc())
        
        result = await db.execute(items_query)
        news_items = result.scalars().all()
        
        # Create a dictionary to store items by ID for easy lookup
        items_by_id = {item.id: item for item in news_items}
        
        # Get all pairwise similarities above threshold
        similarity_query = text("""
            WITH items AS (
                SELECT id 
                FROM news
                WHERE last_seen_at >= :time_filter AND embedding IS NOT NULL
                ORDER BY last_seen_at DESC
            )
            SELECT 
                a.id AS item1_id,
                b.id AS item2_id,
                1 - cosine_distance(a.embedding, b.embedding) AS similarity
            FROM news a
            JOIN news b ON a.id < b.id  -- Use < instead of != to avoid duplicates
            JOIN items ia ON a.id = ia.id
            JOIN items ib ON b.id = ib.id
            WHERE 1 - cosine_distance(a.embedding, b.embedding) >= :min_similarity
            ORDER BY similarity DESC
        """)
        
        # Execute the similarity query
        similarity_result = await db.execute(similarity_query, {
            "time_filter": time_filter,
            "min_similarity": min_similarity
        })
        
        # Build an undirected graph of similar items
        similarity_pairs = []
        for row in similarity_result:
            similarity_pairs.append((row.item1_id, row.item2_id, row.similarity))
        
        # Create a graph representation
        graph = {}
        for item1_id, item2_id, similarity in similarity_pairs:
            if item1_id not in graph:
                graph[item1_id] = []
            if item2_id not in graph:
                graph[item2_id] = []
            
            graph[item1_id].append((item2_id, similarity))
            graph[item2_id].append((item1_id, similarity))
        
        # Find connected components (clusters)
        visited = set()
        clusters = []
        
        for node in graph:
            if node in visited:
                continue
                
            # Start a new cluster
            cluster = []
            queue = [(node, 1.0)]  # (node_id, similarity to center)
            cluster_visited = set()
            
            while queue:
                current, similarity = queue.pop(0)
                
                if current in cluster_visited:
                    continue
                    
                cluster_visited.add(current)
                visited.add(current)
                
                if current in items_by_id:
                    item = items_by_id[current]
                    cluster.append({
                        'id': item.id,
                        'title': item.title,
                        'summary': item.summary,
                        'url': item.url,
                        'source_url': item.source_url,
                        'first_seen_at': item.first_seen_at,
                        'last_seen_at': item.last_seen_at,
                        'hit_count': item.hit_count,
                        'created_at': item.created_at,
                        'updated_at': item.updated_at,
                        'similarity': similarity
                    })
                
                if current in graph:
                    for neighbor, edge_similarity in graph[current]:
                        if neighbor not in cluster_visited:
                            # Calculate transitive similarity (product of similarities along the path)
                            transitive_similarity = similarity * edge_similarity
                            queue.append((neighbor, transitive_similarity))
            
            # Add cluster if it has at least 2 items
            if len(cluster) >= 2:
                # Sort by similarity descending
                cluster.sort(key=lambda x: x['similarity'], reverse=True)
                clusters.append(cluster)
        
        # Sort clusters by size (descending) and recency
        clusters.sort(key=lambda x: (len(x), max(item['last_seen_at'] for item in x)), reverse=True)
        
        # Format the response
        response_clusters = {i: cluster for i, cluster in enumerate(clusters)}
        return response_clusters
        
    except Exception as e:
        logger.error(f"Clustering error: {str(e)}")
        raise

async def generate_umap_visualization(
    db: AsyncSession,
    hours: int = 24,
    min_similarity: float = 0.6
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
        
        # Get clusters to assign cluster IDs to the visualization
        clusters_data = await generate_clusters(db, hours, min_similarity)
        
        # Create a mapping of news item IDs to cluster IDs
        item_to_cluster = {}
        for cluster_id, items in clusters_data.items():
            for item in items:
                item_to_cluster[item['id']] = int(cluster_id)
        
        # Calculate the age of each item for opacity
        now = datetime.utcnow()
        max_age = timedelta(hours=hours)
        
        # Combine UMAP coordinates with news items
        visualization_data = []
        for i, news_item in enumerate(news_items):
            # Calculate age-based opacity (newer = more opaque)
            age = now - news_item.last_seen_at
            opacity = max(0.3, 1.0 - (age / max_age))
            
            visualization_data.append({
                "id": news_item.id,
                "title": news_item.title,
                "url": news_item.url,
                "source_url": news_item.source_url,
                "last_seen_at": news_item.last_seen_at.isoformat(),
                "x": float(umap_result[i][0]),
                "y": float(umap_result[i][1]),
                "cluster_id": item_to_cluster.get(news_item.id),
                "opacity": opacity
            })
        
        return visualization_data
        
    except Exception as e:
        logger.error(f"UMAP visualization error: {str(e)}")
        raise
