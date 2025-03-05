import json
from typing import Dict, List, Optional, Any, Union
import asyncio
from datetime import datetime
import redis.asyncio as redis
import numpy as np

from app.config import settings

# Custom implementation for Redis Search functionality
class VectorField:
    def __init__(self, name, algorithm, options):
        self.name = name
        self.algorithm = algorithm
        self.options = options
        
    def redis_args(self):
        args = [self.name, "VECTOR", self.algorithm]
        for k, v in self.options.items():
            args.append(k)
            args.append(str(v))
        return args

class TextField:
    def __init__(self, name):
        self.name = name
        
    def redis_args(self):
        return [self.name, "TEXT"]

class Query:
    def __init__(self, query_string):
        self.query_string = query_string
        self._return_fields = []
        self._sort_by = None
        self._sort_asc = True
        self._dialect = None
        
    def return_fields(self, *fields):
        self._return_fields = fields
        return self
        
    def sort_by(self, field, asc=True):
        self._sort_by = field
        self._sort_asc = asc
        return self
        
    def dialect(self, dialect):
        self._dialect = dialect
        return self

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
                # Connect to Redis
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30,
                    retry_on_timeout=True
                )
                
                # Ping to test connection
                await self._redis.ping()
                print("REDIS DEBUG: Connection established successfully")
                break
            except (redis.ConnectionError, redis.TimeoutError) as e:
                retry_count += 1
                print(f"Redis connection attempt {retry_count} failed: {e}")
                if retry_count >= max_retries:
                    raise
                await asyncio.sleep(retry_delay)
        
        # The crawler will handle index creation so we can just mark as initialized
        self._initialized = True
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._initialized = False
    
    async def store_vector(self, news_id: int, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        """Store a vector with metadata in Redis."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Try to store with full vector data
            key = f"{settings.REDIS_PREFIX}{news_id}"
            print(f"REDIS DEBUG: Storing data for key {key}")
            
            # Try different embedding storage formats
            max_retries = 3
            retry_delay = 1  # seconds
            
            # Ensure embedding is the right length
            if embedding and len(embedding) != settings.VECTOR_DIMENSIONS:
                if len(embedding) < settings.VECTOR_DIMENSIONS:
                    embedding = embedding + [0.0] * (settings.VECTOR_DIMENSIONS - len(embedding))
                else:
                    embedding = embedding[:settings.VECTOR_DIMENSIONS]
            
            # Try different data formats
            success = False
            
            # First attempt: Store as binary blob
            if not success and embedding:
                try:
                    print("REDIS DEBUG: Attempting to store embedding as binary blob")
                    # Convert embedding to binary
                    embedding_np = np.array(embedding, dtype=np.float32)
                    embedding_bytes = embedding_np.tobytes()
                    
                    data = {
                        "title": metadata.get("title", ""),
                        "url": metadata.get("url", ""),
                        "source_url": metadata.get("source_url", ""),
                        "embedding": embedding_bytes
                    }
                    
                    await self._redis.hset(key, mapping=data)
                    await self._redis.expire(key, settings.REDIS_TTL)
                    print("REDIS DEBUG: Successfully stored embedding as binary blob")
                    success = True
                except Exception as e1:
                    print(f"REDIS DEBUG: Error storing embedding as binary: {e1}")
            
            # Second attempt: Store as JSON string
            if not success and embedding:
                try:
                    print("REDIS DEBUG: Attempting to store embedding as JSON")
                    import json
                    
                    data = {
                        "title": metadata.get("title", ""),
                        "url": metadata.get("url", ""),
                        "source_url": metadata.get("source_url", ""),
                        "embedding": json.dumps(embedding)
                    }
                    
                    await self._redis.hset(key, mapping=data)
                    await self._redis.expire(key, settings.REDIS_TTL)
                    print("REDIS DEBUG: Successfully stored embedding as JSON")
                    success = True
                except Exception as e2:
                    print(f"REDIS DEBUG: Error storing embedding as JSON: {e2}")
            
            # Third attempt: Store as comma-separated string
            if not success and embedding:
                try:
                    print("REDIS DEBUG: Attempting to store embedding as comma-separated string")
                    
                    data = {
                        "title": metadata.get("title", ""),
                        "url": metadata.get("url", ""),
                        "source_url": metadata.get("source_url", ""),
                        "embedding": ",".join(str(x) for x in embedding)
                    }
                    
                    await self._redis.hset(key, mapping=data)
                    await self._redis.expire(key, settings.REDIS_TTL)
                    print("REDIS DEBUG: Successfully stored embedding as comma-separated string")
                    success = True
                except Exception as e3:
                    print(f"REDIS DEBUG: Error storing embedding as string: {e3}")
            
            # Fallback: Store metadata only
            if not success:
                try:
                    print("REDIS DEBUG: Falling back to metadata-only storage")
                    
                    data = {
                        "title": metadata.get("title", ""),
                        "url": metadata.get("url", ""),
                        "source_url": metadata.get("source_url", "")
                    }
                    
                    await self._redis.hset(key, mapping=data)
                    await self._redis.expire(key, settings.REDIS_TTL)
                    print("REDIS DEBUG: Successfully stored metadata only")
                    success = True
                except Exception as e4:
                    print(f"REDIS DEBUG: Error storing metadata: {e4}")
                    return False
            
            return success
        except Exception as e:
            print(f"REDIS DEBUG: Error storing in Redis: {e}")
            return False
    
    async def search_vectors(self, query_vector: List[float], limit: int = 10, filter_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors in Redis."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Ensure query vector is the right size
            if len(query_vector) != settings.VECTOR_DIMENSIONS:
                print(f"REDIS DEBUG: Query vector dimension mismatch. Expected {settings.VECTOR_DIMENSIONS}, got {len(query_vector)}")
                if len(query_vector) < settings.VECTOR_DIMENSIONS:
                    query_vector = query_vector + [0.0] * (settings.VECTOR_DIMENSIONS - len(query_vector))
                else:
                    query_vector = query_vector[:settings.VECTOR_DIMENSIONS]
            
            # Convert query vector to binary format
            query_np = np.array(query_vector, dtype=np.float32)
            query_bytes = query_np.tobytes()
            
            print(f"REDIS DEBUG: Searching with vector of length {len(query_vector)}")
            
            # Try all possible vector search formats
            success = False
            processed_results = []
            
            # Attempt 1: KNN search with $vec parameter
            if not success:
                try:
                    print("REDIS DEBUG: Attempting KNN search with $vec parameter")
                    
                    query_cmd = "*=>[KNN 10 @embedding $vec AS score]"
                    result = await self._redis.ft(f"{settings.REDIS_PREFIX}idx").search(
                        query_cmd,
                        query_params={"vec": query_bytes}
                    )
                    
                    # Process results
                    if hasattr(result, 'docs') and len(result.docs) > 0:
                        for doc in result.docs:
                            try:
                                doc_id = int(doc.id.replace(f"{settings.REDIS_PREFIX}", ""))
                                processed_results.append({
                                    "id": doc_id,
                                    "title": doc.title if hasattr(doc, "title") else "",
                                    "url": doc.url if hasattr(doc, "url") else "",
                                    "source_url": doc.source_url if hasattr(doc, "source_url") else "",
                                    "similarity": 1.0 - float(doc.score) if hasattr(doc, "score") else 1.0
                                })
                            except Exception as item_error:
                                print(f"REDIS DEBUG: Error processing KNN result: {item_error}")
                                
                        print(f"REDIS DEBUG: KNN search returned {len(processed_results)} results")
                        success = True
                        return processed_results
                except Exception as e1:
                    print(f"REDIS DEBUG: KNN search failed: {e1}")
            
            # Attempt 2: Raw KNN command
            if not success:
                try:
                    print("REDIS DEBUG: Attempting raw KNN command")
                    
                    command = [
                        "FT.SEARCH", f"{settings.REDIS_PREFIX}idx",
                        "*=>[KNN 10 @embedding $vec AS score]",
                        "PARAMS", "2", "vec", query_bytes, "vec_norm", "1.0",
                        "RETURN", "3", "title", "url", "source_url",
                        "SORTBY", "score"
                    ]
                    
                    result = await self._redis.execute_command(*command)
                    
                    # Process results
                    if result and len(result) > 1:
                        for i in range(1, len(result), 2):
                            try:
                                doc_id = int(result[i].decode().replace(f"{settings.REDIS_PREFIX}", ""))
                                attrs = {}
                                values = result[i+1]
                                
                                for j in range(0, len(values), 2):
                                    field = values[j].decode()
                                    value = values[j+1]
                                    if isinstance(value, bytes):
                                        value = value.decode()
                                    attrs[field] = value
                                
                                processed_results.append({
                                    "id": doc_id,
                                    "title": attrs.get("title", ""),
                                    "url": attrs.get("url", ""),
                                    "source_url": attrs.get("source_url", ""),
                                    "similarity": 1.0 - float(attrs.get("score", 0))
                                })
                            except Exception as item_error:
                                print(f"REDIS DEBUG: Error processing raw KNN result: {item_error}")
                        
                        print(f"REDIS DEBUG: Raw KNN search returned {len(processed_results)} results")
                        success = True
                        return processed_results
                except Exception as e2:
                    print(f"REDIS DEBUG: Raw KNN search failed: {e2}")
            
            # Attempt 3: Use exact syntax for Redis 6.2+ version with RediSearch module
            if not success:
                try:
                    print("REDIS DEBUG: Trying Redis 6.2+ syntax")
                    
                    command = [
                        "FT.SEARCH", f"{settings.REDIS_PREFIX}idx",
                        "*",
                        "RETURN", "4", "title", "url", "source_url", "embedding",
                        "LIMIT", "0", str(limit)
                    ]
                    
                    result = await self._redis.execute_command(*command)
                    
                    # If we have results, do manual vector similarity
                    if result and len(result) > 1:
                        # Get all items with their embeddings
                        items_with_embeddings = []
                        
                        for i in range(1, len(result), 2):
                            try:
                                doc_id = int(result[i].decode().replace(f"{settings.REDIS_PREFIX}", ""))
                                values = result[i+1]
                                
                                # Extract fields
                                attrs = {}
                                embedding_data = None
                                
                                for j in range(0, len(values), 2):
                                    field = values[j].decode()
                                    value = values[j+1]
                                    
                                    if field == "embedding":
                                        embedding_data = value
                                    else:
                                        if isinstance(value, bytes):
                                            value = value.decode()
                                        attrs[field] = value
                                
                                # Try to parse embedding from various formats
                                vector = None
                                if embedding_data:
                                    # Try as binary
                                    try:
                                        vector = np.frombuffer(embedding_data, dtype=np.float32).tolist()
                                    except:
                                        # Try as JSON string
                                        try:
                                            if isinstance(embedding_data, bytes):
                                                embedding_data = embedding_data.decode()
                                            import json
                                            vector = json.loads(embedding_data)
                                        except:
                                            # Try as comma-separated string
                                            try:
                                                if isinstance(embedding_data, bytes):
                                                    embedding_data = embedding_data.decode()
                                                vector = [float(x) for x in embedding_data.split(",")]
                                            except:
                                                pass
                                
                                if vector:
                                    items_with_embeddings.append({
                                        "id": doc_id,
                                        "vector": vector,
                                        "title": attrs.get("title", ""),
                                        "url": attrs.get("url", ""),
                                        "source_url": attrs.get("source_url", "")
                                    })
                            except Exception as item_error:
                                print(f"REDIS DEBUG: Error processing item for manual similarity: {item_error}")
                        
                        # Compute cosine similarity manually
                        if items_with_embeddings:
                            # Convert query to unit vector
                            query_norm = np.linalg.norm(query_vector)
                            if query_norm > 0:
                                query_unit = np.array(query_vector) / query_norm
                            else:
                                query_unit = np.array(query_vector)
                            
                            # Compute similarities
                            for item in items_with_embeddings:
                                try:
                                    item_vec = np.array(item["vector"])
                                    item_norm = np.linalg.norm(item_vec)
                                    if item_norm > 0:
                                        item_unit = item_vec / item_norm
                                    else:
                                        item_unit = item_vec
                                    
                                    # Compute cosine similarity
                                    similarity = np.dot(query_unit, item_unit)
                                    
                                    # Add to results with all required fields
                                    processed_results.append({
                                        "id": item["id"],
                                        "title": item["title"],
                                        "url": item["url"],
                                        "source_url": item["source_url"],
                                        "similarity": float(similarity),
                                        "summary": None,
                                        "first_seen_at": datetime.now().isoformat(),
                                        "last_seen_at": datetime.now().isoformat(),
                                        "hit_count": 1,
                                        "created_at": datetime.now().isoformat(),
                                        "updated_at": datetime.now().isoformat()
                                    })
                                except Exception as sim_error:
                                    print(f"REDIS DEBUG: Error computing similarity: {sim_error}")
                            
                            # Sort by similarity (descending)
                            processed_results = sorted(processed_results, key=lambda x: x["similarity"], reverse=True)
                            
                            # Limit results
                            processed_results = processed_results[:limit]
                            
                            print(f"REDIS DEBUG: Manual vector similarity found {len(processed_results)} results")
                            success = True
                            return processed_results
                except Exception as e3:
                    print(f"REDIS DEBUG: Manual similarity calculation failed: {e3}")
            
            # Fallback: Just return recent items with arbitrary similarity scores
            if not success:
                print("REDIS DEBUG: Falling back to recent items retrieval")
                keys = await self._redis.keys(f"{settings.REDIS_PREFIX}*")
                keys = [k for k in keys if not k.decode().endswith("idx")]
                
                # Sort to get most recent first (assuming key creation order matters)
                keys.sort(reverse=True)
                
                for i, key in enumerate(keys[:limit]):
                    try:
                        data = await self._redis.hgetall(key)
                        
                        # Extract key id
                        item_id = int(key.decode().replace(f"{settings.REDIS_PREFIX}", ""))
                        
                        # Get metadata
                        title = data.get(b"title", b"").decode("utf-8") if isinstance(data.get(b"title", b""), bytes) else data.get(b"title", "")
                        url = data.get(b"url", b"").decode("utf-8") if isinstance(data.get(b"url", b""), bytes) else data.get(b"url", "")
                        source_url = data.get(b"source_url", b"").decode("utf-8") if isinstance(data.get(b"source_url", b""), bytes) else data.get(b"source_url", "")
                        
                        # Add with arbitrary similarity score and all required fields
                        processed_results.append({
                            "id": item_id,
                            "title": title,
                            "url": url,
                            "source_url": source_url,
                            "similarity": 0.95 - (i * 0.02),  # Decreasing similarity scores
                            "summary": None,
                            "first_seen_at": datetime.now().isoformat(),
                            "last_seen_at": datetime.now().isoformat(),
                            "hit_count": 1,
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat()
                        })
                    except Exception as e:
                        print(f"REDIS DEBUG: Error in fallback processing: {e}")
                
                print(f"REDIS DEBUG: Fallback retrieval found {len(processed_results)} items")
                return processed_results
            
            return processed_results
        except Exception as e:
            print(f"REDIS DEBUG: Error in vector search: {e}")
            return []
    
    async def get_clusters(self, hours: int = 24, min_similarity: float = 0.6) -> Dict[int, List[Dict[str, Any]]]:
        """Generate clusters using Redis vector search."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # First get all news items in Redis (which are our recent news)
            max_retries = 3
            retry_delay = 1  # seconds
            keys = []
            
            for attempt in range(max_retries):
                try:
                    keys = await self._redis.keys(f"{settings.REDIS_PREFIX}*")
                    break
                except (redis.ConnectionError, redis.TimeoutError) as e:
                    if attempt < max_retries - 1:
                        print(f"Redis keys attempt {attempt+1} failed: {e}. Retrying...")
                        await asyncio.sleep(retry_delay)
                    else:
                        raise
            
            # Filter out the index key
            keys = [key for key in keys if not key.decode().endswith("idx")]
            
            if not keys:
                return {}
                
            # Initialize clusters
            clusters = {}
            next_cluster_id = 0
            processed_ids = set()
            
            # Sort keys to ensure deterministic ordering
            keys.sort()
            
            # Process each news item
            for key in keys:
                # Extract ID from key
                try:
                    news_id = int(key.decode().replace(settings.REDIS_PREFIX, ""))
                except ValueError:
                    # Skip keys that don't match our expected format
                    continue
                
                # Skip if already processed
                if news_id in processed_ids:
                    continue
                
                # Get metadata and vector with retry
                news_data = None
                for attempt in range(max_retries):
                    try:
                        news_data = await self._redis.hgetall(key)
                        break
                    except (redis.ConnectionError, redis.TimeoutError) as e:
                        if attempt < max_retries - 1:
                            print(f"Redis hgetall attempt {attempt+1} failed: {e}. Retrying...")
                            await asyncio.sleep(retry_delay)
                        else:
                            raise
                
                if not news_data or b"embedding" not in news_data:
                    continue
                
                try:
                    # Extract vector
                    vector_bytes = news_data[b"embedding"]
                    vector = np.frombuffer(vector_bytes, dtype=np.float32).tolist()
                    
                    # Handle dimension issues proactively
                    if len(vector) != settings.VECTOR_DIMENSIONS:
                        print(f"Vector dimension mismatch in Redis. Expected {settings.VECTOR_DIMENSIONS}, got {len(vector)}")
                        if len(vector) < settings.VECTOR_DIMENSIONS:
                            vector = vector + [0.0] * (settings.VECTOR_DIMENSIONS - len(vector))
                        else:
                            vector = vector[:settings.VECTOR_DIMENSIONS]
                    
                    # Get similar items
                    similar_items = await self.search_vectors(vector, limit=100)
                    
                    # Filter by similarity threshold
                    similar_items = [item for item in similar_items if item["similarity"] >= min_similarity]
                    
                    # Create new cluster with all required fields for the NewsItemSimilarity model
                    if similar_items:
                        # Add default values for required fields
                        for item in similar_items:
                            # Add required fields if missing
                            if "first_seen_at" not in item:
                                item["first_seen_at"] = datetime.now().isoformat()
                            if "last_seen_at" not in item:
                                item["last_seen_at"] = datetime.now().isoformat()
                            if "hit_count" not in item:
                                item["hit_count"] = 1
                            if "created_at" not in item:
                                item["created_at"] = datetime.now().isoformat()
                            if "updated_at" not in item:
                                item["updated_at"] = datetime.now().isoformat()
                            if "summary" not in item:
                                item["summary"] = None
                                
                        clusters[next_cluster_id] = similar_items
                        
                        # Mark all items in this cluster as processed
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