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
    """Initialize the database with required tables and run migrations."""
    async with async_engine.begin() as conn:
        # Create all tables if they don't exist
        await conn.run_sync(NewsBase.metadata.create_all)

        # Run migrations for existing databases that predate multi-topic support
        from sqlalchemy import text
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS topics (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            INSERT INTO topics (name, slug, description)
            VALUES ('Default', 'default', 'Default topic')
            ON CONFLICT (slug) DO NOTHING
        """))

        # Add language to topics if missing
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='topics' AND column_name='language'
        """))
        if not result.fetchone():
            await conn.execute(text("ALTER TABLE topics ADD COLUMN language VARCHAR NOT NULL DEFAULT 'en'"))

        # Add topic_id to news if missing
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='news' AND column_name='topic_id'
        """))
        if not result.fetchone():
            await conn.execute(text("ALTER TABLE news ADD COLUMN topic_id INTEGER NOT NULL DEFAULT 1"))
            await conn.execute(text("""
                ALTER TABLE news ADD CONSTRAINT fk_news_topic
                FOREIGN KEY (topic_id) REFERENCES topics(id)
            """))

        # Add topic_id to news_clusters if missing
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='news_clusters' AND column_name='topic_id'
        """))
        if not result.fetchone():
            await conn.execute(text("ALTER TABLE news_clusters ADD COLUMN topic_id INTEGER NOT NULL DEFAULT 1"))
            await conn.execute(text("""
                ALTER TABLE news_clusters ADD CONSTRAINT fk_news_clusters_topic
                FOREIGN KEY (topic_id) REFERENCES topics(id)
            """))

        # Ensure unique constraint uix_topic_hours_similarity exists on news_clusters
        result = await conn.execute(text("""
            SELECT 1 FROM pg_constraint WHERE conname = 'uix_topic_hours_similarity'
        """))
        if not result.fetchone():
            # Drop old constraints that don't include topic_id
            for old_name in ('news_clusters_hours_min_similarity_key', 'uix_hours_similarity'):
                await conn.execute(text(f"""
                    DO $$ BEGIN
                        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{old_name}') THEN
                            ALTER TABLE news_clusters DROP CONSTRAINT {old_name};
                        END IF;
                    END $$
                """))
            await conn.execute(text("""
                ALTER TABLE news_clusters
                ADD CONSTRAINT uix_topic_hours_similarity UNIQUE (topic_id, hours, min_similarity)
            """))

        # Ensure unique constraint uix_umap_topic_hours_similarity exists on news_umap
        result = await conn.execute(text("""
            SELECT 1 FROM pg_constraint WHERE conname = 'uix_umap_topic_hours_similarity'
        """))
        if not result.fetchone():
            # Drop old constraints that don't include topic_id
            for old_name in ('news_umap_hours_key', 'uix_umap_hours_similarity'):
                await conn.execute(text(f"""
                    DO $$ BEGIN
                        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{old_name}') THEN
                            ALTER TABLE news_umap DROP CONSTRAINT {old_name};
                        END IF;
                    END $$
                """))
            await conn.execute(text("""
                ALTER TABLE news_umap
                ADD CONSTRAINT uix_umap_topic_hours_similarity UNIQUE (topic_id, hours, min_similarity)
            """))

        # Add topic_id to news_umap if missing
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='news_umap' AND column_name='topic_id'
        """))
        if not result.fetchone():
            await conn.execute(text("ALTER TABLE news_umap ADD COLUMN topic_id INTEGER NOT NULL DEFAULT 1"))
            await conn.execute(text("""
                ALTER TABLE news_umap ADD CONSTRAINT fk_news_umap_topic
                FOREIGN KEY (topic_id) REFERENCES topics(id)
            """))

        # Add min_similarity to news_umap if missing
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='news_umap' AND column_name='min_similarity'
        """))
        if not result.fetchone():
            await conn.execute(text("ALTER TABLE news_umap ADD COLUMN min_similarity FLOAT NOT NULL DEFAULT 0.6"))

        # Add topic_id to preference_vectors if missing
        result = await conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name='preference_vectors' AND column_name='topic_id'
        """))
        if not result.fetchone():
            await conn.execute(text("ALTER TABLE preference_vectors ADD COLUMN topic_id INTEGER NOT NULL DEFAULT 1"))
            await conn.execute(text("""
                ALTER TABLE preference_vectors ADD CONSTRAINT fk_preference_vectors_topic
                FOREIGN KEY (topic_id) REFERENCES topics(id)
            """))

    logger.info("Database migrations complete")

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
