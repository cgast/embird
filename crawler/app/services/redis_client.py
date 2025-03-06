import json
from typing import Dict, List, Optional, Any, Union
import asyncio
import redis.asyncio as redis
import numpy as np

from app.config import settings

class RedisClient:
    """Redis client for vector operations."""
    
    _instance = None
    _redis = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
        return cls._instance
    
    async def initialize(self):
        """Initialize Redis connection and create index if needed."""
        if self._initialized:
            return
        
        # Connect to Redis with retry logic
        retry_count = 0
        max_retries = 5
        retry_delay = 2  # seconds
        
        while retry_count < max_retries:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30,
                    retry_on_timeout=True
                )
                
                await self._redis.ping()
                print("REDIS DEBUG: Connection established successfully")
                break
            except (redis.ConnectionError, redis.TimeoutError) as e:
                retry_count += 1
                print(f"Redis connection attempt {retry_count} failed: {e}")
                if retry_count >= max_retries:
                    raise
                await asyncio.sleep(retry_delay)
        
        try:
            # Check for existing indices
            try:
                indices = await self._redis.execute_command("FT._LIST")
                print(f"REDIS DEBUG: Existing indices: {indices}")
            except Exception as e:
                print(f"REDIS DEBUG: Error listing indices: {e}")
                indices = []
            
            # Try to drop existing index if it exists
            if f"{settings.REDIS_PREFIX}idx".encode() in indices or any(idx.decode() == f"{settings.REDIS_PREFIX}idx" for idx in indices if hasattr(idx, 'decode')):
                try:
                    await self._redis.execute_command("FT.DROPINDEX", f"{settings.REDIS_PREFIX}idx")
                    print(f"REDIS DEBUG: Dropped existing index {settings.REDIS_PREFIX}idx")
                except Exception as e:
                    print(f"REDIS DEBUG: Error dropping index: {e}")
            
            # Create vector index with FLAT algorithm
            try:
                schema_args = [
                    "ON", "HASH",
                    "PREFIX", "1", settings.REDIS_PREFIX,
                    "SCHEMA",
                    "embedding", "VECTOR", "FLAT", "TYPE", "FLOAT32", 
                    "DIM", str(settings.VECTOR_DIMENSIONS), 
                    "DISTANCE_METRIC", "COSINE",
                    "title", "TEXT", "SORTABLE",
                    "url", "TEXT", "SORTABLE",
                    "source_url", "TEXT", "SORTABLE"
                ]
                
                command = ["FT.CREATE", f"{settings.REDIS_PREFIX}idx"] + schema_args
                print(f"REDIS DEBUG: Executing command: {command}")
                
                result = await self._redis.execute_command(*command)
                print(f"REDIS DEBUG: Index creation result: {result}")
                self._initialized = True
                
            except Exception as e:
                print(f"REDIS DEBUG: Error creating index: {e}")
                self._initialized = True
                
        except Exception as e:
            print(f"REDIS DEBUG: Error initializing Redis: {e}")
            self._initialized = True
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._initialized = False
    
    def _validate_vector(self, embedding: Union[List[float], np.ndarray]) -> Optional[np.ndarray]:
        """Validate vector format and dimensions."""
        try:
            # Convert to numpy array if needed
            if isinstance(embedding, list):
                embedding = np.array(embedding, dtype=np.float32)
            elif not isinstance(embedding, np.ndarray):
                print(f"REDIS DEBUG: Invalid embedding type: {type(embedding)}")
                return None
                
            # Ensure float32 type
            if embedding.dtype != np.float32:
                embedding = embedding.astype(np.float32)
            
            # Validate dimensions
            if embedding.shape != (settings.VECTOR_DIMENSIONS,):
                print(f"REDIS DEBUG: Invalid embedding shape: {embedding.shape}")
                return None
            
            return embedding
            
        except Exception as e:
            print(f"REDIS DEBUG: Error validating vector: {e}")
            return None
    
    async def store_vector(self, news_id: int, embedding: Union[List[float], np.ndarray], metadata: Dict[str, Any]) -> bool:
        """Store a vector with metadata in Redis."""
        if not self._initialized:
            await self.initialize()
            
        try:
            key = f"{settings.REDIS_PREFIX}{news_id}"
            
            # Validate vector
            embedding_np = self._validate_vector(embedding)
            if embedding_np is None:
                print(f"REDIS DEBUG: Invalid embedding for key {key}")
                return False
            
            # Convert to binary
            embedding_bytes = embedding_np.tobytes()
            
            # Store in Redis
            data = {
                "title": metadata.get("title", ""),
                "url": metadata.get("url", ""),
                "source_url": metadata.get("source_url", ""),
                "embedding": embedding_bytes
            }
            
            await self._redis.hset(key, mapping=data)
            await self._redis.expire(key, settings.REDIS_TTL)
            return True
            
        except Exception as e:
            print(f"REDIS DEBUG: Error storing in Redis: {e}")
            return False
    
    async def search_vectors(self, query_vector: Union[List[float], np.ndarray], limit: int = 10, filter_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors in Redis."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Validate query vector
            query_np = self._validate_vector(query_vector)
            if query_np is None:
                print("REDIS DEBUG: Invalid query vector")
                return []
            
            # Convert to binary
            query_bytes = query_np.tobytes()
            
            # Search using Redis command
            command = [
                "FT.SEARCH", f"{settings.REDIS_PREFIX}idx",
                "*",
                "RETURN", "4", "title", "url", "source_url", "embedding",
                "LIMIT", "0", str(limit)
            ]
            
            result = await self._redis.execute_command(*command)
            
            processed_results = []
            
            if result and len(result) > 1:
                for i in range(1, len(result), 2):
                    try:
                        doc_id = int(result[i].decode().replace(f"{settings.REDIS_PREFIX}", ""))
                        values = result[i+1]
                        
                        # Extract fields
                        attrs = {}
                        vector = None
                        
                        for j in range(0, len(values), 2):
                            field = values[j].decode()
                            value = values[j+1]
                            
                            if field == "embedding":
                                # Parse binary vector
                                try:
                                    vector = np.frombuffer(value, dtype=np.float32)
                                except Exception as e:
                                    print(f"REDIS DEBUG: Error parsing vector: {e}")
                                    continue
                            else:
                                if isinstance(value, bytes):
                                    value = value.decode()
                                attrs[field] = value
                        
                        if vector is not None and vector.shape == (settings.VECTOR_DIMENSIONS,):
                            # Compute cosine similarity
                            similarity = np.dot(query_np, vector) / (np.linalg.norm(query_np) * np.linalg.norm(vector))
                            
                            processed_results.append({
                                "id": doc_id,
                                "title": attrs.get("title", ""),
                                "url": attrs.get("url", ""),
                                "source_url": attrs.get("source_url", ""),
                                "similarity": float(similarity)
                            })
                    except Exception as item_error:
                        print(f"REDIS DEBUG: Error processing search result: {item_error}")
                        continue
                
                # Sort by similarity
                processed_results.sort(key=lambda x: x["similarity"], reverse=True)
            
            return processed_results
            
        except Exception as e:
            print(f"REDIS DEBUG: Error in vector search: {e}")
            return []
    
    async def get_clusters(self, hours: int = 24, min_similarity: float = 0.6) -> Dict[int, List[Dict[str, Any]]]:
        """Generate clusters using Redis vector search."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Get all news items in Redis
            keys = await self._redis.keys(f"{settings.REDIS_PREFIX}*")
            
            # Filter out the index key
            keys = [key for key in keys if not key.decode().endswith("idx")]
            
            if not keys:
                return {}
                
            # Initialize clusters
            clusters = {}
            next_cluster_id = 0
            processed_ids = set()
            
            # Sort keys for deterministic ordering
            keys.sort()
            
            # Process each news item
            for key in keys:
                try:
                    news_id = int(key.decode().replace(settings.REDIS_PREFIX, ""))
                except ValueError:
                    continue
                
                if news_id in processed_ids:
                    continue
                
                news_data = await self._redis.hgetall(key)
                if not news_data or b"embedding" not in news_data:
                    continue
                
                try:
                    # Parse binary vector
                    vector = np.frombuffer(news_data[b"embedding"], dtype=np.float32)
                    
                    if vector.shape != (settings.VECTOR_DIMENSIONS,):
                        print(f"REDIS DEBUG: Invalid vector shape in Redis: {vector.shape}")
                        continue
                    
                    # Get similar items
                    similar_items = await self.search_vectors(vector, limit=100)
                    
                    # Filter by similarity threshold
                    similar_items = [item for item in similar_items if item["similarity"] >= min_similarity]
                    
                    if similar_items:
                        clusters[next_cluster_id] = similar_items
                        for item in similar_items:
                            processed_ids.add(item["id"])
                        next_cluster_id += 1
                        
                except Exception as e:
                    print(f"Error processing vector for item {news_id}: {e}")
                    continue
            
            return clusters
            
        except Exception as e:
            print(f"Error generating clusters in Redis: {e}")
            return {}
    
    async def delete_news(self, news_id: int) -> bool:
        """Delete a news item from Redis."""
        if not self._initialized:
            await self.initialize()
            
        try:
            key = f"{settings.REDIS_PREFIX}{news_id}"
            await self._redis.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting news from Redis: {e}")
            return False


# Singleton instance
async def get_redis_client():
    """Get Redis client instance."""
    client = RedisClient()
    await client.initialize()
    return client


# Async context manager
class RedisClientContextManager:
    """Async context manager for Redis client."""
    
    def __init__(self):
        self.client = None
        
    async def __aenter__(self):
        self.client = RedisClient()
        await self.client.initialize()
        return self.client
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # We don't close the connection because it's a singleton
        pass
