"""API routes for the application."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
from app.models.topic import Topic, TopicCreate, TopicUpdate, TopicResponse
from app.services.db import get_db, url_db, get_all_topics
from app.services.embedding import get_embedding_service, EmbeddingService
from app.services.visualization import generate_clusters, generate_umap_visualization
from app.services.faiss_service import get_faiss_service
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


async def _resolve_topic(topic_slug: str, db: AsyncSession) -> Topic:
    """Resolve a topic slug to a Topic object."""
    result = await db.execute(select(Topic).filter(Topic.slug == topic_slug))
    topic = result.scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic '{topic_slug}' not found")
    return topic


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


# ---- Topic Endpoints ----

@router.get("/topics", response_model=List[TopicResponse])
async def list_topics(db: AsyncSession = Depends(get_db)):
    """List all topics."""
    topics = await get_all_topics(db)
    return topics

@router.post("/topics", response_model=TopicResponse)
async def create_topic(topic_data: TopicCreate, db: AsyncSession = Depends(get_db)):
    """Create a new topic."""
    if not settings.ENABLE_TOPIC_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Topic management is disabled")
    try:
        topic = Topic(name=topic_data.name, slug=topic_data.slug, description=topic_data.description)
        db.add(topic)
        await db.commit()
        await db.refresh(topic)
        return topic
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/topics/{topic_slug}", response_model=TopicResponse)
async def get_topic(topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Get a topic by slug."""
    return await _resolve_topic(topic_slug, db)

@router.put("/topics/{topic_slug}", response_model=TopicResponse)
async def update_topic(topic_slug: str, topic_data: TopicUpdate, db: AsyncSession = Depends(get_db)):
    """Update a topic's name and/or description."""
    if not settings.ENABLE_TOPIC_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Topic management is disabled")
    topic = await _resolve_topic(topic_slug, db)
    if topic_data.name is not None:
        topic.name = topic_data.name
    if topic_data.description is not None:
        topic.description = topic_data.description
    await db.commit()
    await db.refresh(topic)
    return topic

@router.delete("/topics/{topic_slug}")
async def delete_topic(topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Delete a topic."""
    if not settings.ENABLE_TOPIC_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Topic management is disabled")
    if topic_slug == settings.DEFAULT_TOPIC_SLUG:
        raise HTTPException(status_code=400, detail="Cannot delete the default topic")

    topic = await _resolve_topic(topic_slug, db)

    from sqlalchemy import delete
    await db.execute(delete(NewsItem).where(NewsItem.topic_id == topic.id))
    await db.execute(delete(PreferenceVector).where(PreferenceVector.topic_id == topic.id))
    await db.execute(delete(NewsClusters).where(NewsClusters.topic_id == topic.id))
    await db.execute(delete(NewsUMAP).where(NewsUMAP.topic_id == topic.id))
    await db.delete(topic)
    await db.commit()

    # Also delete URLs for this topic from SQLite
    urls = url_db.get_all_urls(topic_id=topic.id)
    for u in urls:
        url_db.delete_url(u.id)

    return {"deleted": True}


# ---- Topic-scoped URL Endpoints ----

@router.get("/{topic_slug}/urls", response_model=List[URL])
async def get_urls(topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Get all URLs for a topic."""
    topic = await _resolve_topic(topic_slug, db)
    return url_db.get_all_urls(topic_id=topic.id)

@router.post("/{topic_slug}/urls", response_model=URL)
async def create_url(topic_slug: str, url: URLCreate, db: AsyncSession = Depends(get_db)):
    """Create a new URL for a topic."""
    topic = await _resolve_topic(topic_slug, db)
    try:
        return url_db.add_url(url, topic_id=topic.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{topic_slug}/urls/{url_id}", response_model=URL)
async def get_url(topic_slug: str, url_id: int, db: AsyncSession = Depends(get_db)):
    """Get a URL by ID."""
    await _resolve_topic(topic_slug, db)
    url = url_db.get_url_by_id(url_id)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")
    return url

@router.delete("/{topic_slug}/urls/{url_id}", response_model=bool)
async def delete_url(topic_slug: str, url_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a URL by ID."""
    await _resolve_topic(topic_slug, db)
    success = url_db.delete_url(url_id)
    if not success:
        raise HTTPException(status_code=404, detail="URL not found")
    return success


# ---- Topic-scoped News Endpoints ----

@router.get("/{topic_slug}/news", response_model=List[NewsItemResponse])
async def get_news(
    topic_slug: str,
    db: AsyncSession = Depends(get_db),
    source_url: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get news items for a topic."""
    topic = await _resolve_topic(topic_slug, db)
    query = select(NewsItem).filter(
        NewsItem.topic_id == topic.id
    ).order_by(NewsItem.last_seen_at.desc())

    if source_url:
        query = query.filter(NewsItem.source_url == source_url)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{topic_slug}/news/search", response_model=List[NewsItemSimilarity])
async def search_news(
    topic_slug: str,
    query: str,
    db: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    source_url: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100)
):
    """Search news items by semantic similarity within a topic."""
    topic = await _resolve_topic(topic_slug, db)

    if not query or not query.strip():
        raise HTTPException(status_code=422, detail="Search query cannot be empty")

    query = query.strip()

    try:
        if not settings.COHERE_API_KEY:
            raise HTTPException(status_code=422, detail="Cohere API key not configured")

        query_embedding = await embedding_service.get_embedding(query)

        if not query_embedding:
            raise HTTPException(status_code=422, detail="Failed to generate embedding")

        faiss_service = get_faiss_service()

        faiss_limit = limit * 5 if source_url else limit
        similar_items = await faiss_service.search_similar(
            db,
            np.array(query_embedding, dtype=np.float32),
            k=faiss_limit,
            min_similarity=0.5,
            topic_id=topic.id
        )

        if similar_items:
            item_ids = [item_id for item_id, _ in similar_items]
            stmt = select(NewsItem).filter(NewsItem.id.in_(item_ids), NewsItem.topic_id == topic.id)
            if source_url:
                stmt = stmt.filter(NewsItem.source_url == source_url)
            result = await db.execute(stmt)
            db_items = {item.id: item for item in result.scalars().all()}

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

        # Fallback to database search
        vector_str = f"[{','.join(str(x) for x in query_embedding)}]"
        source_filter_sql = "AND source_url = :source_url" if source_url else ""

        stmt = text(f"""
            SELECT
                id, title, summary, url, source_url,
                first_seen_at, last_seen_at, hit_count,
                created_at, updated_at,
                cosine_distance(embedding, cast(:vector as vector(1024))) as distance
            FROM news
            WHERE embedding IS NOT NULL AND topic_id = :topic_id {source_filter_sql}
            ORDER BY cosine_distance(embedding, cast(:vector as vector(1024)))
            LIMIT :limit
        """)

        params = {
            "vector": vector_str,
            "topic_id": topic.id,
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
                updated_at=row.updated_at,
                topic_id=topic.id
            )

            item_data = news_item.__dict__.copy()
            item_data['similarity'] = (1.0 - float(row.distance)) / 2.0
            response_item = NewsItemSimilarity.model_validate(item_data)
            news_items.append(response_item)

        return news_items

    except Exception as e:
        logging.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/{topic_slug}/news/clusters", response_model=Dict[str, Dict])
async def get_news_clusters(topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Get clustered news items for a topic."""
    topic = await _resolve_topic(topic_slug, db)

    try:
        result = await db.execute(
            select(NewsClusters).filter(
                NewsClusters.topic_id == topic.id,
                NewsClusters.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsClusters.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsClusters.created_at.desc())
        )
        clusters = result.scalars().first()

        if clusters:
            cluster_data = clusters.clusters
        else:
            cluster_data = await generate_clusters(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY, topic_id=topic.id)

            stmt = pg_insert(NewsClusters).values(
                topic_id=topic.id,
                hours=settings.VISUALIZATION_TIME_RANGE,
                min_similarity=settings.VISUALIZATION_SIMILARITY,
                clusters=cluster_data,
                created_at=func.now()
            ).on_conflict_do_update(
                constraint='uix_topic_hours_similarity',
                set_=dict(clusters=cluster_data, created_at=func.now())
            )
            await db.execute(stmt)
            await db.commit()

        def _serialize_article(item):
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
            if not subclusters:
                return None
            result = []
            for sub in subclusters:
                serialized_sub = {
                    'name': sub.get('name', 'Subtopic'),
                    'articles': [_serialize_article(a) for a in sub.get('articles', [])],
                }
                child_subs = sub.get('subclusters')
                serialized_sub['subclusters'] = _serialize_subclusters(child_subs) if child_subs else None
                result.append(serialized_sub)
            return result

        serialized_clusters = {}
        for cluster_id, cluster_info in cluster_data.items():
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

            if subclusters:
                cluster_result['subclusters'] = _serialize_subclusters(subclusters)

            serialized_clusters[str(cluster_id)] = cluster_result

        return serialized_clusters

    except Exception as e:
        logging.error(f"Clustering error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{topic_slug}/news/umap", response_model=List[dict])
async def get_news_umap(topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Get UMAP visualization data for a topic."""
    topic = await _resolve_topic(topic_slug, db)

    try:
        result = await db.execute(
            select(NewsUMAP).filter(
                NewsUMAP.topic_id == topic.id,
                NewsUMAP.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsUMAP.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsUMAP.created_at.desc())
        )
        umap_data = result.scalars().first()

        if umap_data:
            return umap_data.visualization

        return await generate_umap_visualization(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY, topic_id=topic.id)

    except Exception as e:
        logging.error(f"UMAP visualization error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{topic_slug}/news/stats")
async def get_news_stats(topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Get system statistics for a topic."""
    topic = await _resolve_topic(topic_slug, db)

    try:
        now = datetime.utcnow()
        h24 = now - timedelta(hours=24)
        h48 = now - timedelta(hours=48)

        total_result = await db.execute(select(func.count(NewsItem.id)).filter(NewsItem.topic_id == topic.id))
        total_articles = total_result.scalar() or 0

        r24 = await db.execute(select(func.count(NewsItem.id)).filter(NewsItem.topic_id == topic.id, NewsItem.created_at >= h24))
        articles_24h = r24.scalar() or 0

        r48 = await db.execute(select(func.count(NewsItem.id)).filter(NewsItem.topic_id == topic.id, NewsItem.created_at >= h48))
        articles_48h = r48.scalar() or 0

        src_result = await db.execute(select(func.count(func.distinct(NewsItem.source_url))).filter(NewsItem.topic_id == topic.id))
        unique_sources = src_result.scalar() or 0

        trending_result = await db.execute(
            select(func.count(NewsItem.id)).filter(NewsItem.topic_id == topic.id, NewsItem.hit_count > 1)
        )
        trending_count = trending_result.scalar() or 0

        avg_hits_result = await db.execute(select(func.avg(NewsItem.hit_count)).filter(NewsItem.topic_id == topic.id))
        avg_hit_count = round(float(avg_hits_result.scalar() or 1), 2)

        timeline_stmt = text("""
            SELECT
                date_trunc('hour', created_at) as hour,
                count(*) as count
            FROM news
            WHERE created_at >= :since AND topic_id = :topic_id
            GROUP BY date_trunc('hour', created_at)
            ORDER BY hour ASC
        """)
        timeline_result = await db.execute(timeline_stmt, {"since": h48, "topic_id": topic.id})
        activity_timeline = [
            {"hour": row.hour.isoformat(), "count": row.count}
            for row in timeline_result
        ]

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
            WHERE created_at >= :since AND topic_id = :topic_id
            GROUP BY bucket
            ORDER BY min(extract(epoch from (last_seen_at - first_seen_at)))
        """)
        lifespan_result = await db.execute(lifespan_stmt, {"since": h48, "topic_id": topic.id})
        lifespan_distribution = [
            {"bucket": row.bucket, "count": row.count}
            for row in lifespan_result
        ]

        newest_result = await db.execute(
            select(NewsItem.created_at).filter(NewsItem.topic_id == topic.id).order_by(NewsItem.created_at.desc()).limit(1)
        )
        newest_article = newest_result.scalar()

        oldest_recent_result = await db.execute(
            select(NewsItem.created_at).filter(NewsItem.topic_id == topic.id, NewsItem.created_at >= h48).order_by(NewsItem.created_at.asc()).limit(1)
        )
        oldest_recent = oldest_recent_result.scalar()

        cluster_result = await db.execute(
            select(NewsClusters).filter(NewsClusters.topic_id == topic.id).order_by(NewsClusters.created_at.desc()).limit(1)
        )
        cluster_row = cluster_result.scalars().first()
        cluster_info = None
        if cluster_row:
            cluster_data_raw = cluster_row.clusters or {}
            total_clustered = sum(
                len(c.get('articles', [])) if isinstance(c, dict) else 0
                for c in cluster_data_raw.values()
            )
            cluster_info = {
                "generated_at": cluster_row.created_at.isoformat() if cluster_row.created_at else None,
                "num_clusters": len(cluster_data_raw),
                "total_articles_clustered": total_clustered,
                "hours": cluster_row.hours,
                "min_similarity": cluster_row.min_similarity
            }

        top_sources_stmt = text("""
            SELECT source_url, count(*) as count
            FROM news
            WHERE created_at >= :since AND topic_id = :topic_id
            GROUP BY source_url
            ORDER BY count DESC
            LIMIT 10
        """)
        top_sources_result = await db.execute(top_sources_stmt, {"since": h48, "topic_id": topic.id})
        top_sources = [
            {"source_url": row.source_url, "count": row.count}
            for row in top_sources_result
        ]

        return {
            "topic": {"id": topic.id, "name": topic.name, "slug": topic.slug},
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

@router.get("/{topic_slug}/news/trending", response_model=List[NewsItemResponse])
async def get_trending_news(
    topic_slug: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    hours: int = Query(24, ge=1, le=168)
):
    """Get trending news items for a topic."""
    topic = await _resolve_topic(topic_slug, db)

    time_filter = func.now() - func.make_interval(0, 0, 0, 0, hours, 0, 0)

    query = select(NewsItem).filter(
        NewsItem.topic_id == topic.id,
        NewsItem.last_seen_at >= time_filter
    ).order_by(
        NewsItem.hit_count.desc(),
        NewsItem.last_seen_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{topic_slug}/news/{news_id}", response_model=NewsItemResponse)
async def get_news_item(topic_slug: str, news_id: int, db: AsyncSession = Depends(get_db)):
    """Get a news item by ID within a topic."""
    topic = await _resolve_topic(topic_slug, db)

    result = await db.execute(select(NewsItem).filter(NewsItem.id == news_id, NewsItem.topic_id == topic.id))
    news_item = result.scalars().first()

    if not news_item:
        raise HTTPException(status_code=404, detail="News item not found")

    return news_item

@router.get("/{topic_slug}/news/{news_id}/similar", response_model=List[NewsItemSimilarity])
async def get_similar_news(
    topic_slug: str,
    news_id: int,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(5, ge=1, le=20)
):
    """Get similar news items within a topic."""
    topic = await _resolve_topic(topic_slug, db)

    result = await db.execute(select(NewsItem).filter(NewsItem.id == news_id, NewsItem.topic_id == topic.id))
    news_item = result.scalars().first()

    if not news_item:
        raise HTTPException(status_code=404, detail="News item not found")

    if news_item.embedding is None:
        return []

    try:
        faiss_service = get_faiss_service()
        query_vector = np.array(news_item.embedding, dtype=np.float32)
        similar_results = await faiss_service.search_similar(
            db, query_vector, k=limit + 1, min_similarity=0.5, topic_id=topic.id
        )

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


# ---- Topic-scoped Preference Vector Endpoints ----

@router.get("/{topic_slug}/preference-vectors", response_model=List[PreferenceVectorResponse])
async def get_preference_vectors(topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Get all preference vectors for a topic."""
    if not settings.ENABLE_PREFERENCE_VECTORS:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    topic = await _resolve_topic(topic_slug, db)

    result = await db.execute(select(PreferenceVector).filter(PreferenceVector.topic_id == topic.id))
    return result.scalars().all()

@router.post("/{topic_slug}/preference-vectors", response_model=PreferenceVectorResponse)
async def create_preference_vector(
    topic_slug: str,
    vector_data: PreferenceVectorCreate,
    db: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Create a new preference vector for a topic."""
    if not settings.ENABLE_PREFERENCE_VECTORS:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    topic = await _resolve_topic(topic_slug, db)

    try:
        embedding = await embedding_service.get_embedding(vector_data.description)
        if not embedding:
            raise HTTPException(status_code=422, detail="Failed to generate embedding")

        vector = PreferenceVector(
            title=vector_data.title,
            description=vector_data.description,
            embedding=embedding,
            topic_id=topic.id
        )

        db.add(vector)
        await db.commit()
        await db.refresh(vector)

        await generate_clusters(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY, topic_id=topic.id)
        await generate_umap_visualization(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY, topic_id=topic.id)

        return vector

    except Exception as e:
        logging.error(f"Error creating preference vector: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

@router.put("/{topic_slug}/preference-vectors/{vector_id}", response_model=PreferenceVectorResponse)
async def update_preference_vector(
    topic_slug: str,
    vector_id: int,
    vector_data: PreferenceVectorCreate,
    db: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    """Update a preference vector."""
    if not settings.ENABLE_PREFERENCE_VECTORS:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    topic = await _resolve_topic(topic_slug, db)

    try:
        result = await db.execute(select(PreferenceVector).filter(
            PreferenceVector.id == vector_id,
            PreferenceVector.topic_id == topic.id
        ))
        vector = result.scalars().first()

        if not vector:
            raise HTTPException(status_code=404, detail="Preference vector not found")

        embedding = await embedding_service.get_embedding(vector_data.description)
        if not embedding:
            raise HTTPException(status_code=422, detail="Failed to generate embedding")

        vector.title = vector_data.title
        vector.description = vector_data.description
        vector.embedding = embedding

        await db.commit()
        await db.refresh(vector)

        await generate_clusters(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY, topic_id=topic.id)
        await generate_umap_visualization(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY, topic_id=topic.id)

        return vector

    except Exception as e:
        logging.error(f"Error updating preference vector: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

@router.delete("/{topic_slug}/preference-vectors/{vector_id}", response_model=bool)
async def delete_preference_vector(topic_slug: str, vector_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a preference vector."""
    if not settings.ENABLE_PREFERENCE_VECTORS:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    topic = await _resolve_topic(topic_slug, db)

    result = await db.execute(select(PreferenceVector).filter(
        PreferenceVector.id == vector_id,
        PreferenceVector.topic_id == topic.id
    ))
    vector = result.scalars().first()

    if not vector:
        raise HTTPException(status_code=404, detail="Preference vector not found")

    await db.delete(vector)
    await db.commit()

    await generate_clusters(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY, topic_id=topic.id)
    await generate_umap_visualization(db, settings.VISUALIZATION_TIME_RANGE, settings.VISUALIZATION_SIMILARITY, topic_id=topic.id)

    return True
