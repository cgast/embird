import json
from typing import Dict, List, Optional, Any, Union, Set
import asyncio
from datetime import datetime, timedelta
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
                
                # Check Redis modules
                try:
                    modules = await self._redis.execute_command('MODULE LIST')
                    print("REDIS DEBUG: Loaded modules:", modules)
                except Exception as e:
                    print(f"REDIS DEBUG: Error checking modules: {e}")
                
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
            
            # Only create index if it doesn't exist
            if f"{settings.REDIS_PREFIX}idx".encode() not in indices and not any(idx.decode() == f"{settings.REDIS_PREFIX}idx" for idx in indices if hasattr(idx, 'decode')):
                try:
                    # Create vector index with FLAT type
                    schema_args = [
                        "ON", "HASH",
                        "PREFIX", "1", settings.REDIS_PREFIX,
                        "SCHEMA",
                        "embedding", "VECTOR", "FLOAT32", 
                        "DIM", str(settings.VECTOR_DIMENSIONS), 
                        "DISTANCE_METRIC", "COSINE",
                        "TYPE", "FLAT",
                        "title", "TEXT", "SORTABLE",
                        "url", "TEXT", "SORTABLE",
                        "source_url", "TEXT", "SORTABLE",
                        "timestamp", "NUMERIC", "SORTABLE"
                    ]
                    
                    command = ["FT.CREATE", f"{settings.REDIS_PREFIX}idx"] + schema_args
                    print(f"REDIS DEBUG: Creating index with command: {' '.join(str(x) for x in command)}")
                    
                    result = await self._redis.execute_command(*command)
                    print(f"REDIS DEBUG: Index creation result: {result}")
                    
                    # Verify index was created
                    indices_after = await self._redis.execute_command("FT._LIST")
                    print(f"REDIS DEBUG: Indices after creation: {indices_after}")
                    
                    # Get index info
                    try:
                        info = await self._redis.execute_command("FT.INFO", f"{settings.REDIS_PREFIX}idx")
                        print(f"REDIS DEBUG: Index info: {info}")
                    except Exception as e:
                        print(f"REDIS DEBUG: Error getting index info: {e}")
                    
                except Exception as e:
                    print(f"REDIS DEBUG: Error creating index: {e}")
            else:
                print(f"REDIS DEBUG: Index {settings.REDIS_PREFIX}idx already exists")
                # Get index info
                try:
                    info = await self._redis.execute_command("FT.INFO", f"{settings.REDIS_PREFIX}idx")
                    print(f"REDIS DEBUG: Existing index info: {info}")
                except Exception as e:
                    print(f"REDIS DEBUG: Error getting existing index info: {e}")
            
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
            
            # Store in Redis with timestamp
            data = {
                "title": metadata.get("title", ""),
                "url": metadata.get("url", ""),
                "source_url": metadata.get("source_url", ""),
                "embedding": embedding_bytes,
                "timestamp": str(int(datetime.now().timestamp()))
            }
            
            await self._redis.hset(key, mapping=data)
            await self._redis.expire(key, settings.REDIS_TTL)
            return True
            
        except Exception as e:
            print(f"REDIS DEBUG: Error storing in Redis: {e}")
            return False
    
    async def search_vectors(self, query_vector: Union[List[float], np.ndarray], limit: int = 10, min_timestamp: Optional[int] = None, exclude_ids: Optional[Set[int]] = None) -> List[Dict[str, Any]]:
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
            
            # Build vector search query
            try:
                print("REDIS DEBUG: Attempting KNN search")
                # Build KNN query for Redis Stack 7.2
                if min_timestamp is not None:
                    query = f"@timestamp:[{min_timestamp} +inf] @embedding:[KNN {limit} $vec AS score]"
                else:
                    query = f"*=>[KNN {limit} @embedding $vec AS score]"
                
                result = await self._redis.execute_command(
                    "FT.SEARCH", f"{settings.REDIS_PREFIX}idx",
                    query,
                    "PARAMS", "2", "vec", query_bytes,
                    "RETURN", "6", "title", "url", "source_url", "embedding", "timestamp", "score",
                    "SORTBY", "score"
                )
                
                processed_results = []
                
                if result and len(result) > 1:
                    for i in range(1, len(result), 2):
                        try:
                            doc_id = int(result[i].decode().replace(f"{settings.REDIS_PREFIX}", ""))
                            
                            # Skip if this is in the excluded IDs
                            if exclude_ids is not None and doc_id in exclude_ids:
                                continue
                                
                            values = result[i+1]
                            attrs = {}
                            
                            for j in range(0, len(values), 2):
                                field = values[j].decode()
                                value = values[j+1]
                                
                                if isinstance(value, bytes):
                                    if field != "embedding":
                                        value = value.decode()
                                attrs[field] = value
                            
                            # Convert score to similarity
                            score = float(attrs.get("score", "1"))
                            similarity = 1 - score  # Convert distance to similarity
                            
                            processed_results.append({
                                "id": doc_id,
                                "title": attrs.get("title", ""),
                                "url": attrs.get("url", ""),
                                "source_url": attrs.get("source_url", ""),
                                "similarity": similarity,
                                "timestamp": int(attrs.get("timestamp", "0"))
                            })
                        except Exception as item_error:
                            print(f"REDIS DEBUG: Error processing search result: {item_error}")
                            continue
                    
                    # Sort by similarity
                    processed_results.sort(key=lambda x: x["similarity"], reverse=True)
                
                return processed_results
                
            except Exception as e:
                print(f"REDIS DEBUG: KNN search failed: {e}")
                return []
                
        except Exception as e:
            print(f"REDIS DEBUG: Error in vector search: {e}")
            return []
    
    async def get_clusters(self, hours: int = 24, min_similarity: float = 0.6) -> Dict[int, List[Dict[str, Any]]]:
        """Generate clusters using Redis vector search."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Calculate minimum timestamp based on hours parameter
            min_timestamp = int((datetime.now() - timedelta(hours=hours)).timestamp())
            
            # Get all news items in Redis within time window
            command = [
                "FT.SEARCH", f"{settings.REDIS_PREFIX}idx",
                f"@timestamp:[{min_timestamp} +inf]",
                "RETURN", "5", "title", "url", "source_url", "embedding", "timestamp",
                "SORTBY", "timestamp", "DESC"  # Sort by timestamp descending
            ]
            
            result = await self._redis.execute_command(*command)
            
            if not result or len(result) <= 1:
                return {}
                
            # Initialize clusters
            clusters = {}
            next_cluster_id = 0
            processed_ids = set()
            
            # Process each news item
            for i in range(1, len(result), 2):
                try:
                    doc_id = int(result[i].decode().replace(settings.REDIS_PREFIX, ""))
                    
                    # Skip if this item is already in a cluster
                    if doc_id in processed_ids:
                        continue
                        
                    values = result[i+1]
                    vector = None
                    attrs = {}
                    
                    # Extract fields
                    for j in range(0, len(values), 2):
                        field = values[j].decode()
                        value = values[j+1]
                        
                        if field == "embedding":
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
                        # Get similar items within time window, excluding all processed items
                        similar_items = await self.search_vectors(
                            vector, 
                            limit=100, 
                            min_timestamp=min_timestamp,
                            exclude_ids=processed_ids
                        )
                        
                        # Filter by similarity threshold
                        similar_items = [item for item in similar_items if item["similarity"] >= min_similarity]
                        
                        # Only create a cluster if there are similar items
                        if similar_items:
                            # Add the current item as the first item (center) of the cluster
                            cluster_items = [{
                                "id": doc_id,
                                "title": attrs.get("title", ""),
                                "url": attrs.get("url", ""),
                                "source_url": attrs.get("source_url", ""),
                                "similarity": 1.0,  # This is the center item
                                "timestamp": int(attrs.get("timestamp", "0"))
                            }]
                            
                            # Add similar items
                            cluster_items.extend(similar_items)
                            
                            clusters[next_cluster_id] = cluster_items
                            
                            # Mark all items in cluster as processed
                            processed_ids.add(doc_id)
                            for item in similar_items:
                                processed_ids.add(item["id"])
                                
                            next_cluster_id += 1
                            
                except Exception as e:
                    print(f"Error processing vector for item {doc_id}: {e}")
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
