"""Shared visualization service for generating clusters and UMAP visualizations."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import logging
import traceback
import re
from collections import Counter
import umap
import numpy as np
from sqlalchemy import select, text, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem, NewsClusters, NewsUMAP
from app.models.preference_vector import PreferenceVector
from app.services.faiss_service import get_faiss_service
from app.config import settings

logger = logging.getLogger(__name__)

# Common stop words to filter out from keywords
STOP_WORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
    'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were',
    'will', 'with', 'the', 'this', 'but', 'they', 'have', 'had', 'what', 'when',
    'where', 'who', 'which', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
    'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'can', 'could', 'may', 'might',
    'must', 'shall', 'should', 'would', 'now', 'also', 'into', 'over', 'after',
    'before', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
    'there', 'when', 'where', 'why', 'how', 'any', 'been', 'being', 'do', 'does',
    'did', 'doing', 'about', 'against', 'up', 'down', 'out', 'off', 'through',
    'during', 'while', 'above', 'below', 'their', 'them', 'these', 'those', 'his',
    'her', 'him', 'she', 'he', 'we', 'you', 'your', 'our', 'my', 'me', 'i', 'us',
    'says', 'said', 'new', 'news', 'report', 'reports', 'according', 'like',
    'get', 'gets', 'got', 'make', 'makes', 'made', 'one', 'two', 'three', 'first',
    'year', 'years', 'day', 'days', 'week', 'weeks', 'month', 'months', 'time',
    'way', 'even', 'well', 'back', 'much', 'still', 'many', 'last', 'take', 'see',
    'come', 'use', 'used', 'using', 'go', 'know', 'need', 'want', 'look', 'think',
    'right', 'old', 'going', 'good', 'great', 'big', 'long', 'little', 'own', 'set',
    'put', 'end', 'another', 'best', 'worst', 'top', 'high', 'low', 'part', 'full',
    'early', 'late', 'say', 'latest', 'breaking', 'live', 'update', 'updates'
}


def extract_cluster_keywords(articles: List[dict], num_keywords: int = 4) -> str:
    """
    Extract representative keywords from a cluster of articles.

    Uses a simplified TF-IDF approach to find distinctive terms:
    - Extracts words from titles and summaries
    - Filters stop words and short terms
    - Weights title words higher than summary words
    - Returns top keywords joined with commas

    Args:
        articles: List of article dictionaries with 'title' and 'summary' fields
        num_keywords: Number of keywords to extract (default 4)

    Returns:
        Comma-separated string of keywords (e.g., "AI, technology, OpenAI, regulation")
    """
    if not articles:
        return "Uncategorized"

    word_scores = Counter()

    # Weight for title vs summary words
    TITLE_WEIGHT = 3.0
    SUMMARY_WEIGHT = 1.0

    for article in articles:
        title = article.get('title', '') or ''
        summary = article.get('summary', '') or ''

        # Extract and score title words (higher weight)
        title_words = _tokenize(title)
        for word in title_words:
            word_scores[word] += TITLE_WEIGHT

        # Extract and score summary words (lower weight)
        summary_words = _tokenize(summary)
        for word in summary_words:
            word_scores[word] += SUMMARY_WEIGHT

    if not word_scores:
        return "Uncategorized"

    # Get top keywords, avoiding duplicates and substrings
    top_words = []
    for word, _ in word_scores.most_common(num_keywords * 3):
        # Skip if this word is a substring of an existing keyword or vice versa
        is_redundant = False
        for existing in top_words:
            if word in existing or existing in word:
                is_redundant = True
                break

        if not is_redundant:
            # Capitalize for display
            top_words.append(word.capitalize())

        if len(top_words) >= num_keywords:
            break

    if not top_words:
        return "Uncategorized"

    return ", ".join(top_words)


def _tokenize(text: str) -> List[str]:
    """
    Tokenize text into words, filtering stop words and short terms.

    Args:
        text: Input text to tokenize

    Returns:
        List of filtered word tokens
    """
    if not text:
        return []

    # Convert to lowercase and extract words
    text = text.lower()
    # Match words with at least 2 characters (letters only)
    words = re.findall(r'\b[a-z]{3,}\b', text)

    # Filter out stop words and very common terms
    filtered = [
        word for word in words
        if word not in STOP_WORDS and len(word) >= 3
    ]

    return filtered

def _enrich_article(news_item: NewsItem, similarity: float, cluster_id: int) -> dict:
    """Helper to create enriched article dict from NewsItem."""
    return {
        "id": news_item.id,
        "title": news_item.title,
        "summary": news_item.summary,
        "url": news_item.url,
        "source_url": news_item.source_url,
        "first_seen_at": news_item.first_seen_at.isoformat() if news_item.first_seen_at else None,
        "last_seen_at": news_item.last_seen_at.isoformat() if news_item.last_seen_at else None,
        "hit_count": news_item.hit_count,
        "created_at": news_item.created_at.isoformat() if news_item.created_at else None,
        "updated_at": news_item.updated_at.isoformat() if news_item.updated_at else None,
        "similarity": similarity,
        "cluster_id": cluster_id
    }


def _enrich_subcluster_tree(node: dict, news_items_map: dict, cluster_id: int) -> Optional[dict]:
    """
    Recursively enrich a subcluster tree node with full article data and keywords.

    Args:
        node: Tree node from faiss_service with 'items' and 'subclusters'
        news_items_map: Map of news_id -> NewsItem
        cluster_id: Parent cluster ID

    Returns:
        Enriched node with 'name', 'articles', and optional 'subclusters', or None if empty
    """
    enriched_items = []
    for item in node['items']:
        news_item = news_items_map.get(item['id'])
        if news_item:
            enriched_items.append(_enrich_article(news_item, item['similarity'], cluster_id))

    if not enriched_items:
        return None

    result = {
        'name': extract_cluster_keywords(enriched_items, num_keywords=3),
        'articles': enriched_items,
    }

    if node.get('subclusters') and len(node['subclusters']) > 1:
        enriched_subs = []
        for sub_node in node['subclusters']:
            enriched_sub = _enrich_subcluster_tree(sub_node, news_items_map, cluster_id)
            if enriched_sub:
                enriched_subs.append(enriched_sub)

        if len(enriched_subs) > 1:
            result['subclusters'] = enriched_subs
        else:
            result['subclusters'] = None
    else:
        result['subclusters'] = None

    return result


async def generate_clusters(db: AsyncSession, hours: int, min_similarity: float) -> Dict[int, dict]:
    """Generate news clusters using FAISS vector similarity.

    Returns:
        Dictionary mapping cluster_id to cluster data with structure:
        {
            cluster_id: {
                "name": "keyword1, keyword2, keyword3",
                "articles": [list of article dicts],
                "subclusters": [  # Optional - only for large clusters
                    {
                        "name": "subcluster keywords",
                        "articles": [list of article dicts]
                    },
                    ...
                ]
            }
        }
    """
    try:
        # Get FAISS service
        faiss_service = get_faiss_service()

        # Check if hierarchical clustering is enabled
        use_hierarchical = settings.SUBCLUSTER_ENABLED

        if use_hierarchical:
            # Generate hierarchical clusters with recursive subclustering
            clusters = await faiss_service.get_hierarchical_clusters(
                db,
                hours,
                min_similarity,
                settings.SUBCLUSTER_MIN_SIZE,
                settings.SUBCLUSTER_SIMILARITY,
                settings.SUBCLUSTER_MAX_SIZE
            )
        else:
            # Generate flat clusters (legacy mode)
            flat_clusters = await faiss_service.get_clusters(db, hours, min_similarity)
            # Convert to hierarchical format for consistent processing
            clusters = {
                cid: {'items': items, 'subclusters': None}
                for cid, items in flat_clusters.items()
            }

        if not clusters:
            logger.warning("No clusters found")
            return {}

        # Collect all news IDs for batch fetching
        all_news_ids = set()
        for cluster_data in clusters.values():
            for item in cluster_data['items']:
                all_news_ids.add(item['id'])

        # Batch fetch all news items from database
        stmt = select(NewsItem).filter(NewsItem.id.in_(all_news_ids))
        result = await db.execute(stmt)
        news_items_map = {item.id: item for item in result.scalars().all()}

        # Enrich cluster data
        enriched_clusters: Dict[int, dict] = {}

        for cluster_id, cluster_data in clusters.items():
            try:
                items = cluster_data['items']
                subclusters_raw = cluster_data.get('subclusters')

                # Enrich all items in the cluster
                enriched_items = []
                for item in items:
                    news_item = news_items_map.get(item['id'])
                    if news_item:
                        enriched_items.append(_enrich_article(news_item, item['similarity'], cluster_id))

                if not enriched_items:
                    logger.warning(f"No news items found for cluster {cluster_id}")
                    continue

                # Generate cluster name from all articles
                cluster_name = extract_cluster_keywords(enriched_items)

                cluster_result = {
                    "name": cluster_name,
                    "articles": enriched_items
                }

                # Process subclusters if present (recursive tree structure)
                if subclusters_raw and len(subclusters_raw) > 1:
                    enriched_subclusters = []
                    for sub_node in subclusters_raw:
                        enriched_sub = _enrich_subcluster_tree(sub_node, news_items_map, cluster_id)
                        if enriched_sub:
                            enriched_subclusters.append(enriched_sub)

                    # Only include subclusters if we have multiple meaningful ones
                    if len(enriched_subclusters) > 1:
                        cluster_result["subclusters"] = enriched_subclusters

                enriched_clusters[cluster_id] = cluster_result

            except Exception as e:
                logger.error(f"Error enriching cluster {cluster_id}: {str(e)}\n{traceback.format_exc()}")
                continue

        # Log statistics
        subclustered_count = sum(1 for c in enriched_clusters.values() if 'subclusters' in c)
        logger.info(f"Generated {len(enriched_clusters)} enriched clusters ({subclustered_count} with subclusters)")
        return enriched_clusters

    except Exception as e:
        logger.error(f"Clustering error: {str(e)}\n{traceback.format_exc()}")
        raise

async def generate_umap_visualization(db: AsyncSession, hours: int, min_similarity: float) -> List[dict]:
    """Generate UMAP visualization data."""
    try:
        # First generate clusters to get cluster assignments
        clusters = await generate_clusters(db, hours, min_similarity)

        # Rank clusters by article count and keep only top 20
        TOP_N_CLUSTERS = 20
        ranked_cluster_ids = sorted(
            clusters.keys(),
            key=lambda cid: len(
                clusters[cid].get('articles', clusters[cid])
                if isinstance(clusters[cid], dict) else clusters[cid]
            ),
            reverse=True
        )[:TOP_N_CLUSTERS]
        top_clusters = set(ranked_cluster_ids)

        # Create mappings of news item ID to cluster ID and cluster names
        item_to_cluster = {}
        cluster_names = {}
        for cluster_id, cluster_data in clusters.items():
            if cluster_id not in top_clusters:
                continue
            # Handle both old format (list) and new format (dict with 'articles' key)
            if isinstance(cluster_data, dict):
                articles = cluster_data.get('articles', cluster_data)
                cluster_names[cluster_id] = cluster_data.get('name', f'Cluster {cluster_id}')
            else:
                articles = cluster_data
                cluster_names[cluster_id] = f'Cluster {cluster_id}'
            for item in articles:
                item_to_cluster[item['id']] = cluster_id

        # Get news items from the last n hours - use timezone-aware UTC time
        now = datetime.now(timezone.utc)
        time_filter = now - timedelta(hours=hours)
        
        # Get all news items with embeddings from the specified time period
        stmt = select(NewsItem).filter(
            NewsItem.last_seen_at >= time_filter,
            NewsItem.embedding.is_not(None)
        ).order_by(NewsItem.last_seen_at.desc())
        
        result = await db.execute(stmt)
        news_items = result.scalars().all()
        
        if not news_items:
            logger.warning("No news items found for UMAP visualization")
            return []

        # Get preference vectors from PostgreSQL
        stmt = select(PreferenceVector).filter(PreferenceVector.embedding.is_not(None))
        result = await db.execute(stmt)
        preference_vectors = result.scalars().all()
        logger.info(f"Found {len(preference_vectors)} preference vectors in PostgreSQL")
        
        # Process all embeddings together
        all_embeddings = []
        all_items = []
        is_pref_vector = []  # Track which items are preference vectors

        # Add news item embeddings (only items in top clusters)
        for item in news_items:
            if item.id not in item_to_cluster:
                continue
            try:
                # Convert pgvector to numpy array
                vector = np.array(item.embedding.tolist(), dtype=np.float32)
                if vector.shape != (settings.VECTOR_DIMENSIONS,):
                    logger.error(f"Invalid vector shape for news item {item.id}: {vector.shape}")
                    continue
                all_embeddings.append(vector)
                all_items.append(item)
                is_pref_vector.append(False)
            except Exception as e:
                logger.error(f"Error processing embedding for news item {item.id}: {str(e)}")
                continue

        # Add preference vector embeddings
        for vector in preference_vectors:
            if vector.embedding is not None:
                try:
                    # Convert pgvector to numpy array
                    pref_vector = np.array(vector.embedding.tolist(), dtype=np.float32)
                    if pref_vector.shape != (settings.VECTOR_DIMENSIONS,):
                        logger.error(f"Invalid vector shape for preference vector {vector.id}: {pref_vector.shape}")
                        continue
                    all_embeddings.append(pref_vector)
                    all_items.append(vector)
                    is_pref_vector.append(True)
                    logger.info(f"Added preference vector {vector.id} ({vector.title}) to UMAP input")
                except Exception as e:
                    logger.error(f"Error processing embedding for preference vector {vector.id}: {str(e)}")
                    continue

        if not all_embeddings:
            logger.warning("No valid embeddings found for UMAP visualization")
            return []

        try:
            # Create UMAP reducer
            reducer = umap.UMAP(
                n_components=2,
                random_state=42,
                metric='cosine',
                min_dist=0.1,
                n_neighbors=15
            )

            # Convert to numpy array and get UMAP coordinates for all points together
            embeddings_array = np.array(all_embeddings)
            umap_result = reducer.fit_transform(embeddings_array)
            
            # Create visualization data
            visualization_data = []
            
            # Process all points
            for i, (item, is_pref) in enumerate(zip(all_items, is_pref_vector)):
                try:
                    if is_pref:
                        # Add preference vector
                        visualization_data.append({
                            "id": f"pref_{item.id}",
                            "title": item.title,
                            "description": item.description,
                            "x": float(umap_result[i][0]),
                            "y": float(umap_result[i][1]),
                            "type": "preference_vector",
                            "opacity": 1.0
                        })
                        logger.info(f"Added preference vector {item.id} to visualization data at ({float(umap_result[i][0])}, {float(umap_result[i][1])})")
                    else:
                        # Add news item
                        last_seen = item.last_seen_at
                        if not last_seen.tzinfo:
                            last_seen = last_seen.replace(tzinfo=timezone.utc)
                        
                        if last_seen >= now - timedelta(hours=1):
                            opacity = 0.8
                        elif last_seen <= now - timedelta(days=1):
                            opacity = 0.2
                        else:
                            hours_old = (now - last_seen).total_seconds() / 3600
                            opacity = 0.8 - (0.6 * (hours_old - 1) / 23)
                        
                        cid = item_to_cluster.get(item.id)
                        visualization_data.append({
                            "id": item.id,
                            "title": item.title,
                            "url": item.url,
                            "source_url": item.source_url,
                            "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
                            "x": float(umap_result[i][0]),
                            "y": float(umap_result[i][1]),
                            "cluster_id": cid,
                            "cluster_name": cluster_names.get(cid) if cid is not None else None,
                            "type": "news_item",
                            "opacity": opacity
                        })
                except Exception as e:
                    logger.error(f"Error creating visualization data for item {i}: {str(e)}")
                    continue
            
            logger.info(f"Generated UMAP visualization with {len(visualization_data)} points")
            return visualization_data
            
        except Exception as e:
            logger.error(f"UMAP reduction error: {str(e)}\n{traceback.format_exc()}")
            raise
        
    except Exception as e:
        logger.error(f"UMAP visualization error: {str(e)}\n{traceback.format_exc()}")
        raise

async def update_visualizations(db: AsyncSession):
    """Update pre-generated visualizations using settings from config."""
    try:
        # Use settings from config
        hours = settings.VISUALIZATION_TIME_RANGE
        min_similarity = settings.VISUALIZATION_SIMILARITY
        
        try:
            # Generate UMAP visualization
            umap_data = await generate_umap_visualization(db, hours, min_similarity)
            
            # Check if UMAP visualization exists
            stmt = select(NewsUMAP).filter(
                NewsUMAP.hours == hours,
                NewsUMAP.min_similarity == min_similarity
            )
            result = await db.execute(stmt)
            existing_umap = result.scalar_one_or_none()
            
            if existing_umap:
                # Update existing visualization
                stmt = update(NewsUMAP).where(
                    NewsUMAP.hours == hours,
                    NewsUMAP.min_similarity == min_similarity
                ).values(
                    visualization=umap_data,
                    created_at=func.now()
                )
                await db.execute(stmt)
            else:
                # Create new visualization
                umap_viz = NewsUMAP(
                    hours=hours,
                    min_similarity=min_similarity,
                    visualization=umap_data
                )
                db.add(umap_viz)
            
            # Generate and store clusters
            clusters_data = await generate_clusters(db, hours, min_similarity)
            
            # Check if clusters exist
            stmt = select(NewsClusters).filter(
                NewsClusters.hours == hours,
                NewsClusters.min_similarity == min_similarity
            )
            result = await db.execute(stmt)
            existing_clusters = result.scalar_one_or_none()
            
            if existing_clusters:
                # Update existing clusters
                stmt = update(NewsClusters).where(
                    NewsClusters.hours == hours,
                    NewsClusters.min_similarity == min_similarity
                ).values(
                    clusters=clusters_data,
                    created_at=func.now()
                )
                await db.execute(stmt)
            else:
                # Create new clusters
                clusters = NewsClusters(
                    hours=hours,
                    min_similarity=min_similarity,
                    clusters=clusters_data
                )
                db.add(clusters)
                
        except Exception as e:
            logger.error(f"Error updating visualizations for {hours}h and {min_similarity} similarity: {str(e)}\n{traceback.format_exc()}")
            raise
        
        await db.commit()
        logger.info("Successfully updated all visualizations")
        
    except Exception as e:
        logger.error(f"Error updating visualizations: {str(e)}\n{traceback.format_exc()}")
        await db.rollback()
        raise
