"""Main FastAPI application."""
import os
import logging
import asyncio
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime

from app.routes import web, api
from app.services.crawler import start_crawler, stop_crawler
from app.services.faiss_service import get_faiss_service
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG
)

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Initialize templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Add current_year to template globals
templates.env.globals['current_year'] = lambda: datetime.now().year

# Include routers
app.include_router(web.router)
app.include_router(api.router, prefix="/api")

@app.middleware("http")
async def templates_middleware(request: Request, call_next):
    """Add templates to request state."""
    request.state.templates = templates
    response = await call_next(request)
    return response

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add process time header to responses."""
    import time
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    try:
        # Initialize FAISS service
        faiss_service = get_faiss_service()
        logger.info("FAISS service initialized")
        
        # Start crawler if this is the crawler service
        if os.environ.get("SERVICE_TYPE") == "crawler":
            # Create a new event loop for the crawler
            loop = asyncio.get_event_loop()
            loop.create_task(start_crawler())
            logger.info("Crawler service started")
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        # Stop crawler if running
        if os.environ.get("SERVICE_TYPE") == "crawler":
            await stop_crawler()
            logger.info("Crawler service stopped")
            
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# If this is the crawler service, run it directly
if __name__ == "__main__" and os.environ.get("SERVICE_TYPE") == "crawler":
    loop = asyncio.get_event_loop()
    loop.create_task(start_crawler())
    loop.run_forever()
