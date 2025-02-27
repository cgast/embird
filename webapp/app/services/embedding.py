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
        except Exception as e:
            logging.error(f"Error initializing Cohere client: {e}")
            raise ValueError(f"Failed to initialize Cohere client: {str(e)}")
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for a text."""
        if not text or not text.strip():
            return None
            
        try:
            response = self.client.embed(
                texts=[text],
                model="embed-english-v3.0",
                input_type="search_document",
                embedding_types=["float"]
            )
            
            if response.response_type == "embeddings_floats":
                return response.embeddings[0]
            else:  # embeddings_by_type
                return response.embeddings.float_[0]
                
        except Exception as e:
            logging.error(f"Error generating embedding: {e}")
            raise ValueError(f"Failed to generate embedding: {str(e)}")


_embedding_service = None

def get_embedding_service() -> EmbeddingService:
    """Get embedding service singleton."""
    global _embedding_service
    
    if _embedding_service is None:
        try:
            _embedding_service = EmbeddingService()
        except Exception as e:
            logging.error(f"Failed to create EmbeddingService: {e}")
            raise ValueError(f"Failed to initialize embedding service: {str(e)}")
    
    return _embedding_service
