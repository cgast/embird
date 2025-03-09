import cohere
import time
import logging
from typing import List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating embeddings using Cohere API."""
    
    def __init__(self, api_key: str = None):
        """Initialize the embedding service."""
        self.api_key = api_key or settings.COHERE_API_KEY
        if not self.api_key:
            raise ValueError("Cohere API key is required")
        
        self.client = cohere.Client(self.api_key)
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self.max_text_length = 2048  # Cohere's token limit is higher, but we'll be conservative
    
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
