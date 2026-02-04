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
                                # Calculate actual similarity between this item and the cluster seed
                                d_squared = float(np.sum((vectors_array[i] - vectors_array[idx]) ** 2))
                                similarity = max(0.0, 1 - (d_squared / 2))
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

    def _split_cluster(
        self,
        cluster_items: List[dict],
        cluster_indices: List[int],
        similarity_threshold: float
    ) -> List[Tuple[List[dict], List[int]]]:
        """
        Split a cluster into subclusters at the given similarity threshold.

        Uses transitive clustering within the cluster's own temporary FAISS index.

        Args:
            cluster_items: List of items in the cluster with 'id' and 'similarity'
            cluster_indices: Corresponding indices in the main FAISS index
            similarity_threshold: Similarity threshold for this split level

        Returns:
            List of (items, indices) tuples, one per resulting subcluster
        """
        if len(cluster_items) < 2:
            return [(cluster_items, cluster_indices)]

        max_l2_squared = 2 * (1 - similarity_threshold)
        cluster_vectors = np.array([self.vectors[idx] for idx in cluster_indices])

        temp_index = faiss.IndexFlatL2(self.dimension)
        temp_index.add(cluster_vectors)

        subclusters = []
        used = set()

        for i in range(len(cluster_vectors)):
            if i in used:
                continue

            D, I = temp_index.search(cluster_vectors[i:i+1], len(cluster_vectors))
            similar = set(I[0][D[0] <= max_l2_squared])

            # Transitive expansion
            growing = True
            while growing:
                before = len(similar)
                for idx in list(similar):
                    if 0 <= idx < len(cluster_vectors):
                        D_new, I_new = temp_index.search(cluster_vectors[idx:idx+1], len(cluster_vectors))
                        similar.update(set(I_new[0][D_new[0] <= max_l2_squared]))
                growing = len(similar) > before

            sub_items = []
            sub_indices = []
            for temp_idx in sorted(similar):
                if 0 <= temp_idx < len(cluster_items) and temp_idx not in used:
                    used.add(temp_idx)
                    sub_items.append(cluster_items[temp_idx])
                    sub_indices.append(cluster_indices[temp_idx])

            if sub_items:
                subclusters.append((sub_items, sub_indices))

        return subclusters

    def _recursive_subcluster(
        self,
        cluster_items: List[dict],
        cluster_indices: List[int],
        similarity_threshold: float,
        max_cluster_size: int,
        similarity_step: float = 0.05,
        max_similarity: float = 0.95,
        depth: int = 0,
        max_depth: int = 5
    ) -> dict:
        """
        Recursively split a cluster into subclusters until all leaf clusters
        are at most max_cluster_size items.

        At each level, tries to split using transitive clustering at the current
        similarity threshold. If that doesn't split, increases the threshold
        progressively until it does (or reaches max_similarity). Then recursively
        processes any subclusters that are still too large.

        Args:
            cluster_items: Items in this cluster
            cluster_indices: FAISS index positions for these items
            similarity_threshold: Starting similarity threshold for splitting
            max_cluster_size: Maximum items per leaf subcluster
            similarity_step: How much to increase threshold per attempt
            max_similarity: Maximum threshold to try before giving up
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            Tree node: {'items': [...], 'subclusters': None or [node, ...]}
        """
        # Base case: small enough or too deep
        if len(cluster_items) <= max_cluster_size or depth >= max_depth:
            return {
                'items': cluster_items,
                'subclusters': None
            }

        # Try splitting at progressively higher thresholds
        subclusters = None
        current_threshold = similarity_threshold

        while current_threshold <= max_similarity:
            result = self._split_cluster(cluster_items, cluster_indices, current_threshold)
            if len(result) > 1:
                subclusters = result
                break
            current_threshold = round(current_threshold + similarity_step, 2)

        # Can't split even at max threshold
        if subclusters is None:
            return {
                'items': cluster_items,
                'subclusters': None
            }

        # Recursively process each subcluster that's still too large
        next_threshold = round(current_threshold + similarity_step, 2)
        children = []
        for sub_items, sub_indices in subclusters:
            child = self._recursive_subcluster(
                sub_items, sub_indices,
                next_threshold, max_cluster_size,
                similarity_step, max_similarity,
                depth + 1, max_depth
            )
            children.append(child)

        return {
            'items': cluster_items,
            'subclusters': children
        }

    async def get_hierarchical_clusters(
        self,
        db: AsyncSession,
        hours: int,
        min_similarity: float,
        subcluster_min_size: int,
        subcluster_similarity: float,
        max_cluster_size: int = 10
    ) -> Dict[int, dict]:
        """
        Get hierarchical news clusters using FAISS similarity search.

        Creates a recursive hierarchy:
        - Top-level clusters at min_similarity threshold
        - Recursively splits large clusters at progressively higher thresholds
          until all leaf subclusters have at most max_cluster_size items

        Args:
            db: Database session
            hours: Time range in hours
            min_similarity: Similarity threshold for top-level clusters
            subcluster_min_size: Minimum cluster size to trigger subclustering
            subcluster_similarity: Starting similarity threshold for subclusters
            max_cluster_size: Maximum items per leaf subcluster

        Returns:
            Dictionary mapping cluster_id to hierarchical cluster data:
            {
                cluster_id: {
                    'items': [...],
                    'subclusters': None or [  # Recursive tree of subclusters
                        {'items': [...], 'subclusters': None or [...]},
                        ...
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

                        # Create cluster items with correct similarity to cluster center
                        cluster_items = []
                        cluster_indices_list = []

                        for idx in similar_indices:
                            if idx >= 0 and idx not in used_indices:
                                used_indices.add(idx)
                                # Calculate actual similarity between this item and the cluster seed
                                d_squared = float(np.sum((vectors_array[i] - vectors_array[idx]) ** 2))
                                similarity = max(0.0, 1 - (d_squared / 2))
                                cluster_items.append({
                                    'id': self.news_ids[idx],
                                    'similarity': similarity
                                })
                                cluster_indices_list.append(idx)

                        if len(cluster_items) > 1:
                            # Recursively subcluster if large enough
                            if len(cluster_items) >= subcluster_min_size:
                                tree = self._recursive_subcluster(
                                    cluster_items,
                                    cluster_indices_list,
                                    subcluster_similarity,
                                    max_cluster_size
                                )
                                subclusters = tree.get('subclusters')
                            else:
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
            def _count_tree_stats(node, depth=0):
                """Count subclusters and max depth in a tree."""
                if node is None or not isinstance(node, list):
                    return 0, depth
                total = len(node)
                max_d = depth
                for child in node:
                    if isinstance(child, dict) and child.get('subclusters'):
                        sub_count, sub_depth = _count_tree_stats(child['subclusters'], depth + 1)
                        total += sub_count
                        max_d = max(max_d, sub_depth)
                return total, max_d

            subclustered_count = sum(1 for c in hierarchical_clusters.values() if c['subclusters'] is not None)
            total_subclusters = 0
            max_depth = 0
            for c in hierarchical_clusters.values():
                if c['subclusters']:
                    count, depth = _count_tree_stats(c['subclusters'])
                    total_subclusters += count
                    max_depth = max(max_depth, depth)

            logger.info(
                f"Generated {len(hierarchical_clusters)} hierarchical clusters "
                f"({subclustered_count} with subclusters, "
                f"{total_subclusters} total subcluster nodes, "
                f"max depth {max_depth})"
            )

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
