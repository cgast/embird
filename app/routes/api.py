"""API routes for the application."""
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
from app.models.news import (  # Updated import path
    NewsItem, NewsItemResponse, NewsItemSimilarity,
    NewsClusters, NewsUMAP,
    NewsClustersResponse, NewsUMAPResponse
)
from app.services.db import get_db, url_db
from app.services.embedding import get_embedding_service, EmbeddingService
from app.services.visualization import generate_clusters, generate_umap_visualization
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

@router.get("/news/umap", response_model=List[dict])
async def get_news_umap(
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),  # Default 24 hours, max 1 week
    min_similarity: float = Query(0.6, ge=0.0, le=100.0)  # Accept both decimal and percentage values
):
    """Get UMAP visualization data for news items."""
    try:
        # Convert percentage to decimal if needed
        normalized_similarity = min_similarity / 100.0 if min_similarity > 1.0 else min_similarity
        
        # Try to get pre-generated visualization
        result = await db.execute(
            select(NewsUMAP).filter(NewsUMAP.hours == hours).order_by(NewsUMAP.created_at.desc())
        )
        umap_data = result.scalars().first()
        
        if umap_data:
            return umap_data.visualization
        
        # If no pre-generated data, generate it now
        return await generate_umap_visualization(db, hours, normalized_similarity)
        
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
            
        # Try to use Redis for search
        try:
            # Import Redis client
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
            from crawler.app.services.redis_client import RedisClientContextManager
            
            async with RedisClientContextManager() as redis_client:
                # Search using Redis
                redis_results = await redis_client.search_vectors(query_embedding, limit=limit)
                
                if redis_results:
                    # Get full news items from database
                    item_ids = [item["id"] for item in redis_results]
                    stmt = select(NewsItem).filter(NewsItem.id.in_(item_ids))
                    result = await db.execute(stmt)
                    db_items = {item.id: item for item in result.scalars().all()}
                    
                    # Create NewsItemSimilarity objects
                    news_items = []
                    for item in redis_results:
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
                            response_item = NewsItemSimilarity.model_validate(item_data)
                            news_items.append(response_item)
                    
                    return news_items
        except Exception as e:
            logging.warning(f"Redis search failed, falling back to database: {str(e)}")
        
        # If Redis search fails or returns no results, fall back to database search
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

@router.get("/news/clusters", response_model=Dict[str, List[Dict]])
async def get_news_clusters(
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),  # Default 24 hours, max 1 week
    min_similarity: float = Query(0.6, ge=0.0, le=100.0)  # Accept both decimal and percentage values
):
    """Get clustered news items based on vector similarity."""
    try:
        # Convert percentage to decimal if needed
        normalized_similarity = min_similarity / 100.0 if min_similarity > 1.0 else min_similarity
        
        # Try to get pre-generated clusters
        result = await db.execute(
            select(NewsClusters).filter(
                NewsClusters.hours == hours,
                NewsClusters.min_similarity == normalized_similarity
            ).order_by(NewsClusters.created_at.desc())
        )
        clusters = result.scalars().first()
        
        if clusters:
            cluster_data = clusters.clusters
        else:
            # If no pre-generated clusters, generate them now
            cluster_data = await generate_clusters(db, hours, normalized_similarity)
            
            # Store the newly generated clusters in the database
            new_clusters = NewsClusters(
                hours=hours,
                min_similarity=normalized_similarity,
                clusters=cluster_data
            )
            db.add(new_clusters)
            await db.commit()
        
        # Convert to dictionary with string keys and serialized items
        serialized_clusters = {}
        for cluster_id, items in cluster_data.items():
            serialized_items = []
            for item in items:
                # Handle both dictionaries and objects
                if isinstance(item, dict):
                    # Use get() for all fields to handle missing values safely
                    item_dict = {
                        'id': item.get('id', 0),
                        'title': item.get('title', ''),
                        'summary': item.get('summary', None),
                        'url': item.get('url', ''),
                        'source_url': item.get('source_url', ''),
                        'similarity': item.get('similarity', 0.0),
                        'hit_count': item.get('hit_count', 1),
                    }
                    
                    # Handle datetime fields carefully
                    first_seen = item.get('first_seen_at')
                    if first_seen:
                        item_dict['first_seen_at'] = first_seen.isoformat() if hasattr(first_seen, 'isoformat') else first_seen
                    else:
                        item_dict['first_seen_at'] = datetime.now().isoformat()
                        
                    last_seen = item.get('last_seen_at')
                    if last_seen:
                        item_dict['last_seen_at'] = last_seen.isoformat() if hasattr(last_seen, 'isoformat') else last_seen
                    else:
                        item_dict['last_seen_at'] = datetime.now().isoformat()
                        
                    created_at = item.get('created_at')
                    if created_at:
                        item_dict['created_at'] = created_at.isoformat() if hasattr(created_at, 'isoformat') else created_at
                    else:
                        item_dict['created_at'] = datetime.now().isoformat()
                        
                    updated_at = item.get('updated_at')
                    if updated_at:
                        item_dict['updated_at'] = updated_at.isoformat() if hasattr(updated_at, 'isoformat') else updated_at
                    else:
                        item_dict['updated_at'] = datetime.now().isoformat()
                else:
                    item_dict = {
                        'id': item.id,
                        'title': item.title,
                        'summary': item.summary,
                        'url': item.url,
                        'source_url': item.source_url,
                        'similarity': item.similarity,
                        'first_seen_at': item.first_seen_at.isoformat() if hasattr(item.first_seen_at, 'isoformat') else item.first_seen_at,
                        'last_seen_at': item.last_seen_at.isoformat() if hasattr(item.last_seen_at, 'isoformat') else item.last_seen_at,
                        'hit_count': item.hit_count,
                        'created_at': item.created_at.isoformat() if hasattr(item.created_at, 'isoformat') else item.created_at,
                        'updated_at': item.updated_at.isoformat() if hasattr(item.updated_at, 'isoformat') else item.updated_at
                    }
                serialized_items.append(item_dict)
            
            # Convert numeric cluster_id to string for JSON compatibility
            serialized_clusters[str(cluster_id)] = serialized_items
            
        return serialized_clusters
        
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
