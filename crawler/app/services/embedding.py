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
                model="embed-english-v3.0",  # or your preferred model
                input_type="search_document"
            )
            
            # Return the embedding vector
            return response.embeddings[0]
        except Exception as e:
            # Log the error and return None
            print(f"Error generating embedding: {e}")
            return None