import os
import sqlite3
import logging
from sqlalchemy import create_engine, MetaData, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

from app.config import settings
from app.models.news import Base as NewsBase
from app.models.topic import Topic
from app.models.url import URLDatabase

logger = logging.getLogger(__name__)

# PostgreSQL async engine
async_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.DEBUG
)
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# SQLite database for URL storage
url_db = URLDatabase(settings.SQLITE_PATH)

async def init_db():
    """Initialize the database with required tables."""
    async with async_engine.begin() as conn:
        # Create all tables if they don't exist
        await conn.run_sync(NewsBase.metadata.create_all)

async def ensure_default_topic(db: AsyncSession) -> Topic:
    """Ensure the default topic exists, creating it if needed. Returns the topic."""
    result = await db.execute(
        select(Topic).filter(Topic.slug == settings.DEFAULT_TOPIC_SLUG)
    )
    topic = result.scalars().first()
    if not topic:
        topic = Topic(
            name=settings.DEFAULT_TOPIC_NAME,
            slug=settings.DEFAULT_TOPIC_SLUG,
            description="Default topic"
        )
        db.add(topic)
        await db.commit()
        await db.refresh(topic)
        logger.info(f"Created default topic: {topic.name} ({topic.slug})")
    return topic

async def get_all_topics(db: AsyncSession):
    """Get all topics."""
    result = await db.execute(select(Topic).order_by(Topic.name))
    return result.scalars().all()

@asynccontextmanager
async def get_db_context():
    """Context manager for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_db():
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except:
            await session.rollback()
            raise
        finally:
            await session.close()
