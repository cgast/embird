"""Web routes for the application."""
from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import List, Optional, Dict
import time
from datetime import datetime, timedelta, timezone
import numpy as np

from app.models.url import URL, URLCreate, URLDatabase
from app.models.news import NewsItem, NewsClusters, NewsUMAP
from app.models.preference_vector import PreferenceVector, PreferenceVectorCreate, PreferenceVectorResponse
from app.models.topic import Topic, TopicCreate
from app.services.db import get_db, url_db, get_all_topics
from app.services.visualization import generate_clusters, generate_umap_visualization, update_visualizations
from app.services.embedding import get_embedding_service
from app.services.faiss_service import get_faiss_service
from app.config import settings

# Configure logging
import logging
logger = logging.getLogger(__name__)
router = APIRouter()


async def _resolve_topic(topic_slug: str, db: AsyncSession) -> Topic:
    """Resolve a topic slug to a Topic object, raising 404 if not found."""
    result = await db.execute(select(Topic).filter(Topic.slug == topic_slug))
    topic = result.scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic '{topic_slug}' not found")
    return topic


async def _base_context(request: Request, db: AsyncSession, topic: Topic) -> dict:
    """Build the base template context with topic info."""
    topics = await get_all_topics(db)
    return {
        "request": request,
        "topic": topic,
        "topic_slug": topic.slug,
        "topics": topics,
        "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
        "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT,
        "enable_topic_management": settings.ENABLE_TOPIC_MANAGEMENT,
    }


# ---- Root routes ----

@router.get("/", response_class=HTMLResponse)
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    """Redirect to the default topic."""
    return RedirectResponse(url=f"/{settings.DEFAULT_TOPIC_SLUG}/", status_code=302)


@router.get("/topics", response_class=HTMLResponse)
async def topics_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Render the topics management page."""
    topics = await get_all_topics(db)
    # Get article counts per topic
    topic_stats = {}
    for topic in topics:
        result = await db.execute(
            select(func.count(NewsItem.id)).filter(NewsItem.topic_id == topic.id)
        )
        topic_stats[topic.id] = result.scalar() or 0

    return request.state.templates.TemplateResponse(
        "topics.html",
        {
            "request": request,
            "topics": topics,
            "topic_stats": topic_stats,
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT,
            "enable_topic_management": settings.ENABLE_TOPIC_MANAGEMENT,
        }
    )


@router.post("/topics")
async def create_topic(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db)
):
    """Create a new topic."""
    if not settings.ENABLE_TOPIC_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Topic management is disabled")
    try:
        topic_data = TopicCreate(name=name, slug=slug, description=description)
        topic = Topic(name=topic_data.name, slug=topic_data.slug, description=topic_data.description)
        db.add(topic)
        await db.commit()
        return RedirectResponse(url="/topics", status_code=303)
    except Exception as e:
        topics = await get_all_topics(db)
        return request.state.templates.TemplateResponse(
            "topics.html",
            {
                "request": request,
                "topics": topics,
                "topic_stats": {},
                "error": str(e),
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT,
                "enable_topic_management": settings.ENABLE_TOPIC_MANAGEMENT,
            }
        )


@router.post("/topics/{topic_slug}/delete")
async def delete_topic(topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Delete a topic and all its data."""
    if not settings.ENABLE_TOPIC_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Topic management is disabled")
    if topic_slug == settings.DEFAULT_TOPIC_SLUG:
        raise HTTPException(status_code=400, detail="Cannot delete the default topic")

    topic = await _resolve_topic(topic_slug, db)

    # Delete all associated data
    await db.execute(select(NewsItem).filter(NewsItem.topic_id == topic.id))
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

    return RedirectResponse(url="/topics", status_code=303)


# ---- Topic-scoped routes ----

@router.get("/{topic_slug}/", response_class=HTMLResponse)
async def index(request: Request, topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Render the home page for a topic."""
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)

    # Get news items from last 24 hours for this topic
    time_filter = datetime.now(timezone.utc) - timedelta(hours=24)
    query = select(NewsItem).filter(
        NewsItem.topic_id == topic.id,
        NewsItem.last_seen_at >= time_filter,
        NewsItem.embedding.isnot(None)
    ).order_by(NewsItem.last_seen_at.desc())
    result = await db.execute(query)
    news_items = result.scalars().all()

    # Get preference vectors for this topic
    query = select(PreferenceVector).filter(
        PreferenceVector.topic_id == topic.id,
        PreferenceVector.embedding.is_not(None)
    )
    result = await db.execute(query)
    preference_vectors = result.scalars().all()

    # Calculate proximity scores
    scored_items = []
    for item in news_items:
        try:
            if item.embedding is None:
                continue

            vector_scores = []
            total_score = 0

            for pv in preference_vectors:
                if pv.embedding is None:
                    continue

                news_vector = np.array(item.embedding.tolist(), dtype=np.float32)
                pv_vector = np.array(pv.embedding.tolist(), dtype=np.float32)

                news_norm = np.linalg.norm(news_vector)
                pv_norm = np.linalg.norm(pv_vector)

                if news_norm == 0 or pv_norm == 0:
                    continue

                news_vector = news_vector / news_norm
                pv_vector = pv_vector / pv_norm

                similarity = float(np.dot(news_vector, pv_vector))

                if similarity > 0:
                    vector_scores.append({
                        'vector': pv,
                        'score': similarity
                    })
                    total_score += similarity

            vector_scores.sort(key=lambda x: x['score'], reverse=True)
            top_vectors = vector_scores[:5]

            scored_items.append({
                'item': item,
                'total_score': total_score,
                'top_vectors': top_vectors
            })
        except Exception as e:
            logger.error(f"Error processing item {item.id}: {str(e)}")
            continue

    scored_items.sort(key=lambda x: x['total_score'], reverse=True)

    # Get URLs for this topic
    urls = url_db.get_all_urls(topic_id=topic.id)

    # Count total news items for this topic
    count_query = select(func.count()).select_from(NewsItem).filter(NewsItem.topic_id == topic.id)
    result = await db.execute(count_query)
    total_news = result.scalar()

    ctx.update({
        "scored_items": scored_items,
        "urls": urls,
        "total_news": total_news,
    })
    return request.state.templates.TemplateResponse("index.html", ctx)


@router.get("/{topic_slug}/urls", response_class=HTMLResponse)
async def list_urls(request: Request, topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Render the URLs page for a topic."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)
    urls = url_db.get_all_urls(topic_id=topic.id)
    ctx.update({"urls": urls, "mode": "list"})
    return request.state.templates.TemplateResponse("url_form.html", ctx)


@router.get("/{topic_slug}/urls/add", response_class=HTMLResponse)
async def add_url_form(request: Request, topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Render the add URL form for a topic."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)
    ctx.update({"mode": "add"})
    return request.state.templates.TemplateResponse("url_form.html", ctx)


@router.post("/{topic_slug}/urls/add")
async def add_url(
    request: Request,
    topic_slug: str,
    url: str = Form(...),
    type: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle URL form submission for a topic."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    topic = await _resolve_topic(topic_slug, db)
    try:
        url_create = URLCreate(url=url, type=type)
        url_db.add_url(url_create, topic_id=topic.id)
        return RedirectResponse(url=f"/{topic_slug}/urls", status_code=303)
    except Exception as e:
        ctx = await _base_context(request, db, topic)
        ctx.update({"error": str(e), "mode": "add"})
        return request.state.templates.TemplateResponse("url_form.html", ctx)


@router.get("/{topic_slug}/urls/{url_id}/delete")
async def delete_url_confirm(request: Request, topic_slug: str, url_id: int, db: AsyncSession = Depends(get_db)):
    """Render delete URL confirmation page."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    topic = await _resolve_topic(topic_slug, db)
    url_item = url_db.get_url_by_id(url_id)
    if not url_item:
        raise HTTPException(status_code=404, detail="URL not found")
    ctx = await _base_context(request, db, topic)
    ctx.update({"url": url_item, "mode": "delete"})
    return request.state.templates.TemplateResponse("url_form.html", ctx)


@router.post("/{topic_slug}/urls/{url_id}/delete")
async def delete_url_handle(topic_slug: str, url_id: int, db: AsyncSession = Depends(get_db)):
    """Handle URL deletion."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    await _resolve_topic(topic_slug, db)
    success = url_db.delete_url(url_id)
    if not success:
        raise HTTPException(status_code=404, detail="URL not found")
    return RedirectResponse(url=f"/{topic_slug}/urls", status_code=303)


@router.get("/{topic_slug}/news", response_class=HTMLResponse)
async def list_news(
    request: Request,
    topic_slug: str,
    db: AsyncSession = Depends(get_db),
    source_url: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """Render the news list page for a topic."""
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)

    offset = (page - 1) * per_page

    query = select(NewsItem).filter(
        NewsItem.topic_id == topic.id
    ).order_by(NewsItem.last_seen_at.desc())

    if source_url:
        query = query.filter(NewsItem.source_url == source_url)

    query = query.limit(per_page).offset(offset)
    result = await db.execute(query)
    news_items = result.scalars().all()

    count_query = select(func.count()).select_from(NewsItem).filter(NewsItem.topic_id == topic.id)
    if source_url:
        count_query = count_query.filter(NewsItem.source_url == source_url)

    result = await db.execute(count_query)
    total_items = result.scalar()
    total_pages = (total_items + per_page - 1) // per_page

    urls = url_db.get_all_urls(topic_id=topic.id)

    ctx.update({
        "news_items": news_items,
        "urls": urls,
        "current_source": source_url,
        "page": page,
        "total_pages": total_pages,
        "total_items": total_items,
    })
    return request.state.templates.TemplateResponse("news_list.html", ctx)


@router.get("/{topic_slug}/news/{news_id}", response_class=HTMLResponse)
async def view_news_item(
    request: Request,
    topic_slug: str,
    news_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Render a single news item page."""
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)

    result = await db.execute(select(NewsItem).filter(NewsItem.id == news_id, NewsItem.topic_id == topic.id))
    news_item = result.scalars().first()

    if not news_item:
        raise HTTPException(status_code=404, detail="News item not found")

    related_query = select(NewsItem).filter(
        NewsItem.topic_id == topic.id,
        NewsItem.source_url == news_item.source_url,
        NewsItem.id != news_item.id
    ).order_by(NewsItem.last_seen_at.desc()).limit(5)

    related_result = await db.execute(related_query)
    related_items = related_result.scalars().all()

    ctx.update({
        "news_item": news_item,
        "related_items": related_items,
    })
    return request.state.templates.TemplateResponse("news_detail.html", ctx)


@router.get("/{topic_slug}/search", response_class=HTMLResponse)
async def search_form(request: Request, topic_slug: str, db: AsyncSession = Depends(get_db)):
    """Render the search form for a topic."""
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)
    urls = url_db.get_all_urls(topic_id=topic.id)
    ctx.update({"urls": urls})
    return request.state.templates.TemplateResponse("search.html", ctx)


@router.get("/{topic_slug}/clusters", response_class=HTMLResponse)
async def view_clusters(
    request: Request,
    topic_slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Render the news clusters page for a topic."""
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)

    try:
        # Try to get pre-generated clusters for this topic
        result = await db.execute(
            select(NewsClusters).filter(
                NewsClusters.topic_id == topic.id,
                NewsClusters.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsClusters.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsClusters.created_at.desc())
        )
        clusters = result.scalars().first()

        if not clusters:
            clusters_data = await generate_clusters(
                db,
                hours=settings.VISUALIZATION_TIME_RANGE,
                min_similarity=settings.VISUALIZATION_SIMILARITY,
                topic_id=topic.id
            )
        else:
            clusters_data = clusters.clusters

        def _serialize_article_web(item):
            if isinstance(item, dict):
                return {
                    'id': item.get('id'),
                    'title': item.get('title', ''),
                    'summary': item.get('summary', ''),
                    'url': item.get('url', ''),
                    'source_url': item.get('source_url', ''),
                    'similarity': float(item.get('similarity', 0.0)),
                    'hit_count': int(item.get('hit_count', 1)),
                    'first_seen_at': item.get('first_seen_at'),
                    'last_seen_at': item.get('last_seen_at'),
                    'created_at': item.get('created_at'),
                    'updated_at': item.get('updated_at')
                }
            return item

        def _serialize_subclusters_web(subclusters):
            if not subclusters:
                return None
            result = []
            for sub in subclusters:
                serialized = {
                    'name': sub.get('name', 'Subtopic'),
                    'articles': [_serialize_article_web(a) for a in sub.get('articles', [])],
                }
                child_subs = sub.get('subclusters')
                serialized['subclusters'] = _serialize_subclusters_web(child_subs) if child_subs else None
                result.append(serialized)
            return result

        serializable_clusters = {}
        for cluster_id, cluster_info in clusters_data.items():
            if isinstance(cluster_info, dict) and 'articles' in cluster_info:
                articles = cluster_info['articles']
                serializable_items = [_serialize_article_web(item) for item in articles]
                subclusters = cluster_info.get('subclusters')

                if serializable_items:
                    cluster_result = {
                        'name': cluster_info.get('name', f'Cluster {cluster_id}'),
                        'articles': serializable_items,
                    }
                    if subclusters:
                        cluster_result['subclusters'] = _serialize_subclusters_web(subclusters)
                    serializable_clusters[str(cluster_id)] = cluster_result
            else:
                serializable_items = []
                items = cluster_info if isinstance(cluster_info, list) else []
                for item in items:
                    if isinstance(item, dict):
                        serializable_items.append(_serialize_article_web(item))
                if serializable_items:
                    serializable_clusters[str(cluster_id)] = serializable_items

        ctx.update({
            "initial_clusters": serializable_clusters,
            "hours": settings.VISUALIZATION_TIME_RANGE,
            "min_similarity": settings.VISUALIZATION_SIMILARITY * 100,
        })
        return request.state.templates.TemplateResponse("news_clusters.html", ctx)
    except Exception as e:
        logger.error(f"Error loading clusters: {str(e)}")
        ctx.update({"error": "Failed to load clusters. Please try again later."})
        return request.state.templates.TemplateResponse("news_clusters.html", ctx)


@router.get("/{topic_slug}/umap")
async def view_umap(
    request: Request,
    topic_slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Render the UMAP visualization page for a topic."""
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)

    try:
        start_time = time.time()

        result = await db.execute(
            select(NewsUMAP).filter(
                NewsUMAP.topic_id == topic.id,
                NewsUMAP.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsUMAP.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsUMAP.created_at.desc())
        )
        umap_data = result.scalars().first()

        if not umap_data:
            visualization_data = await generate_umap_visualization(
                db,
                hours=settings.VISUALIZATION_TIME_RANGE,
                min_similarity=settings.VISUALIZATION_SIMILARITY,
                topic_id=topic.id
            )
        else:
            visualization_data = umap_data.visualization

        logger.info(f"UMAP visualization generated in {time.time() - start_time:.2f} seconds")

        accept = request.headers.get("accept", "")
        if "application/json" in accept:
            return JSONResponse({
                "visualization": visualization_data,
                "hours": settings.VISUALIZATION_TIME_RANGE,
                "min_similarity": settings.VISUALIZATION_SIMILARITY * 100,
            })

        ctx.update({
            "initial_visualization": visualization_data,
            "hours": settings.VISUALIZATION_TIME_RANGE,
            "min_similarity": settings.VISUALIZATION_SIMILARITY * 100,
        })
        return request.state.templates.TemplateResponse("news_umap.html", ctx)
    except Exception as e:
        logger.error(f"Error loading UMAP visualization: {str(e)}", exc_info=True)
        error_msg = "Failed to load visualization. Please try again later."

        accept = request.headers.get("accept", "")
        if "application/json" in accept:
            return JSONResponse({"error": error_msg}, status_code=500)

        ctx.update({"error": error_msg})
        return request.state.templates.TemplateResponse("news_umap.html", ctx)


# ---- Preference Vector Routes (topic-scoped) ----

@router.get("/{topic_slug}/preference-vectors", response_class=HTMLResponse)
async def list_preference_vectors(request: Request, topic_slug: str, db: AsyncSession = Depends(get_db)):
    """List all preference vectors for a topic."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    topic = await _resolve_topic(topic_slug, db)
    ctx = await _base_context(request, db, topic)
    result = await db.execute(select(PreferenceVector).filter(PreferenceVector.topic_id == topic.id))
    vectors = result.scalars().all()
    ctx.update({"vectors": vectors})
    return request.state.templates.TemplateResponse("preference_vectors.html", ctx)


@router.post("/{topic_slug}/preference-vectors")
async def create_preference_vector(
    request: Request,
    topic_slug: str,
    title: str = Form(...),
    description: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Create a new preference vector for a topic."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    topic = await _resolve_topic(topic_slug, db)
    try:
        embedding_service = get_embedding_service()
        embedding = await embedding_service.get_embedding(description)

        vector = PreferenceVector(
            title=title,
            description=description,
            embedding=embedding,
            topic_id=topic.id
        )
        db.add(vector)
        await db.commit()

        await update_visualizations(db, topic_id=topic.id)

        return RedirectResponse(url=f"/{topic_slug}/preference-vectors", status_code=303)
    except Exception as e:
        ctx = await _base_context(request, db, topic)
        ctx.update({"error": str(e)})
        result = await db.execute(select(PreferenceVector).filter(PreferenceVector.topic_id == topic.id))
        vectors = result.scalars().all()
        ctx.update({"vectors": vectors})
        return request.state.templates.TemplateResponse("preference_vectors.html", ctx)


@router.post("/{topic_slug}/preference-vectors/{vector_id}")
async def update_preference_vector(
    request: Request,
    topic_slug: str,
    vector_id: int,
    title: str = Form(...),
    description: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Update a preference vector."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    topic = await _resolve_topic(topic_slug, db)
    try:
        embedding_service = get_embedding_service()
        embedding = await embedding_service.get_embedding(description)

        result = await db.execute(select(PreferenceVector).filter(
            PreferenceVector.id == vector_id,
            PreferenceVector.topic_id == topic.id
        ))
        vector = result.scalar_one_or_none()
        if not vector:
            raise HTTPException(status_code=404, detail="Preference vector not found")

        vector.title = title
        vector.description = description
        vector.embedding = embedding
        vector.updated_at = func.now()

        await db.commit()
        await update_visualizations(db, topic_id=topic.id)

        return RedirectResponse(url=f"/{topic_slug}/preference-vectors", status_code=303)
    except Exception as e:
        ctx = await _base_context(request, db, topic)
        result = await db.execute(select(PreferenceVector).filter(PreferenceVector.topic_id == topic.id))
        vectors = result.scalars().all()
        ctx.update({"vectors": vectors, "error": str(e)})
        return request.state.templates.TemplateResponse("preference_vectors.html", ctx)


@router.post("/{topic_slug}/preference-vectors/{vector_id}/delete")
async def delete_preference_vector(request: Request, topic_slug: str, vector_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a preference vector."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    topic = await _resolve_topic(topic_slug, db)

    result = await db.execute(select(PreferenceVector).filter(
        PreferenceVector.id == vector_id,
        PreferenceVector.topic_id == topic.id
    ))
    vector = result.scalar_one_or_none()
    if not vector:
        raise HTTPException(status_code=404, detail="Preference vector not found")

    await db.delete(vector)
    await db.commit()
    await update_visualizations(db, topic_id=topic.id)

    return RedirectResponse(url=f"/{topic_slug}/preference-vectors", status_code=303)
