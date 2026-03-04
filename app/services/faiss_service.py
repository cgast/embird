"""FAISS service for in-memory vector operations with per-topic indexes."""
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


class TopicIndex:
    """FAISS index and metadata for a single topic."""

    def __init__(self, dimension: int):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.news_ids: List[int] = []
        self.vectors: List[np.ndarray] = []
        self.last_update: Optional[datetime] = None


class FaissService:
    """Service for managing vector operations using FAISS, with per-topic indexes."""

    def __init__(self):
        """Initialize the FAISS service."""
        self.dimension = settings.VECTOR_DIMENSIONS
        self.topic_indexes: Dict[int, TopicIndex] = {}

    def _get_topic_index(self, topic_id: int) -> TopicIndex:
        """Get or create a topic index."""
        if topic_id not in self.topic_indexes:
            self.topic_indexes[topic_id] = TopicIndex(self.dimension)
        return self.topic_indexes[topic_id]

    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize vector for cosine similarity."""
        try:
            return vector / np.linalg.norm(vector)
        except Exception as e:
            logger.error(f"Error normalizing vector: {str(e)}\nVector shape: {vector.shape}\nVector: {vector}")
            raise

    async def update_index(self, db: AsyncSession, hours: int = 48, topic_id: Optional[int] = None):
        """Update the FAISS index with recent vectors from PostgreSQL.

        If topic_id is provided, only update that topic's index.
        If topic_id is None, update all topics.
        """
        try:
            # Get recent news items using timezone-aware UTC time
            time_filter = datetime.now(timezone.utc) - timedelta(hours=hours)
            stmt = select(NewsItem).filter(
                NewsItem.last_seen_at >= time_filter,
                NewsItem.embedding.is_not(None)
            )
            if topic_id is not None:
                stmt = stmt.filter(NewsItem.topic_id == topic_id)

            result = await db.execute(stmt)
            news_items = result.scalars().all()

            if not news_items:
                if topic_id is not None:
                    logger.warning(f"No news items found for indexing (topic_id={topic_id})")
                else:
                    logger.warning("No news items found for indexing")
                return

            # Group by topic_id
            items_by_topic: Dict[int, List] = {}
            for item in news_items:
                tid = item.topic_id
                if tid not in items_by_topic:
                    items_by_topic[tid] = []
                items_by_topic[tid].append(item)

            for tid, items in items_by_topic.items():
                tindex = self._get_topic_index(tid)

                # Reset index
                tindex.index = faiss.IndexFlatL2(self.dimension)
                tindex.news_ids = []
                tindex.vectors = []

                # Add vectors to index
                for item in items:
                    try:
                        vector = np.array(item.embedding, dtype=np.float32)
                        if vector.shape != (self.dimension,):
                            logger.error(f"Invalid vector shape for news item {item.id}: {vector.shape}")
                            continue
                        vector = self._normalize_vector(vector)
                        tindex.vectors.append(vector)
                        tindex.news_ids.append(item.id)
                    except Exception as e:
                        logger.error(f"Error processing vector for news item {item.id}: {str(e)}")
                        continue

                if not tindex.vectors:
                    logger.warning(f"No valid vectors found for indexing (topic_id={tid})")
                    continue

                vectors_array = np.array(tindex.vectors)
                tindex.index.add(vectors_array)
                tindex.last_update = datetime.now(timezone.utc)

                logger.info(f"Updated FAISS index for topic {tid} with {len(tindex.vectors)} vectors")

        except Exception as e:
            logger.error(f"Error updating FAISS index: {str(e)}\n{traceback.format_exc()}")
            raise

    async def get_clusters(self, db: AsyncSession, hours: int, min_similarity: float, topic_id: int = 1) -> Dict[int, List[dict]]:
        """Get news clusters using FAISS similarity search for a specific topic."""
        try:
            tindex = self._get_topic_index(topic_id)

            # Update index if needed
            now = datetime.now(timezone.utc)
            if not tindex.last_update or \
               (now - tindex.last_update) > timedelta(hours=1):
                await self.update_index(db, hours, topic_id)
                tindex = self._get_topic_index(topic_id)

            if tindex.index.ntotal == 0 or not tindex.vectors:
                logger.warning(f"No vectors in FAISS index for topic {topic_id}")
                return {}

            # Convert similarity threshold to L2 distance
            max_l2_squared = 2 * (1 - min_similarity)

            # Find clusters using transitive clustering
            clusters = {}
            used_indices = set()
            cluster_id = 0

            vectors_array = np.array(tindex.vectors)

            for i in range(len(vectors_array)):
                if i in used_indices:
                    continue

                try:
                    D, I = tindex.index.search(vectors_array[i:i+1], tindex.index.ntotal)
                    similar_indices = set(I[0][D[0] <= max_l2_squared])

                    if len(similar_indices) > 1:
                        cluster_growing = True
                        while cluster_growing:
                            size_before = len(similar_indices)
                            for idx in list(similar_indices):
                                if idx >= 0:
                                    D_new, I_new = tindex.index.search(vectors_array[idx:idx+1], tindex.index.ntotal)
                                    new_similar = set(I_new[0][D_new[0] <= max_l2_squared])
                                    similar_indices.update(new_similar)
                            cluster_growing = len(similar_indices) > size_before

                        cluster_items = []
                        for idx in similar_indices:
                            if idx >= 0 and idx not in used_indices:
                                used_indices.add(idx)
                                d_squared = float(np.sum((vectors_array[i] - vectors_array[idx]) ** 2))
                                similarity = max(0.0, 1 - (d_squared / 2))
                                cluster_items.append({
                                    'id': tindex.news_ids[idx],
                                    'similarity': similarity
                                })

                        if len(cluster_items) > 1:
                            clusters[cluster_id] = cluster_items
                            cluster_id += 1

                except Exception as e:
                    logger.error(f"Error processing cluster for vector {i}: {str(e)}\n{traceback.format_exc()}")
                    continue

            logger.info(f"Generated {len(clusters)} clusters for topic {topic_id}")
            return clusters

        except Exception as e:
            logger.error(f"Error getting clusters: {str(e)}\n{traceback.format_exc()}")
            raise

    def _split_cluster(
        self,
        cluster_items: List[dict],
        cluster_indices: List[int],
        similarity_threshold: float,
        topic_id: int = 1
    ) -> List[Tuple[List[dict], List[int]]]:
        """Split a cluster into subclusters at the given similarity threshold."""
        if len(cluster_items) < 2:
            return [(cluster_items, cluster_indices)]

        tindex = self._get_topic_index(topic_id)
        max_l2_squared = 2 * (1 - similarity_threshold)
        cluster_vectors = np.array([tindex.vectors[idx] for idx in cluster_indices])

        temp_index = faiss.IndexFlatL2(self.dimension)
        temp_index.add(cluster_vectors)

        subclusters = []
        used = set()

        for i in range(len(cluster_vectors)):
            if i in used:
                continue

            D, I = temp_index.search(cluster_vectors[i:i+1], len(cluster_vectors))
            similar = set(I[0][D[0] <= max_l2_squared])

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
        topic_id: int = 1,
        similarity_step: float = 0.05,
        max_similarity: float = 0.95,
        depth: int = 0,
        max_depth: int = 5
    ) -> dict:
        """Recursively split a cluster into subclusters."""
        if len(cluster_items) <= max_cluster_size or depth >= max_depth:
            return {
                'items': cluster_items,
                'subclusters': None
            }

        subclusters = None
        current_threshold = similarity_threshold

        while current_threshold <= max_similarity:
            result = self._split_cluster(cluster_items, cluster_indices, current_threshold, topic_id)
            if len(result) > 1:
                subclusters = result
                break
            current_threshold = round(current_threshold + similarity_step, 2)

        if subclusters is None:
            return {
                'items': cluster_items,
                'subclusters': None
            }

        next_threshold = round(current_threshold + similarity_step, 2)
        children = []
        for sub_items, sub_indices in subclusters:
            child = self._recursive_subcluster(
                sub_items, sub_indices,
                next_threshold, max_cluster_size,
                topic_id,
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
        max_cluster_size: int = 10,
        topic_id: int = 1
    ) -> Dict[int, dict]:
        """Get hierarchical news clusters using FAISS similarity search for a topic."""
        try:
            tindex = self._get_topic_index(topic_id)

            # Update index if needed
            now = datetime.now(timezone.utc)
            if not tindex.last_update or \
               (now - tindex.last_update) > timedelta(hours=1):
                await self.update_index(db, hours, topic_id)
                tindex = self._get_topic_index(topic_id)

            if tindex.index.ntotal == 0 or not tindex.vectors:
                logger.warning(f"No vectors in FAISS index for topic {topic_id}")
                return {}

            max_l2_squared = 2 * (1 - min_similarity)

            hierarchical_clusters = {}
            used_indices = set()
            cluster_id = 0

            vectors_array = np.array(tindex.vectors)

            for i in range(len(vectors_array)):
                if i in used_indices:
                    continue

                try:
                    D, I = tindex.index.search(vectors_array[i:i+1], tindex.index.ntotal)
                    similar_indices = set(I[0][D[0] <= max_l2_squared])

                    if len(similar_indices) > 1:
                        cluster_growing = True
                        while cluster_growing:
                            size_before = len(similar_indices)
                            for idx in list(similar_indices):
                                if idx >= 0:
                                    D_new, I_new = tindex.index.search(vectors_array[idx:idx+1], tindex.index.ntotal)
                                    new_similar = set(I_new[0][D_new[0] <= max_l2_squared])
                                    similar_indices.update(new_similar)
                            cluster_growing = len(similar_indices) > size_before

                        cluster_items = []
                        cluster_indices_list = []

                        for idx in similar_indices:
                            if idx >= 0 and idx not in used_indices:
                                used_indices.add(idx)
                                d_squared = float(np.sum((vectors_array[i] - vectors_array[idx]) ** 2))
                                similarity = max(0.0, 1 - (d_squared / 2))
                                cluster_items.append({
                                    'id': tindex.news_ids[idx],
                                    'similarity': similarity
                                })
                                cluster_indices_list.append(idx)

                        if len(cluster_items) > 1:
                            if len(cluster_items) >= subcluster_min_size:
                                tree = self._recursive_subcluster(
                                    cluster_items,
                                    cluster_indices_list,
                                    subcluster_similarity,
                                    max_cluster_size,
                                    topic_id
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
                f"Generated {len(hierarchical_clusters)} hierarchical clusters for topic {topic_id} "
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
        min_similarity: float = 0.5,
        topic_id: int = 1
    ) -> List[Tuple[int, float]]:
        """Search for similar vectors within a topic."""
        try:
            tindex = self._get_topic_index(topic_id)

            if tindex.index.ntotal == 0:
                return []

            # Normalize query vector
            vector = self._normalize_vector(vector.reshape(1, -1))

            # Search
            D, I = tindex.index.search(vector, k)

            # Convert L2 distances to similarities and filter
            results = []
            for i, idx in enumerate(I[0]):
                if idx != -1:
                    similarity = 1 - (D[0][i] / 2)
                    if similarity >= min_similarity:
                        results.append((tindex.news_ids[idx], float(similarity)))

            return results

        except Exception as e:
            logger.error(f"Error searching similar vectors: {str(e)}\n{traceback.format_exc()}")
            raise


# Global instance
faiss_service = FaissService()

def get_faiss_service() -> FaissService:
    """Get the global FAISS service instance."""
    return faiss_service
