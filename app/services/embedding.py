import cohere
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from pgvector.sqlalchemy import Vector

from app.config import settings
from app.models.news import NewsItem
from app.models.topic import Topic
from app.services.faiss_service import get_faiss_service
from app.services.visualization import update_visualizations

logger = logging.getLogger(__name__)

# Set up PostgreSQL connection
pg_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False
)
AsyncSessionLocal = sessionmaker(pg_engine, expire_on_commit=False, class_=AsyncSession)

class EmbeddingService:
    """Service for generating embeddings and managing vector operations."""

    def __init__(self, api_key: str = None):
        """Initialize the embedding service."""
        self.api_key = api_key or settings.COHERE_API_KEY
        if not self.api_key:
            raise ValueError("Cohere API key is required")

        self.client = cohere.Client(self.api_key)
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self.max_text_length = 2048
        self.running = False

    def preprocess_text(self, text: str) -> str:
        """Preprocess text before generating embedding."""
        text = ' '.join(text.split())
        if len(text) > self.max_text_length:
            text = text[:self.max_text_length] + "..."
        return text

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for a text with retries."""
        if not text:
            logger.warning("Empty text provided for embedding")
            return None

        text = self.preprocess_text(text)

        for attempt in range(self.max_retries):
            try:
                response = self.client.embed(
                    texts=[text],
                    model="embed-english-v3.0",
                    input_type="search_document",
                    embedding_types=["float"]
                )

                if response.response_type == "embeddings_floats":
                    return response.embeddings[0]
                else:
                    embeddings = response.embeddings.float_
                    return embeddings[0]

            except Exception as e:
                logger.warning(f"Cohere API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if "rate" in str(e).lower():
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                elif attempt == self.max_retries - 1:
                    logger.error(f"Failed to generate embedding after {self.max_retries} attempts: {e}")
                    return None
                else:
                    await asyncio.sleep(self.retry_delay)

    def _validate_vector(self, vector_data) -> Optional[np.ndarray]:
        """Validate vector from database."""
        try:
            if isinstance(vector_data, Vector):
                vector = np.array(vector_data, dtype=np.float32)
            elif isinstance(vector_data, (list, np.ndarray)):
                vector = np.array(vector_data, dtype=np.float32)
            else:
                logger.error(f"Invalid vector type from database: {type(vector_data)}")
                return None

            if vector.shape != (settings.VECTOR_DIMENSIONS,):
                logger.error(f"Invalid vector dimensions from database: {vector.shape}")
                return None

            return vector

        except Exception as e:
            logger.error(f"Error validating vector from database: {e}")
            return None

    async def update_faiss_index(self):
        """Update FAISS index with recent vectors from PostgreSQL for all topics."""
        try:
            async with AsyncSessionLocal() as session:
                faiss_service = get_faiss_service()

                # Get all topics
                result = await session.execute(select(Topic))
                topics = result.scalars().all()

                for topic in topics:
                    await faiss_service.update_index(session, settings.VISUALIZATION_TIME_RANGE, topic_id=topic.id)

                logger.info("Successfully updated FAISS indexes for all topics")

        except Exception as e:
            logger.error(f"Error updating FAISS index: {str(e)}")

    async def run_background_tasks(self):
        """Run background tasks continuously."""
        self.running = True

        try:
            while self.running:
                logger.info("Running embedding service background tasks")

                # Update FAISS index for all topics
                await self.update_faiss_index()

                # Update pre-generated visualizations for all topics
                async with AsyncSessionLocal() as session:
                    result = await session.execute(select(Topic))
                    topics = result.scalars().all()

                for topic in topics:
                    try:
                        async with AsyncSessionLocal() as session:
                            await update_visualizations(session, topic_id=topic.id, language=topic.language or 'en')
                    except Exception as e:
                        logger.error(f"Error updating visualizations for topic {topic.id}: {str(e)}")

                logger.info(f"Background tasks completed, sleeping for {settings.FAISS_UPDATE_INTERVAL} seconds")
                await asyncio.sleep(settings.FAISS_UPDATE_INTERVAL)

        except Exception as e:
            logger.error(f"Error in background tasks: {str(e)}")
            self.running = False

    async def stop_background_tasks(self):
        """Stop background tasks."""
        self.running = False

# Create a global instance
embedding_service = EmbeddingService()

async def start_background_tasks():
    """Start the background tasks."""
    await embedding_service.run_background_tasks()

# Function to be called during application shutdown
async def stop_background_tasks():
    """Stop the background tasks."""
    await embedding_service.stop_background_tasks()

# FastAPI dependency injection function
def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    return embedding_service
