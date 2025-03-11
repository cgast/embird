import cohere
import time
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
        self.max_text_length = 2048  # Cohere's token limit is higher, but we'll be conservative
        self.running = False
        
    def preprocess_text(self, text: str) -> str:
        """Preprocess text before generating embedding."""
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Truncate if too long
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
                # Use async version if available in your Cohere client
                # For now, this is a synchronous call
                response = self.client.embed(
                    texts=[text],
                    model="embed-english-v3.0",  # Using v3.0 model which provides 1024-dimensional embeddings
                    input_type="search_document",  # Required for v3 models
                    embedding_types=["float"]  # Get float embeddings for maximum precision
                )
                
                # Handle different response types
                if response.response_type == "embeddings_floats":
                    return response.embeddings[0]
                else:  # embeddings_by_type
                    embeddings = response.embeddings.float_  # This is already a list of embeddings
                    return embeddings[0]
                
            except Exception as e:
                logger.warning(f"Cohere API error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if "rate" in str(e).lower():
                    # Rate limit hit, wait longer
                    time.sleep(self.retry_delay * (attempt + 1))
                elif attempt == self.max_retries - 1:
                    # Last attempt failed
                    logger.error(f"Failed to generate embedding after {self.max_retries} attempts: {e}")
                    return None
                else:
                    # Other error, wait standard delay
                    time.sleep(self.retry_delay)

    def _validate_vector(self, vector_data) -> Optional[np.ndarray]:
        """Validate vector from database."""
        try:
            # Handle pgvector data
            if isinstance(vector_data, Vector):
                vector = np.array(vector_data, dtype=np.float32)
            # Handle array data
            elif isinstance(vector_data, (list, np.ndarray)):
                vector = np.array(vector_data, dtype=np.float32)
            else:
                logger.error(f"Invalid vector type from database: {type(vector_data)}")
                return None

            # Validate dimensions
            if vector.shape != (settings.VECTOR_DIMENSIONS,):
                logger.error(f"Invalid vector dimensions from database: {vector.shape}")
                return None

            return vector

        except Exception as e:
            logger.error(f"Error validating vector from database: {e}")
            return None

    async def update_faiss_index(self):
        """Update FAISS index with recent vectors from PostgreSQL."""
        try:
            async with AsyncSessionLocal() as session:
                # Get FAISS service
                faiss_service = get_faiss_service()
                
                # Update FAISS index with recent vectors
                await faiss_service.update_index(session, settings.VISUALIZATION_TIME_RANGE)
                
                logger.info("Successfully updated FAISS index")
                
        except Exception as e:
            logger.error(f"Error updating FAISS index: {str(e)}")

    async def run_background_tasks(self):
        """Run background tasks continuously."""
        self.running = True
        
        try:
            while self.running:
                logger.info("Running embedding service background tasks")
                
                # Update FAISS index
                await self.update_faiss_index()
                
                # Update pre-generated visualizations
                async with AsyncSessionLocal() as session:
                    await update_visualizations(session)
                
                # Sleep for a while before next cycle
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
