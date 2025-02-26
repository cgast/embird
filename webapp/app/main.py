import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.routes import api, web
from app.services.db import init_db

# Create FastAPI app
app = FastAPI(title=settings.APP_NAME)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# Setup templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)

# Include routers
app.include_router(api.router, prefix="/api")
app.include_router(web.router)

@app.on_event("startup")
async def startup_db_client():
    """Initialize database on startup."""
    await init_db()

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