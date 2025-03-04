from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Tuple
from pgvector.sqlalchemy import Vector
import time
import logging
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import ARRAY, FLOAT
import numpy as np
import umap

from app.models.url import URL, URLCreate, URLDatabase
from app.models.news import NewsItem, NewsItemResponse, NewsItemSimilarity
from app.services.db import get_db, url_db
from app.services.embedding import get_embedding_service, EmbeddingService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

@router.get("/news/umap", response_model=List[dict])
async def get_news_umap(
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),  # Default 24 hours, max 1 week
):
    """Get UMAP visualization data for news items."""
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
                "last_seen_at": news_item.last_seen_at.isoformat(),
                "x": float(umap_result[i][0]),
                "y": float(umap_result[i][1])
            })
        
        return visualization_data
        
    except Exception as e:
        logging.error(f"UMAP visualization error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ---- URL Endpoints ----

@router.get("/urls", response_model=List[URL])
async def get_urls():
    """Get all URLs."""
    return url_db.get_all_urls()

@router.post("/urls", response_model=URL)
async def create_url(url: URLCreate):
    """Create a new URL."""
    try:
        return url_db.add_url(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/urls/{url_id}", response_model=URL)
async def get_url(url_id: int):
    """Get a URL by ID."""
    url = url_db.get_url_by_id(url_id)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")
    return url

@router.delete("/urls/{url_id}", response_model=bool)
async def delete_url(url_id: int):
    """Delete a URL by ID."""
    success = url_db.delete_url(url_id)
    if not success:
        raise HTTPException(status_code=404, detail="URL not found")
    return success

# ---- News Endpoints ----

@router.get("/news", response_model=List[NewsItemResponse])
async def get_news(
    db: AsyncSession = Depends(get_db),
    source_url: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get news items with optional filtering by source URL."""
    query = select(NewsItem).order_by(NewsItem.last_seen_at.desc())
    
    if source_url:
        query = query.filter(NewsItem.source_url == source_url)
    
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    news_items = result.scalars().all()
    
    return news_items

@router.get("/news/search", response_model=List[NewsItemSimilarity])
async def search_news(
    query: str,
    db: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    limit: int = Query(10, ge=1, le=100)
):
    """Search news items by semantic similarity."""
    # Validate query
    if not query or not query.strip():
        raise HTTPException(status_code=422, detail="Search query cannot be empty")
    
    # Clean query
    query = query.strip()
    
    try:
        # Verify API key is loaded
        if not settings.COHERE_API_KEY:
            raise HTTPException(status_code=422, detail="Cohere API key not configured")
        
        # Generate embedding for the query
        query_embedding = await embedding_service.get_embedding(query)
        
        if not query_embedding:
            raise HTTPException(status_code=422, detail="Failed to generate embedding")
        
        # Convert embedding to string representation
        vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        # Modified SQL using cast() function instead of :: operator
        stmt = text("""
            SELECT 
                id, title, summary, url, source_url, 
                first_seen_at, last_seen_at, hit_count,
                created_at, updated_at,
                cosine_distance(embedding, cast(:vector as vector(1024))) as distance
            FROM news
            WHERE embedding IS NOT NULL
            ORDER BY cosine_distance(embedding, cast(:vector as vector(1024)))
            LIMIT :limit
        """)

        # Execute query with parameters
        result = await db.execute(
            stmt,
            {
                "vector": vector_str,
                "limit": limit
            }
        )
        
        news_items = []
        for row in result:
            
            # Create a NewsItem instance
            news_item = NewsItem(
                id=row.id,
                title=row.title,
                summary=row.summary,
                url=row.url,
                source_url=row.source_url,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
                hit_count=row.hit_count,
                created_at=row.created_at,
                updated_at=row.updated_at
            )
            
            # First create a dictionary with all needed fields
            item_data = news_item.__dict__.copy()
            item_data['similarity'] = (1.0 - float(row.distance)) / 2.0

            # Then validate the complete data
            response_item = NewsItemSimilarity.model_validate(item_data)
            news_items.append(response_item)

        return news_items
        
    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/news/clusters", response_model=Dict[int, List[NewsItemSimilarity]])
async def get_news_clusters(
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),  # Default 24 hours, max 1 week
    min_similarity: float = Query(0.2, ge=0.0, le=1.0)  # Default 20% similarity
):
    """Get clustered news items based on vector similarity."""
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
            
            logger.info("Processing news item %s", news_item.title)

            # Check similarity with existing clusters
            for cluster_id, cluster_vector in cluster_vectors.items():
                # Calculate cosine similarity using PostgreSQL's function with explicit vector dimension
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
        response_clusters: Dict[int, List[NewsItemSimilarity]] = {}
        for cluster_id, items in clusters.items():
            # Sort items by similarity
            sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
            
            # Convert to NewsItemSimilarity objects
            response_items = []
            for item, similarity in sorted_items:
                item_data = item.__dict__.copy()
                item_data['similarity'] = similarity
                response_item = NewsItemSimilarity.model_validate(item_data)
                response_items.append(response_item)
            
            response_clusters[cluster_id] = response_items
        
        return response_clusters
        
    except Exception as e:
        logging.error(f"Clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news/trending", response_model=List[NewsItemResponse])
async def get_trending_news(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    hours: int = Query(24, ge=1, le=168)  # Default to 24 hours, max 1 week
):
    """Get trending news items based on hit count in a time period."""
    # Get current time minus specified hours
    time_filter = func.now() - func.make_interval(hours=hours)
    
    query = select(NewsItem).filter(
        NewsItem.last_seen_at >= time_filter
    ).order_by(
        NewsItem.hit_count.desc(),
        NewsItem.last_seen_at.desc()
    ).limit(limit)
    
    result = await db.execute(query)
    news_items = result.scalars().all()
    
    return news_items

@router.get("/news/{news_id}", response_model=NewsItemResponse)
async def get_news_item(news_id: int, db: AsyncSession = Depends(get_db)):
    """Get a news item by ID."""
    result = await db.execute(select(NewsItem).filter(NewsItem.id == news_id))
    news_item = result.scalars().first()
    
    if not news_item:
        raise HTTPException(status_code=404, detail="News item not found")
    
    return news_item
