from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pgvector.sqlalchemy import Vector
import time
import logging
from sqlalchemy.dialects.postgresql import ARRAY, FLOAT

from app.models.url import URL, URLCreate, URLDatabase
from app.models.news import NewsItem, NewsItemResponse, NewsItemSimilarity
from app.services.db import get_db, url_db
from app.services.embedding import get_embedding_service, EmbeddingService
from app.config import settings

router = APIRouter(tags=["api"])

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

# Important: Place specific routes before parameterized routes
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
        
        # Convert the embedding list to a Vector
        vector_embedding = Vector(query_embedding)
        
        # Search for similar news items using cosine similarity
        stmt = select(
            NewsItem,
            func.cosine_distance(NewsItem.embedding, vector_embedding).label("distance")
        ).filter(
            NewsItem.embedding.is_not(None)
        ).order_by(
            func.cosine_distance(NewsItem.embedding, vector_embedding)
        ).limit(limit)
        
        result = await db.execute(stmt)
        news_items = []
        
        for item, distance in result:
            news_item = NewsItemSimilarity.from_orm(item)
            news_item.similarity = (1.0 - float(distance)) / 2.0
            news_items.append(news_item)
        
        return news_items
        
    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

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

# Place parameterized routes last
@router.get("/news/{news_id}", response_model=NewsItemResponse)
async def get_news_item(news_id: int, db: AsyncSession = Depends(get_db)):
    """Get a news item by ID."""
    result = await db.execute(select(NewsItem).filter(NewsItem.id == news_id))
    news_item = result.scalars().first()
    
    if not news_item:
        raise HTTPException(status_code=404, detail="News item not found")
    
    return news_item
