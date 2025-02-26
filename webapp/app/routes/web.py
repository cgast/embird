from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import time

from app.models.url import URL, URLCreate, URLDatabase
from app.models.news import NewsItem
from app.services.db import get_db, url_db

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    """Render the home page."""
    # Get latest news items
    query = select(NewsItem).order_by(NewsItem.last_seen_at.desc()).limit(10)
    result = await db.execute(query)
    news_items = result.scalars().all()
    
    # Get trending news items
    time_filter = func.now() - func.make_interval(hours=24)
    trending_query = select(NewsItem).filter(
        NewsItem.last_seen_at >= time_filter
    ).order_by(
        NewsItem.hit_count.desc(),
        NewsItem.last_seen_at.desc()
    ).limit(5)
    
    trending_result = await db.execute(trending_query)
    trending_news = trending_result.scalars().all()
    
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
            "news_items": news_items,
            "trending_news": trending_news,
            "urls": urls,
            "total_news": total_news
        }
    )

@router.get("/urls", response_class=HTMLResponse)
async def list_urls(request: Request):
    """Render the URLs page."""
    urls = url_db.get_all_urls()
    return request.state.templates.TemplateResponse(
        "url_list.html",
        {"request": request, "urls": urls}
    )

@router.get("/urls/add", response_class=HTMLResponse)
async def add_url_form(request: Request):
    """Render the add URL form."""
    return request.state.templates.TemplateResponse(
        "url_form.html",
        {"request": request}
    )

@router.post("/urls/add")
async def add_url(
    request: Request,
    url: str = Form(...),
    type: str = Form(...)
):
    """Handle URL form submission."""
    try:
        url_create = URLCreate(url=url, type=type)
        url_db.add_url(url_create)
        return RedirectResponse(url="/urls", status_code=303)
    except Exception as e:
        return request.state.templates.TemplateResponse(
            "url_form.html",
            {"request": request, "error": str(e)}
        )

@router.get("/urls/{url_id}/delete")
async def delete_url_confirm(request: Request, url_id: int):
    """Render delete URL confirmation page."""
    url = url_db.get_url_by_id(url_id)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")
    
    return request.state.templates.TemplateResponse(
        "url_delete.html",
        {"request": request, "url": url}
    )

@router.post("/urls/{url_id}/delete")
async def delete_url_handle(url_id: int):
    """Handle URL deletion."""
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
            "total_items": total_items
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
            "related_items": related_items
        }
    )

@router.get("/search", response_class=HTMLResponse)
async def search_form(request: Request):
    """Render the search form."""
    return request.state.templates.TemplateResponse(
        "search.html",
        {"request": request}
    )