"""FAISS service for in-memory vector operations."""
import logging
import traceback
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np
import faiss
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem
from app.config import settings

logger = logging.getLogger(__name__)

class FaissService:
    """Service for managing vector operations using FAISS."""
    
    def __init__(self):
        """Initialize the FAISS index."""
        self.dimension = settings.VECTOR_DIMENSIONS
        # Using L2 distance, normalize vectors for cosine similarity
        self.index = faiss.IndexFlatL2(self.dimension)
        self.news_ids = []  # Keep track of news IDs in same order as vectors
        self.last_update = None
        self.vectors = None  # Store vectors for clustering
        
    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize vector for cosine similarity."""
        try:
            return vector / np.linalg.norm(vector)
        except Exception as e:
            logger.error(f"Error normalizing vector: {str(e)}\nVector shape: {vector.shape}\nVector: {vector}")
            raise
        
    async def update_index(self, db: AsyncSession, hours: int = 48):
        """Update the FAISS index with recent vectors from PostgreSQL."""
        try:
            # Get recent news items using timezone-aware UTC time
            time_filter = datetime.now(timezone.utc) - timedelta(hours=hours)
            stmt = select(NewsItem).filter(
                NewsItem.last_seen_at >= time_filter,
                NewsItem.embedding.is_not(None)
            )
            
            result = await db.execute(stmt)
            news_items = result.scalars().all()
            
            if not news_items:
                logger.warning("No news items found for indexing")
                return
            
            # Reset index
            self.index = faiss.IndexFlatL2(self.dimension)
            self.news_ids = []
            self.vectors = []
            
            # Add vectors to index
            for item in news_items:
                try:
                    vector = np.array(item.embedding, dtype=np.float32)
                    if vector.shape != (self.dimension,):
                        logger.error(f"Invalid vector shape for news item {item.id}: {vector.shape}")
                        continue
                    vector = self._normalize_vector(vector)
                    self.vectors.append(vector)
                    self.news_ids.append(item.id)
                except Exception as e:
                    logger.error(f"Error processing vector for news item {item.id}: {str(e)}")
                    continue
            
            if not self.vectors:
                logger.warning("No valid vectors found for indexing")
                return
                
            vectors_array = np.array(self.vectors)
            self.index.add(vectors_array)
            self.last_update = datetime.now(timezone.utc)
            
            logger.info(f"Updated FAISS index with {len(self.vectors)} vectors")
            
        except Exception as e:
            logger.error(f"Error updating FAISS index: {str(e)}\n{traceback.format_exc()}")
            raise
            
    async def get_clusters(self, db: AsyncSession, hours: int, min_similarity: float) -> Dict[int, List[dict]]:
        """Get news clusters using FAISS similarity search."""
        try:
            # Update index if needed
            now = datetime.now(timezone.utc)
            if not self.last_update or \
               (now - self.last_update) > timedelta(hours=1):
                await self.update_index(db, hours)
            
            if self.index.ntotal == 0 or not self.vectors:
                logger.warning("No vectors in FAISS index")
                return {}
            
            # Convert similarity threshold to L2 distance
            # For normalized vectors: cos_sim = 1 - L2^2/2
            # Therefore: L2^2 = 2(1 - cos_sim)
            max_l2_squared = 2 * (1 - min_similarity)
            
            # Find clusters using transitive clustering
            clusters = {}
            used_indices = set()
            cluster_id = 0
            
            vectors_array = np.array(self.vectors)
            
            for i in range(len(vectors_array)):
                if i in used_indices:
                    continue
                    
                try:
                    # Search for similar vectors
                    D, I = self.index.search(vectors_array[i:i+1], self.index.ntotal)
                    
                    # Filter by distance threshold and create cluster
                    similar_indices = set(I[0][D[0] <= max_l2_squared])
                    
                    if len(similar_indices) > 1:  # At least 2 items to form a cluster
                        # Use transitive similarity: add items similar to any cluster member
                        cluster_growing = True
                        while cluster_growing:
                            size_before = len(similar_indices)
                            
                            # Check similarity to all current cluster members
                            for idx in list(similar_indices):
                                if idx >= 0:  # Valid index
                                    D_new, I_new = self.index.search(vectors_array[idx:idx+1], self.index.ntotal)
                                    new_similar = set(I_new[0][D_new[0] <= max_l2_squared])
                                    similar_indices.update(new_similar)
                            
                            cluster_growing = len(similar_indices) > size_before
                        
                        # Create cluster items
                        cluster_items = []
                        for idx in similar_indices:
                            if idx >= 0 and idx not in used_indices:  # Valid index and not used
                                used_indices.add(idx)
                                # Calculate similarity to cluster center
                                D_center, _ = self.index.search(vectors_array[i:i+1], 1)
                                similarity = 1 - (float(D_center[0][0]) / 2)  # Convert L2 squared to similarity
                                cluster_items.append({
                                    'id': self.news_ids[idx],
                                    'similarity': similarity
                                })
                        
                        if len(cluster_items) > 1:  # Ensure cluster has at least 2 items
                            clusters[cluster_id] = cluster_items
                            cluster_id += 1
                            
                except Exception as e:
                    logger.error(f"Error processing cluster for vector {i}: {str(e)}\n{traceback.format_exc()}")
                    continue
            
            logger.info(f"Generated {len(clusters)} clusters")
            return clusters

        except Exception as e:
            logger.error(f"Error getting clusters: {str(e)}\n{traceback.format_exc()}")
            raise

    def _create_subclusters(
        self,
        cluster_items: List[dict],
        cluster_indices: List[int],
        subcluster_similarity: float
    ) -> List[List[dict]]:
        """
        Create subclusters within a large cluster using higher similarity threshold.

        Args:
            cluster_items: List of items in the cluster with 'id' and 'similarity'
            cluster_indices: Corresponding indices in the FAISS index
            subcluster_similarity: Higher similarity threshold for subclustering

        Returns:
            List of subclusters, each containing a list of items
        """
        if len(cluster_items) < 2:
            return [cluster_items]

        # Convert similarity threshold to L2 distance
        max_l2_squared = 2 * (1 - subcluster_similarity)

        # Get vectors for this cluster
        cluster_vectors = np.array([self.vectors[idx] for idx in cluster_indices])

        # Create a temporary FAISS index for this cluster
        temp_index = faiss.IndexFlatL2(self.dimension)
        temp_index.add(cluster_vectors)

        # Map from temp index position to original item
        temp_to_item = {i: (cluster_items[i], cluster_indices[i]) for i in range(len(cluster_items))}

        subclusters = []
        used_temp_indices = set()

        for i in range(len(cluster_vectors)):
            if i in used_temp_indices:
                continue

            # Search for similar vectors within this cluster
            D, I = temp_index.search(cluster_vectors[i:i+1], len(cluster_vectors))

            # Filter by higher similarity threshold
            similar_temp_indices = set(I[0][D[0] <= max_l2_squared])

            if len(similar_temp_indices) > 0:
                # Use transitive similarity within the subcluster
                subcluster_growing = True
                while subcluster_growing:
                    size_before = len(similar_temp_indices)

                    for idx in list(similar_temp_indices):
                        if idx >= 0 and idx < len(cluster_vectors):
                            D_new, I_new = temp_index.search(cluster_vectors[idx:idx+1], len(cluster_vectors))
                            new_similar = set(I_new[0][D_new[0] <= max_l2_squared])
                            similar_temp_indices.update(new_similar)

                    subcluster_growing = len(similar_temp_indices) > size_before

                # Create subcluster items
                subcluster_items = []
                for temp_idx in similar_temp_indices:
                    if temp_idx >= 0 and temp_idx not in used_temp_indices and temp_idx < len(cluster_items):
                        used_temp_indices.add(temp_idx)
                        item, _ = temp_to_item[temp_idx]
                        subcluster_items.append(item)

                if subcluster_items:
                    subclusters.append(subcluster_items)

        # If subclustering didn't produce meaningful results, return original as single subcluster
        if len(subclusters) <= 1:
            return [cluster_items]

        return subclusters

    async def get_hierarchical_clusters(
        self,
        db: AsyncSession,
        hours: int,
        min_similarity: float,
        subcluster_min_size: int,
        subcluster_similarity: float
    ) -> Dict[int, dict]:
        """
        Get hierarchical news clusters using FAISS similarity search.

        Creates two-level hierarchy:
        - Top-level clusters at min_similarity threshold
        - Subclusters at higher subcluster_similarity for large clusters

        Args:
            db: Database session
            hours: Time range in hours
            min_similarity: Similarity threshold for top-level clusters
            subcluster_min_size: Minimum cluster size to trigger subclustering
            subcluster_similarity: Higher similarity threshold for subclusters

        Returns:
            Dictionary mapping cluster_id to hierarchical cluster data:
            {
                cluster_id: {
                    'items': [...],  # All items in cluster
                    'subclusters': [  # List of subclusters (if applicable)
                        [item1, item2, ...],
                        [item3, item4, ...],
                    ]
                }
            }
        """
        try:
            # Update index if needed
            now = datetime.now(timezone.utc)
            if not self.last_update or \
               (now - self.last_update) > timedelta(hours=1):
                await self.update_index(db, hours)

            if self.index.ntotal == 0 or not self.vectors:
                logger.warning("No vectors in FAISS index")
                return {}

            # Convert similarity threshold to L2 distance
            max_l2_squared = 2 * (1 - min_similarity)

            # Find clusters using transitive clustering
            hierarchical_clusters = {}
            used_indices = set()
            cluster_id = 0

            vectors_array = np.array(self.vectors)

            for i in range(len(vectors_array)):
                if i in used_indices:
                    continue

                try:
                    # Search for similar vectors
                    D, I = self.index.search(vectors_array[i:i+1], self.index.ntotal)

                    # Filter by distance threshold and create cluster
                    similar_indices = set(I[0][D[0] <= max_l2_squared])

                    if len(similar_indices) > 1:  # At least 2 items to form a cluster
                        # Use transitive similarity
                        cluster_growing = True
                        while cluster_growing:
                            size_before = len(similar_indices)

                            for idx in list(similar_indices):
                                if idx >= 0:
                                    D_new, I_new = self.index.search(vectors_array[idx:idx+1], self.index.ntotal)
                                    new_similar = set(I_new[0][D_new[0] <= max_l2_squared])
                                    similar_indices.update(new_similar)

                            cluster_growing = len(similar_indices) > size_before

                        # Create cluster items
                        cluster_items = []
                        cluster_indices = []  # Track indices for subclustering

                        for idx in similar_indices:
                            if idx >= 0 and idx not in used_indices:
                                used_indices.add(idx)
                                D_center, _ = self.index.search(vectors_array[i:i+1], 1)
                                similarity = 1 - (float(D_center[0][0]) / 2)
                                cluster_items.append({
                                    'id': self.news_ids[idx],
                                    'similarity': similarity
                                })
                                cluster_indices.append(idx)

                        if len(cluster_items) > 1:
                            # Check if cluster should be subclustered
                            subclusters = None
                            if len(cluster_items) >= subcluster_min_size:
                                subclusters = self._create_subclusters(
                                    cluster_items,
                                    cluster_indices,
                                    subcluster_similarity
                                )
                                # Only keep subclusters if we got meaningful division
                                if len(subclusters) <= 1:
                                    subclusters = None

                            hierarchical_clusters[cluster_id] = {
                                'items': cluster_items,
                                'subclusters': subclusters
                            }
                            cluster_id += 1

                except Exception as e:
                    logger.error(f"Error processing hierarchical cluster for vector {i}: {str(e)}\n{traceback.format_exc()}")
                    continue

            # Log statistics
            subclustered_count = sum(1 for c in hierarchical_clusters.values() if c['subclusters'] is not None)
            logger.info(f"Generated {len(hierarchical_clusters)} hierarchical clusters ({subclustered_count} with subclusters)")

            return hierarchical_clusters

        except Exception as e:
            logger.error(f"Error getting hierarchical clusters: {str(e)}\n{traceback.format_exc()}")
            raise

    async def search_similar(
        self, 
        db: AsyncSession,
        vector: np.ndarray,
        k: int = 10,
        min_similarity: float = 0.5
    ) -> List[Tuple[int, float]]:
        """Search for similar vectors."""
        try:
            if self.index.ntotal == 0:
                return []
            
            # Normalize query vector
            vector = self._normalize_vector(vector.reshape(1, -1))
            
            # Convert similarity threshold to L2 distance
            max_l2_squared = 2 * (1 - min_similarity)
            
            # Search
            D, I = self.index.search(vector, k)
            
            # Convert L2 distances to similarities and filter
            results = []
            for i, idx in enumerate(I[0]):
                if idx != -1:  # Valid index
                    similarity = 1 - (D[0][i] / 2)  # Convert L2 squared to similarity
                    if similarity >= min_similarity:
                        results.append((self.news_ids[idx], float(similarity)))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching similar vectors: {str(e)}\n{traceback.format_exc()}")
            raise

# Global instance
faiss_service = FaissService()

def get_faiss_service() -> FaissService:
    """Get the global FAISS service instance."""
    return faiss_service
