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
from app.services.db import get_db, url_db
from app.services.visualization import generate_clusters, generate_umap_visualization, update_visualizations
from app.services.embedding import get_embedding_service
from app.services.faiss_service import get_faiss_service
from app.config import settings

# Configure logging
import logging
logger = logging.getLogger(__name__)    
router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    """Render the home page."""
    # Get news items from last 24 hours
    time_filter = datetime.now(timezone.utc) - timedelta(hours=24)
    query = select(NewsItem).filter(
        NewsItem.last_seen_at >= time_filter,
        NewsItem.embedding.isnot(None)  # Use isnot(None) for proper NULL check
    ).order_by(NewsItem.last_seen_at.desc())
    result = await db.execute(query)
    news_items = result.scalars().all()
    
    # Get all preference vectors from PostgreSQL if enabled
    preference_vectors = []
    query = select(PreferenceVector).filter(PreferenceVector.embedding.is_not(None))
    result = await db.execute(query)
    preference_vectors = result.scalars().all()
    
    # Calculate proximity scores for each news item
    scored_items = []
    
    for item in news_items:
        try:
            # Skip if no embedding
            if item.embedding is None:
                continue
                
            # Calculate similarity to each preference vector
            vector_scores = []
            total_score = 0
            
            for pv in preference_vectors:
                if pv.embedding is None:
                    continue
                    
                # Calculate cosine similarity
                news_vector = np.array(item.embedding.tolist(), dtype=np.float32)
                pv_vector = np.array(pv.embedding.tolist(), dtype=np.float32)
                
                # Normalize vectors
                news_norm = np.linalg.norm(news_vector)
                pv_norm = np.linalg.norm(pv_vector)
                
                if news_norm == 0 or pv_norm == 0:
                    continue
                    
                news_vector = news_vector / news_norm
                pv_vector = pv_vector / pv_norm
                
                # Calculate similarity
                similarity = float(np.dot(news_vector, pv_vector))
                
                if similarity > 0:  # Only consider positive similarities
                    vector_scores.append({
                        'vector': pv,
                        'score': similarity
                    })
                    total_score += similarity
            
            # Sort vector scores and get top 5
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
    
    # Sort items by total score
    scored_items.sort(key=lambda x: x['total_score'], reverse=True)
    
    # Get all URLs
    urls = url_db.get_all_urls()
    
    # Count total news items
    count_query = select(func.count()).select_from(NewsItem)
    result = await db.execute(count_query)
    total_news = result.scalar()
    
    return request.state.templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "scored_items": scored_items,
            "urls": urls,
            "total_news": total_news,
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.get("/urls", response_class=HTMLResponse)
async def list_urls(request: Request):
    """Render the URLs page."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    urls = url_db.get_all_urls()
    return request.state.templates.TemplateResponse(
        "url_form.html",
        {
            "request": request,
            "urls": urls,
            "mode": "list",
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.get("/urls/add", response_class=HTMLResponse)
async def add_url_form(request: Request):
    """Render the add URL form."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    return request.state.templates.TemplateResponse(
        "url_form.html",
        {
            "request": request,
            "mode": "add",
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.post("/urls/add")
async def add_url(
    request: Request,
    url: str = Form(...),
    type: str = Form(...)
):
    """Handle URL form submission."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    try:
        url_create = URLCreate(url=url, type=type)
        url_db.add_url(url_create)
        return RedirectResponse(url="/urls", status_code=303)
    except Exception as e:
        return request.state.templates.TemplateResponse(
            "url_form.html",
            {
                "request": request,
                "error": str(e),
                "mode": "add",
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
            }
        )

@router.get("/urls/{url_id}/delete")
async def delete_url_confirm(request: Request, url_id: int):
    """Render delete URL confirmation page."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    url = url_db.get_url_by_id(url_id)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")
    
    return request.state.templates.TemplateResponse(
        "url_form.html",
        {
            "request": request,
            "url": url,
            "mode": "delete",
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.post("/urls/{url_id}/delete")
async def delete_url_handle(url_id: int):
    """Handle URL deletion."""
    if not settings.ENABLE_URL_MANAGEMENT:
        raise HTTPException(status_code=403, detail="URL management is disabled")
    success = url_db.delete_url(url_id)
    if not success:
        raise HTTPException(status_code=404, detail="URL not found")
    
    return RedirectResponse(url="/urls", status_code=303)

@router.get("/news", response_class=HTMLResponse)
async def list_news(
    request: Request,
    db: AsyncSession = Depends(get_db),
    source_url: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """Render the news list page."""
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get news items
    query = select(NewsItem).order_by(NewsItem.last_seen_at.desc())
    
    if source_url:
        query = query.filter(NewsItem.source_url == source_url)
    
    query = query.limit(per_page).offset(offset)
    result = await db.execute(query)
    news_items = result.scalars().all()
    
    # Get total count for pagination
    count_query = select(func.count()).select_from(NewsItem)
    
    if source_url:
        count_query = count_query.filter(NewsItem.source_url == source_url)
    
    result = await db.execute(count_query)
    total_items = result.scalar()
    
    total_pages = (total_items + per_page - 1) // per_page
    
    # Get all URLs for filter dropdown
    urls = url_db.get_all_urls()
    
    return request.state.templates.TemplateResponse(
        "news_list.html",
        {
            "request": request,
            "news_items": news_items,
            "urls": urls,
            "current_source": source_url,
            "page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.get("/news/{news_id}", response_class=HTMLResponse)
async def view_news_item(
    request: Request,
    news_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Render a single news item page."""
    result = await db.execute(select(NewsItem).filter(NewsItem.id == news_id))
    news_item = result.scalars().first()
    
    if not news_item:
        raise HTTPException(status_code=404, detail="News item not found")
    
    # Get related news items (from same source)
    related_query = select(NewsItem).filter(
        NewsItem.source_url == news_item.source_url,
        NewsItem.id != news_item.id
    ).order_by(
        NewsItem.last_seen_at.desc()
    ).limit(5)
    
    related_result = await db.execute(related_query)
    related_items = related_result.scalars().all()
    
    return request.state.templates.TemplateResponse(
        "news_detail.html",
        {
            "request": request,
            "news_item": news_item,
            "related_items": related_items,
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.get("/search", response_class=HTMLResponse)
async def search_form(request: Request):
    """Render the search form."""
    return request.state.templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.get("/clusters", response_class=HTMLResponse)
async def view_clusters(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Render the news clusters page."""
    try:
        # Try to get pre-generated clusters
        result = await db.execute(
            select(NewsClusters).filter(
                NewsClusters.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsClusters.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsClusters.created_at.desc())
        )
        clusters = result.scalars().first()
        
        # If no pre-generated clusters found, generate them with parameters
        if not clusters:
            clusters_data = await generate_clusters(
                db,
                hours=settings.VISUALIZATION_TIME_RANGE,
                min_similarity=settings.VISUALIZATION_SIMILARITY
            )
        else:
            clusters_data = clusters.clusters
            
        def _serialize_article_web(item):
            """Serialize a single article for the web template."""
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
            """Recursively serialize subclusters for the web template."""
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

        # Convert clusters data to JSON-serializable format
        serializable_clusters = {}
        for cluster_id, cluster_info in clusters_data.items():
            # Handle both old format (list of items) and new format (dict with name/articles/subclusters)
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
                # Old format: cluster_info is a list of items
                serializable_items = []
                items = cluster_info if isinstance(cluster_info, list) else []
                for item in items:
                    if isinstance(item, dict):
                        serializable_items.append(_serialize_article_web(item))
                if serializable_items:
                    serializable_clusters[str(cluster_id)] = serializable_items
        
        return request.state.templates.TemplateResponse(
            "news_clusters.html",
            {
                "request": request,
                "initial_clusters": serializable_clusters,
                "hours": settings.VISUALIZATION_TIME_RANGE,
                "min_similarity": settings.VISUALIZATION_SIMILARITY * 100,  # Convert to percentage for display
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
            }
        )
    except Exception as e:
        logger.error(f"Error loading clusters: {str(e)}")
        return request.state.templates.TemplateResponse(
            "news_clusters.html",
            {
                "request": request,
                "error": "Failed to load clusters. Please try again later.",
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
            }
        )

@router.get("/umap")
async def view_umap(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Render the UMAP visualization page."""
    try:
        start_time = time.time()
        logger.info("Generating UMAP visualization using settings")
        
        # Try to get pre-generated visualization
        result = await db.execute(
            select(NewsUMAP).filter(
                NewsUMAP.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsUMAP.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsUMAP.created_at.desc())
        )
        umap_data = result.scalars().first()
        
        # If no pre-generated visualization found, generate it with parameters
        if not umap_data:
            logger.info("No pre-generated UMAP data found, generating new visualization")
            visualization_data = await generate_umap_visualization(
                db,
                hours=settings.VISUALIZATION_TIME_RANGE,
                min_similarity=settings.VISUALIZATION_SIMILARITY
            )
        else:
            logger.info(f"Using pre-generated UMAP data from {umap_data.created_at}")
            visualization_data = umap_data.visualization
        
        logger.info(f"UMAP visualization generated in {time.time() - start_time:.2f} seconds")
        
        # Check if request wants JSON
        accept = request.headers.get("accept", "")
        if "application/json" in accept:
            return JSONResponse({
                "visualization": visualization_data,
                "hours": settings.VISUALIZATION_TIME_RANGE,
                "min_similarity": settings.VISUALIZATION_SIMILARITY * 100,
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
            })
        
        # Otherwise return HTML
        return request.state.templates.TemplateResponse(
            "news_umap.html",
            {
                "request": request,
                "initial_visualization": visualization_data,
                "hours": settings.VISUALIZATION_TIME_RANGE,
                "min_similarity": settings.VISUALIZATION_SIMILARITY * 100,  # Convert to percentage for display
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
            }
        )
    except Exception as e:
        logger.error(f"Error loading UMAP visualization: {str(e)}", exc_info=True)
        error_msg = "Failed to load visualization. Please try again later."
        
        # Return error in requested format
        accept = request.headers.get("accept", "")
        if "application/json" in accept:
            return JSONResponse({"error": error_msg}, status_code=500)
            
        return request.state.templates.TemplateResponse(
            "news_umap.html",
            {
                "request": request,
                "error": error_msg,
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
            }
        )

# Preference Vector Routes
@router.get("/preference-vectors", response_class=HTMLResponse)
async def list_preference_vectors(request: Request, db: AsyncSession = Depends(get_db)):
    """List all preference vectors."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    result = await db.execute(select(PreferenceVector))
    vectors = result.scalars().all()
    return request.state.templates.TemplateResponse(
        "preference_vectors.html",
        {
            "request": request,
            "vectors": vectors,
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.get("/preference-vectors/new", response_class=HTMLResponse)
async def new_preference_vector(request: Request):
    """Show form to create a new preference vector."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    return request.state.templates.TemplateResponse(
        "preference_vector_form.html",
        {
            "request": request,
            "vector": None,
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.post("/preference-vectors")
async def create_preference_vector(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Create a new preference vector."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    try:
        # Get embedding service
        embedding_service = get_embedding_service()
        
        # Generate embedding from description
        embedding = await embedding_service.get_embedding(description)
        
        # Create vector with embedding
        vector = PreferenceVector(
            title=title,
            description=description,
            embedding=embedding
        )
        db.add(vector)
        await db.commit()
        
        # Update visualizations after adding new preference vector
        await update_visualizations(db)
        
        return RedirectResponse(url="/preference-vectors", status_code=303)
    except Exception as e:
        return request.state.templates.TemplateResponse(
            "preference_vector_form.html",
            {
                "request": request,
                "vector": None,
                "error": str(e),
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
            }
        )

@router.get("/preference-vectors/{vector_id}/edit", response_class=HTMLResponse)
async def edit_preference_vector(request: Request, vector_id: int, db: AsyncSession = Depends(get_db)):
    """Show form to edit a preference vector."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    result = await db.execute(select(PreferenceVector).filter(PreferenceVector.id == vector_id))
    vector = result.scalar_one_or_none()
    if not vector:
        raise HTTPException(status_code=404, detail="Preference vector not found")
    
    return request.state.templates.TemplateResponse(
        "preference_vector_form.html",
        {
            "request": request,
            "vector": vector,
            "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
            "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
        }
    )

@router.post("/preference-vectors/{vector_id}")
async def update_preference_vector(
    request: Request,
    vector_id: int,
    title: str = Form(...),
    description: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Update a preference vector."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    try:
        # Get embedding service
        embedding_service = get_embedding_service()
        
        # Generate new embedding from updated description
        embedding = await embedding_service.get_embedding(description)
        
        # Update vector with new embedding
        result = await db.execute(select(PreferenceVector).filter(PreferenceVector.id == vector_id))
        vector = result.scalar_one_or_none()
        if not vector:
            raise HTTPException(status_code=404, detail="Preference vector not found")
        
        vector.title = title
        vector.description = description
        vector.embedding = embedding
        vector.updated_at = func.now()
        
        await db.commit()
        
        # Update visualizations after modifying preference vector
        await update_visualizations(db)
        
        return RedirectResponse(url="/preference-vectors", status_code=303)
    except Exception as e:
        result = await db.execute(select(PreferenceVector).filter(PreferenceVector.id == vector_id))
        vector = result.scalar_one_or_none()
        return request.state.templates.TemplateResponse(
            "preference_vector_form.html",
            {
                "request": request,
                "vector": vector,
                "error": str(e),
                "enable_url_management": settings.ENABLE_URL_MANAGEMENT,
                "enable_preference_management": settings.ENABLE_PREFERENCE_MANAGEMENT
            }
        )

@router.post("/preference-vectors/{vector_id}/delete")
async def delete_preference_vector(request: Request, vector_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a preference vector."""
    if not settings.ENABLE_PREFERENCE_MANAGEMENT:
        raise HTTPException(status_code=403, detail="Preference vector management is disabled")
    result = await db.execute(select(PreferenceVector).filter(PreferenceVector.id == vector_id))
    vector = result.scalar_one_or_none()
    if not vector:
        raise HTTPException(status_code=404, detail="Preference vector not found")
    
    await db.delete(vector)
    await db.commit()
    
    # Update visualizations after deleting preference vector
    await update_visualizations(db)
    
    return RedirectResponse(url="/preference-vectors", status_code=303)
