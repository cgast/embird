import cohere
from typing import List, Optional
import logging
from app.config import settings

class EmbeddingService:
    """Service for generating embeddings using Cohere API."""
    
    def __init__(self, api_key: str = None):
        """Initialize the embedding service."""
        self.api_key = api_key or settings.COHERE_API_KEY
        if not self.api_key:
            raise ValueError("Cohere API key is required")
        
        try:
            self.client = cohere.Client(self.api_key)
            logging.info("Cohere client initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing Cohere client: {e}")
            raise
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text."""
        if not text or not text.strip():
            logging.error("Empty text provided for embedding")
            return None
            
        try:
            # Use async version if available in your Cohere client
            # For now, this is a synchronous call
            response = self.client.embed(
                texts=[text],
                model="embed-english-v3.0",  # Using v3.0 model which provides 1024-dimensional embeddings
                input_type="search_document",  # Required for v3 models
                embedding_types=["float"]  # Get float embeddings for maximum precision
            )
            
            # Log successful embedding generation
            logging.info(f"Successfully generated embedding for text: {text[:50]}...")
            
            # Handle different response types
            if response.response_type == "embeddings_floats":
                return response.embeddings[0]
            else:  # embeddings_by_type
                embeddings = response.embeddings.float_  # This is already a list of embeddings
                return embeddings[0]
                
        except Exception as e:
            logging.error(f"Error generating embedding: {e}")
            # Re-raise with more context
            raise Exception(f"Failed to generate embedding: {str(e)}")


def get_embedding_service() -> EmbeddingService:
    """Get embedding service singleton."""
    try:
        return EmbeddingService()
    except Exception as e:
        logging.error(f"Failed to create EmbeddingService: {e}")
        raise
