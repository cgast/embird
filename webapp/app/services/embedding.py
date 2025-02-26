import cohere
from typing import List, Optional
from app.config import settings

class EmbeddingService:
    """Service for generating embeddings using Cohere API."""
    
    def __init__(self, api_key: str = None):
        """Initialize the embedding service."""
        self.api_key = api_key or settings.COHERE_API_KEY
        if not self.api_key:
            raise ValueError("Cohere API key is required")
        
        self.client = cohere.Client(self.api_key)
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text."""
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
            print(f"Error generating embedding: {e}")
            return None


def get_embedding_service() -> EmbeddingService:
    """Get embedding service singleton."""
    return EmbeddingService()
