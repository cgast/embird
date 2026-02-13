"""API routes for the application."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Tuple
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel
import time
import logging
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import ARRAY, FLOAT
import numpy as np
import umap

from app.models.url import URL, URLCreate, URLDatabase
from app.models.news import (
    NewsItem, NewsItemResponse, NewsItemSimilarity,
    NewsClusters, NewsUMAP,
    NewsClustersResponse, NewsUMAPResponse
)
from app.models.preference_vector import PreferenceVector, PreferenceVectorCreate, PreferenceVectorResponse
from app.services.db import get_db, url_db
from app.services.embedding import get_embedding_service, EmbeddingService
from app.services.visualization import generate_clusters, generate_umap_visualization
from app.services.faiss_service import get_faiss_service
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


# ---- Auth Endpoint ----

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/login")
async def login(credentials: LoginRequest):
    """Authenticate with admin credentials."""
    if (credentials.username == settings.ADMIN_EMAIL and
            credentials.password == settings.ADMIN_PASSWORD):
        return {"token": "authenticated"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}

@router.get("/news/umap", response_model=List[dict])
async def get_news_umap(db: AsyncSession = Depends(get_db)):
    """Get UMAP visualization data for news items."""
    try:
        # Try to get pre-generated visualization
        result = await db.execute(
            select(NewsUMAP).filter(
                NewsUMAP.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsUMAP.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsUMAP.created_at.desc())
        )
        umap_data = result.scalars().first()
        
        if umap_data:
            return umap_data.visualization
        
        # If no pre-generated data, generate it now
        return await generate_umap_visualization(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY)
        
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
    source_url: Optional[str] = None,
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

        # Get FAISS service
        faiss_service = get_faiss_service()

        # Search using FAISS (fetch more results if filtering by source, since we filter after)
        faiss_limit = limit * 5 if source_url else limit
        similar_items = await faiss_service.search_similar(
            db,
            np.array(query_embedding, dtype=np.float32),
            k=faiss_limit,
            min_similarity=0.5
        )

        if similar_items:
            # Get full news items from database
            item_ids = [item_id for item_id, _ in similar_items]
            stmt = select(NewsItem).filter(NewsItem.id.in_(item_ids))
            if source_url:
                stmt = stmt.filter(NewsItem.source_url == source_url)
            result = await db.execute(stmt)
            db_items = {item.id: item for item in result.scalars().all()}

            # Create NewsItemSimilarity objects
            news_items = []
            for item_id, similarity in similar_items:
                if item_id in db_items:
                    db_item = db_items[item_id]
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
                        'similarity': similarity
                    }
                    response_item = NewsItemSimilarity.model_validate(item_data)
                    news_items.append(response_item)

            if news_items:
                return news_items[:limit]

        # If no results from FAISS, fall back to database search
        vector_str = f"[{','.join(str(x) for x in query_embedding)}]"

        source_filter_sql = "AND source_url = :source_url" if source_url else ""

        stmt = text(f"""
            SELECT
                id, title, summary, url, source_url,
                first_seen_at, last_seen_at, hit_count,
                created_at, updated_at,
                cosine_distance(embedding, cast(:vector as vector(1024))) as distance
            FROM news
            WHERE embedding IS NOT NULL {source_filter_sql}
            ORDER BY cosine_distance(embedding, cast(:vector as vector(1024)))
            LIMIT :limit
        """)

        params = {
            "vector": vector_str,
            "limit": limit
        }
        if source_url:
            params["source_url"] = source_url

        result = await db.execute(stmt, params)

        news_items = []
        for row in result:
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

            item_data = news_item.__dict__.copy()
            item_data['similarity'] = (1.0 - float(row.distance)) / 2.0
            response_item = NewsItemSimilarity.model_validate(item_data)
            news_items.append(response_item)

        return news_items

    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/news/clusters", response_model=Dict[str, Dict])
async def get_news_clusters(db: AsyncSession = Depends(get_db)):
    """Get clustered news items based on vector similarity.

    Returns:
        Dictionary mapping cluster_id to cluster data:
        {
            "cluster_id": {
                "name": "keyword1, keyword2, keyword3",
                "articles": [list of article dicts]
            }
        }
    """
    try:
        # Try to get pre-generated clusters
        result = await db.execute(
            select(NewsClusters).filter(
                NewsClusters.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsClusters.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsClusters.created_at.desc())
        )
        clusters = result.scalars().first()

        if clusters:
            cluster_data = clusters.clusters
        else:
            # If no pre-generated clusters, generate them now
            cluster_data = await generate_clusters(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY)

            # Store the newly generated clusters in the database
            new_clusters = NewsClusters(
                hours=settings.VISUALIZATION_TIME_RANGE,
                min_similarity=settings.VISUALIZATION_SIMILARITY,
                clusters=cluster_data
            )
            db.add(new_clusters)
            await db.commit()

        def _serialize_article(item):
            """Serialize a single article item to a JSON-safe dict."""
            if isinstance(item, dict):
                item_dict = {
                    'id': item.get('id', 0),
                    'title': item.get('title', ''),
                    'summary': item.get('summary', None),
                    'url': item.get('url', ''),
                    'source_url': item.get('source_url', ''),
                    'similarity': item.get('similarity', 0.0),
                    'hit_count': item.get('hit_count', 1),
                }

                for field in ('first_seen_at', 'last_seen_at', 'created_at', 'updated_at'):
                    val = item.get(field)
                    if val:
                        item_dict[field] = val.isoformat() if hasattr(val, 'isoformat') else val
                    else:
                        item_dict[field] = datetime.now().isoformat()
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
            return item_dict

        def _serialize_subclusters(subclusters):
            """Recursively serialize subcluster tree."""
            if not subclusters:
                return None
            result = []
            for sub in subclusters:
                serialized_sub = {
                    'name': sub.get('name', 'Subtopic'),
                    'articles': [_serialize_article(a) for a in sub.get('articles', [])],
                }
                # Recursively serialize nested subclusters
                child_subs = sub.get('subclusters')
                serialized_sub['subclusters'] = _serialize_subclusters(child_subs) if child_subs else None
                result.append(serialized_sub)
            return result

        # Convert to dictionary with string keys and serialized items
        serialized_clusters = {}
        for cluster_id, cluster_info in cluster_data.items():
            # Handle both old format (list of items) and new format (dict with 'name' and 'articles')
            if isinstance(cluster_info, dict) and 'articles' in cluster_info:
                cluster_name = cluster_info.get('name', f'Cluster {cluster_id}')
                items = cluster_info['articles']
                subclusters = cluster_info.get('subclusters')
            else:
                cluster_name = f'Cluster {cluster_id}'
                items = cluster_info
                subclusters = None

            serialized_items = [_serialize_article(item) for item in items]

            cluster_result = {
                'name': cluster_name,
                'articles': serialized_items
            }

            # Include subclusters if present
            if subclusters:
                cluster_result['subclusters'] = _serialize_subclusters(subclusters)

            serialized_clusters[str(cluster_id)] = cluster_result

        return serialized_clusters

    except Exception as e:
        logging.error(f"Clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news/stats")
async def get_news_stats(db: AsyncSession = Depends(get_db)):
    """Get system statistics for the dashboard: article counts, activity timelines, cluster info."""
    try:
        now = datetime.utcnow()

        # Total articles
        total_result = await db.execute(select(func.count(NewsItem.id)))
        total_articles = total_result.scalar() or 0

        # Articles in last 24h, 48h
        h24 = now - timedelta(hours=24)
        h48 = now - timedelta(hours=48)
        r24 = await db.execute(select(func.count(NewsItem.id)).filter(NewsItem.created_at >= h24))
        articles_24h = r24.scalar() or 0
        r48 = await db.execute(select(func.count(NewsItem.id)).filter(NewsItem.created_at >= h48))
        articles_48h = r48.scalar() or 0

        # Unique sources
        src_result = await db.execute(select(func.count(func.distinct(NewsItem.source_url))))
        unique_sources = src_result.scalar() or 0

        # Articles with hit_count > 1 (trending)
        trending_result = await db.execute(
            select(func.count(NewsItem.id)).filter(NewsItem.hit_count > 1)
        )
        trending_count = trending_result.scalar() or 0

        # Average hit count
        avg_hits_result = await db.execute(select(func.avg(NewsItem.hit_count)))
        avg_hit_count = round(float(avg_hits_result.scalar() or 1), 2)

        # Activity timeline: articles created per hour over last 48 hours
        # Using date_trunc to group by hour
        timeline_stmt = text("""
            SELECT
                date_trunc('hour', created_at) as hour,
                count(*) as count
            FROM news
            WHERE created_at >= :since
            GROUP BY date_trunc('hour', created_at)
            ORDER BY hour ASC
        """)
        timeline_result = await db.execute(timeline_stmt, {"since": h48})
        activity_timeline = [
            {"hour": row.hour.isoformat(), "count": row.count}
            for row in timeline_result
        ]

        # Story lifespan distribution: how long stories remain active (last_seen - first_seen)
        lifespan_stmt = text("""
            SELECT
                CASE
                    WHEN extract(epoch from (last_seen_at - first_seen_at)) / 3600 < 1 THEN '<1h'
                    WHEN extract(epoch from (last_seen_at - first_seen_at)) / 3600 < 6 THEN '1-6h'
                    WHEN extract(epoch from (last_seen_at - first_seen_at)) / 3600 < 12 THEN '6-12h'
                    WHEN extract(epoch from (last_seen_at - first_seen_at)) / 3600 < 24 THEN '12-24h'
                    WHEN extract(epoch from (last_seen_at - first_seen_at)) / 3600 < 48 THEN '1-2d'
                    ELSE '2d+'
                END as bucket,
                count(*) as count
            FROM news
            WHERE created_at >= :since
            GROUP BY bucket
            ORDER BY min(extract(epoch from (last_seen_at - first_seen_at)))
        """)
        lifespan_result = await db.execute(lifespan_stmt, {"since": h48})
        lifespan_distribution = [
            {"bucket": row.bucket, "count": row.count}
            for row in lifespan_result
        ]

        # Newest and oldest articles
        newest_result = await db.execute(
            select(NewsItem.created_at).order_by(NewsItem.created_at.desc()).limit(1)
        )
        newest_article = newest_result.scalar()

        oldest_recent_result = await db.execute(
            select(NewsItem.created_at).filter(NewsItem.created_at >= h48).order_by(NewsItem.created_at.asc()).limit(1)
        )
        oldest_recent = oldest_recent_result.scalar()

        # Cluster info
        cluster_result = await db.execute(
            select(NewsClusters).order_by(NewsClusters.created_at.desc()).limit(1)
        )
        cluster_row = cluster_result.scalars().first()
        cluster_info = None
        if cluster_row:
            cluster_data = cluster_row.clusters or {}
            total_clustered = sum(
                len(c.get('articles', [])) if isinstance(c, dict) else 0
                for c in cluster_data.values()
            )
            cluster_info = {
                "generated_at": cluster_row.created_at.isoformat() if cluster_row.created_at else None,
                "num_clusters": len(cluster_data),
                "total_articles_clustered": total_clustered,
                "hours": cluster_row.hours,
                "min_similarity": cluster_row.min_similarity
            }

        # Top sources by article count (last 48h)
        top_sources_stmt = text("""
            SELECT source_url, count(*) as count
            FROM news
            WHERE created_at >= :since
            GROUP BY source_url
            ORDER BY count DESC
            LIMIT 10
        """)
        top_sources_result = await db.execute(top_sources_stmt, {"since": h48})
        top_sources = [
            {"source_url": row.source_url, "count": row.count}
            for row in top_sources_result
        ]

        return {
            "total_articles": total_articles,
            "articles_24h": articles_24h,
            "articles_48h": articles_48h,
            "unique_sources": unique_sources,
            "trending_count": trending_count,
            "avg_hit_count": avg_hit_count,
            "newest_article_at": newest_article.isoformat() if newest_article else None,
            "oldest_recent_at": oldest_recent.isoformat() if oldest_recent else None,
            "activity_timeline": activity_timeline,
            "lifespan_distribution": lifespan_distribution,
            "cluster_info": cluster_info,
            "top_sources": top_sources
        }

    except Exception as e:
        logging.error(f"Stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news/trending", response_model=List[NewsItemResponse])
async def get_trending_news(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    hours: int = Query(24, ge=1, le=168)  # Default to 24 hours, max 1 week
):
    """Get trending news items based on hit count in a time period."""
    # Get current time minus specified hours
    # make_interval signature: (years, months, weeks, days, hours, mins, secs)
    time_filter = func.now() - func.make_interval(0, 0, 0, 0, hours, 0, 0)
    
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

@router.get("/news/{news_id}/similar", response_model=List[NewsItemSimilarity])
async def get_similar_news(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(5, ge=1, le=20)
):
    """Get similar news items using vector proximity."""
    result = await db.execute(select(NewsItem).filter(NewsItem.id == news_id))
    news_item = result.scalars().first()

    if not news_item:
        raise HTTPException(status_code=404, detail="News item not found")

    if news_item.embedding is None:
        return []

    try:
        faiss_service = get_faiss_service()
        query_vector = np.array(news_item.embedding, dtype=np.float32)
        similar_results = await faiss_service.search_similar(
            db, query_vector, k=limit + 1, min_similarity=0.5
        )

        # Filter out the current article
        similar_ids_scores = [(sid, score) for sid, score in similar_results if sid != news_id][:limit]
        if not similar_ids_scores:
            return []

        item_ids = [sid for sid, _ in similar_ids_scores]
        stmt = select(NewsItem).filter(NewsItem.id.in_(item_ids))
        result = await db.execute(stmt)
        db_items = {item.id: item for item in result.scalars().all()}

        news_items = []
        for item_id, similarity in similar_ids_scores:
            if item_id in db_items:
                db_item = db_items[item_id]
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
                    'similarity': similarity
                }
                news_items.append(NewsItemSimilarity.model_validate(item_data))

        return news_items

    except Exception as e:
        logger.error(f"Error fetching similar items for news {news_id}: {str(e)}")
        return []

# ---- Preference Vector Endpoints ----

@router.get("/preference-vectors", response_model=List[PreferenceVectorResponse])
async def get_preference_vectors(db: AsyncSession = Depends(get_db)):
    """Get all preference vectors."""
    if not settings.ENABLE_PREFERENCE_VECTORS:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")

    result = await db.execute(select(PreferenceVector))
    vectors = result.scalars().all()
    return vectors

@router.post("/preference-vectors", response_model=PreferenceVectorResponse)
async def create_preference_vector(
    vector_data: PreferenceVectorCreate,
    db: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Create a new preference vector."""
    if not settings.ENABLE_PREFERENCE_VECTORS:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")

    try:
        # Generate embedding from description
        embedding = await embedding_service.get_embedding(vector_data.description)

        if not embedding:
            raise HTTPException(status_code=422, detail="Failed to generate embedding")

        # Create vector
        vector = PreferenceVector(
            title=vector_data.title,
            description=vector_data.description,
            embedding=embedding
        )

        db.add(vector)
        await db.commit()
        await db.refresh(vector)

        # Update visualizations after adding new preference vector
        await generate_clusters(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY)
        await generate_umap_visualization(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY)

        return vector

    except Exception as e:
        logging.error(f"Error creating preference vector: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

@router.put("/preference-vectors/{vector_id}", response_model=PreferenceVectorResponse)
async def update_preference_vector(
    vector_id: int,
    vector_data: PreferenceVectorCreate,
    db: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Update a preference vector."""
    if not settings.ENABLE_PREFERENCE_VECTORS:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")

    try:
        result = await db.execute(select(PreferenceVector).filter(PreferenceVector.id == vector_id))
        vector = result.scalars().first()

        if not vector:
            raise HTTPException(status_code=404, detail="Preference vector not found")

        # Generate new embedding
        embedding = await embedding_service.get_embedding(vector_data.description)

        if not embedding:
            raise HTTPException(status_code=422, detail="Failed to generate embedding")

        # Update vector
        vector.title = vector_data.title
        vector.description = vector_data.description
        vector.embedding = embedding

        await db.commit()
        await db.refresh(vector)

        # Update visualizations after modifying preference vector
        await generate_clusters(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY)
        await generate_umap_visualization(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY)

        return vector

    except Exception as e:
        logging.error(f"Error updating preference vector: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

@router.delete("/preference-vectors/{vector_id}", response_model=bool)
async def delete_preference_vector(vector_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a preference vector."""
    if not settings.ENABLE_PREFERENCE_VECTORS:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")

    result = await db.execute(select(PreferenceVector).filter(PreferenceVector.id == vector_id))
    vector = result.scalars().first()

    if not vector:
        raise HTTPException(status_code=404, detail="Preference vector not found")

    await db.delete(vector)
    await db.commit()

    # Update visualizations after deleting preference vector
    await generate_clusters(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY)
    await generate_umap_visualization(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY)

    return True
