import os
import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select, update, func

from app.config import settings
from app.routes import api, web
from app.services.db import init_db, get_db
from app.services.crawler import Crawler
from app.models.url import URLDatabase
from app.services.visualization import generate_clusters
from shared.models.news import NewsClusters

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Initialize URL database for crawler
url_db = URLDatabase(settings.SQLITE_PATH)

class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        for header in ['x-forwarded-proto', 'x-forwarded-for', 'x-forwarded-host']:
            if header in request.headers:
                os.environ[header.upper().replace('-', '_')] = request.headers[header]
        response = await call_next(request)
        return response

# Crawler Functions
async def update_clusters(db):
    """Update pre-generated clusters in the database."""
    logger.info("Generating news clusters")
    try:
        clusters_data = await generate_clusters(db)
        
        stmt = select(NewsClusters).filter(
            NewsClusters.hours == 24,
            NewsClusters.min_similarity == 0.2
        )
        result = await db.execute(stmt)
        existing_clusters = result.scalar_one_or_none()
        
        if existing_clusters:
            stmt = update(NewsClusters).where(
                NewsClusters.hours == 24,
                NewsClusters.min_similarity == 0.2
            ).values(
                clusters=clusters_data,
                created_at=func.now()
            )
            await db.execute(stmt)
        else:
            new_clusters = NewsClusters(
                hours=24,
                min_similarity=0.2,
                clusters=clusters_data
            )
            db.add(new_clusters)
        
        await db.commit()
        logger.info("Successfully updated news clusters")
    except Exception as e:
        logger.error(f"Error generating clusters: {str(e)}")
        await db.rollback()

async def crawl_all_urls():
    """Crawl all URLs in the database."""
    logger.info("Starting crawl job")
    
    crawler = Crawler(url_db=url_db)
    urls = url_db.get_urls_to_crawl()
    
    if not urls:
        logger.info("No URLs to crawl")
        return
    
    logger.info(f"Found {len(urls)} URLs to crawl")
    
    for url_item in urls:
        try:
            logger.info(f"Crawling URL: {url_item.url}")
            await crawler.crawl_url(url_item)
            url_db.update_url_crawl_time(url_item.id)
            logger.info(f"Successfully crawled URL: {url_item.url}")
        except Exception as e:
            logger.error(f"Error crawling URL {url_item.url}: {str(e)}")
    
    logger.info("Crawl job completed")
    
    async with get_db() as db:
        await update_clusters(db)

async def crawler_main():
    """Main function for crawler service."""
    logger.info("Starting news-suck crawler service")
    
    while True:
        await crawl_all_urls()
        await asyncio.sleep(settings.CRAWLER_INTERVAL)

# Web App Setup
app = FastAPI(title=settings.APP_NAME)

# Add security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(ProxyHeadersMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Setup templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)
templates.env.globals["current_year"] = lambda: datetime.now().year

# Include routers
app.include_router(api.router, prefix="/api")
app.include_router(web.router)

@app.on_event("startup")
async def startup_db_client():
    """Initialize database on startup."""
    await init_db()
    
    # Start crawler if running in crawler mode
    if os.getenv("SERVICE_TYPE") == "crawler":
        asyncio.create_task(crawler_main())

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# Make templates available in request
@app.middleware("http")
async def add_templates_to_request(request: Request, call_next):
    request.state.templates = templates
    response = await call_next(request)
    return response

# Add response headers for proxy
@app.middleware("http")
async def add_proxy_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

if __name__ == "__main__":
    if os.getenv("SERVICE_TYPE") == "crawler":
        asyncio.run(crawler_main())
