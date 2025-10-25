"""API routes with comprehensive OpenAPI documentation."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import List, Optional, Dict
import logging
from datetime import datetime, timedelta
import numpy as np

from app.models.url import URL, URLCreate, URLDatabase
from app.models.news import NewsItem, NewsClusters, NewsUMAP
from app.models.preference_vector import PreferenceVector
from app.schemas.news import (
    NewsItemResponse,
    NewsItemSimilarity,
    NewsSearchRequest,
    NewsTrendingParams,
)
from app.schemas.url import URLResponse, URLCreate as URLCreateSchema, URLDeleteResponse
from app.schemas.preference import (
    PreferenceVectorResponse,
    PreferenceVectorCreate,
    PreferenceVectorDetailResponse,
    PreferenceVectorUpdate,
    PreferenceVectorDeleteResponse
)
from app.schemas.common import ErrorResponse, SuccessResponse, HealthCheckResponse
from app.services.db import get_db, url_db
from app.services.embedding import get_embedding_service, EmbeddingService
from app.services.visualization import generate_clusters, generate_umap_visualization
from app.services.faiss_service import get_faiss_service
from app.config import settings

logger = logging.getLogger(__name__)

# Create router with tags for better organization
router = APIRouter(
    prefix="/api",
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {"model": ErrorResponse, "description": "Validation Error"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
)


# ============================================================================
# Health Check Endpoints
# ============================================================================

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["Health"],
    summary="Health check endpoint",
    description="Check the health status of EmBird services including database, FAISS index, and embedding service.",
    status_code=status.HTTP_200_OK
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthCheckResponse:
    """
    Perform a health check on all system components.

    Returns the overall system status and individual service statuses.
    Useful for monitoring and load balancer health checks.
    """
    services = {}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        services["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        services["database"] = "unhealthy"

    # Check FAISS service
    try:
        faiss_service = get_faiss_service()
        services["faiss"] = "healthy" if faiss_service.index.ntotal >= 0 else "unhealthy"
    except Exception as e:
        logger.error(f"FAISS health check failed: {e}")
        services["faiss"] = "unhealthy"

    # Check embedding service
    try:
        embedding_service = get_embedding_service()
        services["embedding"] = "healthy" if settings.COHERE_API_KEY else "degraded"
    except Exception as e:
        logger.error(f"Embedding service health check failed: {e}")
        services["embedding"] = "unhealthy"

    # Determine overall status
    if all(s == "healthy" for s in services.values()):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in services.values()):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return HealthCheckResponse(
        status=overall_status,
        version="1.0.0",
        services=services,
        timestamp=datetime.utcnow()
    )


# ============================================================================
# URL Management Endpoints
# ============================================================================

@router.get(
    "/urls",
    response_model=List[URLResponse],
    tags=["Sources"],
    summary="List all crawl sources",
    description="Retrieve all configured URLs (RSS feeds and homepages) that the crawler monitors.",
    status_code=status.HTTP_200_OK
)
async def get_urls() -> List[URLResponse]:
    """
    Get all configured crawl sources.

    Returns a list of all URLs that are being monitored by the crawler,
    including their type (RSS or homepage) and last crawl time.
    """
    return url_db.get_all_urls()


@router.post(
    "/urls",
    response_model=URLResponse,
    tags=["Sources"],
    summary="Add a new crawl source",
    description="Add a new RSS feed or homepage URL to the crawler's monitoring list.",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "URL created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid URL or duplicate"},
    }
)
async def create_url(url_data: URLCreateSchema) -> URLResponse:
    """
    Add a new URL source to the crawler.

    The crawler will begin monitoring this URL on its next scheduled run (hourly).

    - **url**: Full URL to the RSS feed or homepage
    - **type**: Either "rss" for RSS feeds or "homepage" for website homepages

    Returns the created URL with its assigned ID and timestamps.
    """
    try:
        url_obj = URLCreate(url=url_data.url, type=url_data.type)
        return url_db.add_url(url_obj)
    except Exception as e:
        logger.error(f"Error creating URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create URL: {str(e)}"
        )


@router.get(
    "/urls/{url_id}",
    response_model=URLResponse,
    tags=["Sources"],
    summary="Get a specific source by ID",
    description="Retrieve details for a specific crawl source by its ID.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "URL not found"},
    }
)
async def get_url(url_id: int) -> URLResponse:
    """
    Get details for a specific crawl source.

    - **url_id**: The unique identifier for the URL

    Returns the URL details including last crawl time.
    """
    url = url_db.get_url_by_id(url_id)
    if not url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"URL with ID {url_id} not found"
        )
    return url


@router.delete(
    "/urls/{url_id}",
    response_model=URLDeleteResponse,
    tags=["Sources"],
    summary="Delete a crawl source",
    description="Remove a URL from the crawler's monitoring list. Already crawled content will remain in the database.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "URL not found"},
    }
)
async def delete_url(url_id: int) -> URLDeleteResponse:
    """
    Delete a crawl source by ID.

    - **url_id**: The unique identifier for the URL to delete

    Note: Deleting a source does not delete news items already crawled from that source.
    """
    success = url_db.delete_url(url_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"URL with ID {url_id} not found"
        )
    return URLDeleteResponse(success=True, id=url_id)


# ============================================================================
# News Endpoints
# ============================================================================

@router.get(
    "/news",
    response_model=List[NewsItemResponse],
    tags=["News"],
    summary="List news items",
    description="Retrieve news items with optional filtering and pagination. Items are ordered by last seen timestamp.",
    status_code=status.HTTP_200_OK
)
async def get_news(
    db: AsyncSession = Depends(get_db),
    source_url: Optional[str] = Query(
        None,
        description="Filter by source URL (exact match)",
        examples=["https://techcrunch.com/feed/"]
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of items to return (1-1000)"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of items to skip for pagination"
    )
) -> List[NewsItemResponse]:
    """
    Get a list of news items with optional filtering.

    Results are ordered by `last_seen_at` in descending order (newest first).

    **Pagination:**
    - Use `offset` and `limit` to paginate through results
    - Example: offset=0, limit=100 returns items 1-100
    - Example: offset=100, limit=100 returns items 101-200

    **Filtering:**
    - Optionally filter by `source_url` to get news from a specific source
    """
    query = select(NewsItem).order_by(NewsItem.last_seen_at.desc())

    if source_url:
        query = query.filter(NewsItem.source_url == source_url)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    news_items = result.scalars().all()

    return news_items


@router.get(
    "/news/{news_id}",
    response_model=NewsItemResponse,
    tags=["News"],
    summary="Get a specific news item",
    description="Retrieve details for a specific news item by its ID.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "News item not found"},
    }
)
async def get_news_item(
    news_id: int,
    db: AsyncSession = Depends(get_db)
) -> NewsItemResponse:
    """
    Get details for a specific news item.

    - **news_id**: The unique identifier for the news item

    Returns the full news item including title, summary, URL, and timestamps.
    """
    result = await db.execute(select(NewsItem).filter(NewsItem.id == news_id))
    news_item = result.scalars().first()

    if not news_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"News item with ID {news_id} not found"
        )

    return news_item


@router.get(
    "/news/search",
    response_model=List[NewsItemSimilarity],
    tags=["News"],
    summary="Semantic search for news",
    description="Search news items using AI-powered semantic similarity. Finds articles related to your query even without exact keyword matches.",
    status_code=status.HTTP_200_OK,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid query or embedding generation failed"},
    }
)
async def search_news(
    query: str = Query(
        ...,
        min_length=1,
        max_length=500,
        description="Search query (semantic search using embeddings)",
        examples=["artificial intelligence breakthroughs", "climate change policy"]
    ),
    db: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )
) -> List[NewsItemSimilarity]:
    """
    Search for news articles using semantic similarity.

    This endpoint uses AI embeddings to find articles semantically related to your query,
    even if they don't contain the exact keywords.

    **How it works:**
    1. Your query is converted to a 1024-dimensional embedding vector
    2. FAISS performs fast similarity search against all news embeddings
    3. Results are ranked by cosine similarity score (0.0 to 1.0)

    **Tips:**
    - Use natural language queries (e.g., "renewable energy developments")
    - Longer, more specific queries often yield better results
    - Similarity scores above 0.7 indicate strong relevance

    Returns news items with similarity scores in descending order.
    """
    # Validate query
    if not query or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search query cannot be empty"
        )

    # Clean query
    query = query.strip()

    try:
        # Verify API key is configured
        if not settings.COHERE_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cohere API key not configured. Please set COHERE_API_KEY environment variable."
            )

        # Generate embedding for the query
        query_embedding = await embedding_service.get_embedding(query)

        if not query_embedding:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to generate embedding for query"
            )

        # Get FAISS service
        faiss_service = get_faiss_service()

        # Search using FAISS
        similar_items = await faiss_service.search_similar(
            db,
            np.array(query_embedding, dtype=np.float32),
            k=limit,
            min_similarity=0.5
        )

        if similar_items:
            # Get full news items from database
            item_ids = [item_id for item_id, _ in similar_items]
            stmt = select(NewsItem).filter(NewsItem.id.in_(item_ids))
            result = await db.execute(stmt)
            db_items = {item.id: item for item in result.scalars().all()}

            # Create NewsItemSimilarity objects
            news_items = []
            for item_id, similarity in similar_items:
                if item_id in db_items:
                    db_item = db_items[item_id]
                    item_data = {
                        'id': db_item.id,
                        'title': db_item.title,
                        'summary': db_item.summary,
                        'url': db_item.url,
                        'source_url': db_item.source_url,
                        'first_seen_at': db_item.first_seen_at,
                        'last_seen_at': db_item.last_seen_at,
                        'hit_count': db_item.hit_count,
                        'created_at': db_item.created_at,
                        'updated_at': db_item.updated_at,
                        'similarity': similarity
                    }
                    response_item = NewsItemSimilarity.model_validate(item_data)
                    news_items.append(response_item)

            return news_items

        # If no results from FAISS, fall back to database search
        vector_str = f"[{','.join(str(x) for x in query_embedding)}]"

        stmt = text("""
            SELECT
                id, title, summary, url, source_url,
                first_seen_at, last_seen_at, hit_count,
                created_at, updated_at,
                cosine_distance(embedding, cast(:vector as vector(1024))) as distance
            FROM news
            WHERE embedding IS NOT NULL
            ORDER BY cosine_distance(embedding, cast(:vector as vector(1024)))
            LIMIT :limit
        """)

        result = await db.execute(
            stmt,
            {
                "vector": vector_str,
                "limit": limit
            }
        )

        news_items = []
        for row in result:
            news_item = NewsItem(
                id=row.id,
                title=row.title,
                summary=row.summary,
                url=row.url,
                source_url=row.source_url,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
                hit_count=row.hit_count,
                created_at=row.created_at,
                updated_at=row.updated_at
            )

            item_data = news_item.__dict__.copy()
            item_data['similarity'] = (1.0 - float(row.distance)) / 2.0
            response_item = NewsItemSimilarity.model_validate(item_data)
            news_items.append(response_item)

        return news_items

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Search failed: {str(e)}"
        )


@router.get(
    "/news/trending",
    response_model=List[NewsItemResponse],
    tags=["News"],
    summary="Get trending news",
    description="Retrieve trending news items based on hit count within a specified time window.",
    status_code=status.HTTP_200_OK
)
async def get_trending_news(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of trending items to return"
    ),
    hours: int = Query(
        24,
        ge=1,
        le=168,
        description="Time window in hours (default: 24, max: 168 = 1 week)"
    )
) -> List[NewsItemResponse]:
    """
    Get trending news based on hit count.

    Articles are ranked by how many times they've been seen during crawls
    within the specified time window. Higher hit counts indicate the article
    appeared in multiple sources or was republished.

    **Parameters:**
    - **limit**: Number of trending items to return (1-100)
    - **hours**: Time window to consider (1-168 hours)

    Results are ordered by hit_count (descending) then last_seen_at (descending).
    """
    # Get current time minus specified hours
    time_filter = func.now() - func.make_interval(hours=hours)

    query = select(NewsItem).filter(
        NewsItem.last_seen_at >= time_filter
    ).order_by(
        NewsItem.hit_count.desc(),
        NewsItem.last_seen_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    news_items = result.scalars().all()

    return news_items


@router.get(
    "/news/clusters",
    response_model=Dict[str, List[Dict]],
    tags=["News"],
    summary="Get news clusters",
    description="Retrieve automatically grouped clusters of similar news articles using FAISS-powered transitive clustering.",
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Clustering failed"},
    }
)
async def get_news_clusters(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, List[Dict]]:
    """
    Get clustered news items based on vector similarity.

    This endpoint uses FAISS to automatically group related news articles
    into clusters using transitive similarity matching.

    **How it works:**
    1. Loads recent news embeddings (last 48 hours by default)
    2. Performs similarity search for each article
    3. Groups articles that are mutually similar (transitive clustering)
    4. Returns clusters with similarity scores

    **Configuration:**
    - Time range: Set via VISUALIZATION_TIME_RANGE (default: 48 hours)
    - Similarity threshold: Set via VISUALIZATION_SIMILARITY (default: 0.55)

    **Response format:**
    ```json
    {
      "0": [
        {"id": 1, "title": "Article 1", "similarity": 0.95, ...},
        {"id": 2, "title": "Related Article", "similarity": 0.87, ...}
      ],
      "1": [...]
    }
    ```

    Returns a dictionary mapping cluster IDs (as strings) to lists of news items.
    """
    try:
        # Try to get pre-generated clusters
        result = await db.execute(
            select(NewsClusters).filter(
                NewsClusters.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsClusters.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsClusters.created_at.desc())
        )
        clusters = result.scalars().first()

        if clusters:
            cluster_data = clusters.clusters
        else:
            # If no pre-generated clusters, generate them now
            cluster_data = await generate_clusters(db)

            # Store the newly generated clusters in the database
            new_clusters = NewsClusters(
                hours=settings.VISUALIZATION_TIME_RANGE,
                min_similarity=settings.VISUALIZATION_SIMILARITY,
                clusters=cluster_data
            )
            db.add(new_clusters)
            await db.commit()

        # Convert to dictionary with string keys and serialized items
        serialized_clusters = {}
        for cluster_id, items in cluster_data.items():
            serialized_items = []
            for item in items:
                # Handle both dictionaries and objects
                if isinstance(item, dict):
                    # Use get() for all fields to handle missing values safely
                    item_dict = {
                        'id': item.get('id', 0),
                        'title': item.get('title', ''),
                        'summary': item.get('summary', None),
                        'url': item.get('url', ''),
                        'source_url': item.get('source_url', ''),
                        'similarity': item.get('similarity', 0.0),
                        'hit_count': item.get('hit_count', 1),
                    }

                    # Handle datetime fields carefully
                    first_seen = item.get('first_seen_at')
                    if first_seen:
                        item_dict['first_seen_at'] = first_seen.isoformat() if hasattr(first_seen, 'isoformat') else first_seen
                    else:
                        item_dict['first_seen_at'] = datetime.now().isoformat()

                    last_seen = item.get('last_seen_at')
                    if last_seen:
                        item_dict['last_seen_at'] = last_seen.isoformat() if hasattr(last_seen, 'isoformat') else last_seen
                    else:
                        item_dict['last_seen_at'] = datetime.now().isoformat()

                    created_at = item.get('created_at')
                    if created_at:
                        item_dict['created_at'] = created_at.isoformat() if hasattr(created_at, 'isoformat') else created_at
                    else:
                        item_dict['created_at'] = datetime.now().isoformat()

                    updated_at = item.get('updated_at')
                    if updated_at:
                        item_dict['updated_at'] = updated_at.isoformat() if hasattr(updated_at, 'isoformat') else updated_at
                    else:
                        item_dict['updated_at'] = datetime.now().isoformat()
                else:
                    item_dict = {
                        'id': item.id,
                        'title': item.title,
                        'summary': item.summary,
                        'url': item.url,
                        'source_url': item.source_url,
                        'similarity': item.similarity,
                        'first_seen_at': item.first_seen_at.isoformat() if hasattr(item.first_seen_at, 'isoformat') else item.first_seen_at,
                        'last_seen_at': item.last_seen_at.isoformat() if hasattr(item.last_seen_at, 'isoformat') else item.last_seen_at,
                        'hit_count': item.hit_count,
                        'created_at': item.created_at.isoformat() if hasattr(item.created_at, 'isoformat') else item.created_at,
                        'updated_at': item.updated_at.isoformat() if hasattr(item.updated_at, 'isoformat') else item.updated_at
                    }
                serialized_items.append(item_dict)

            # Convert numeric cluster_id to string for JSON compatibility
            serialized_clusters[str(cluster_id)] = serialized_items

        return serialized_clusters

    except Exception as e:
        logger.error(f"Clustering error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate clusters: {str(e)}"
        )


@router.get(
    "/news/umap",
    response_model=List[dict],
    tags=["News"],
    summary="Get UMAP visualization data",
    description="Get 2D UMAP projection of news embeddings for visualization. Shows relationships between articles in 2D space.",
    status_code=status.HTTP_200_OK,
    responses={
        500: {"model": ErrorResponse, "description": "Visualization generation failed"},
    }
)
async def get_news_umap(
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """
    Get UMAP visualization data for news items.

    UMAP (Uniform Manifold Approximation and Projection) reduces the 1024-dimensional
    news embeddings to 2D points that can be visualized, preserving semantic relationships.

    **Use case:**
    - Visualize news landscape at a glance
    - Identify topic clusters visually
    - Explore relationships between different news stories

    **How it works:**
    1. Loads recent news embeddings (configured time range)
    2. Applies UMAP dimensionality reduction (1024D → 2D)
    3. Returns x,y coordinates for each article along with metadata

    **Configuration:**
    - Time range: VISUALIZATION_TIME_RANGE (default: 48 hours)
    - Similarity threshold: VISUALIZATION_SIMILARITY (default: 0.55)

    **Response:** Array of news items with x, y coordinates for plotting.

    Note: UMAP generation is computationally expensive. Results are cached
    in the database and regenerated periodically.
    """
    try:
        # Try to get pre-generated visualization
        result = await db.execute(
            select(NewsUMAP).filter(
                NewsUMAP.hours == settings.VISUALIZATION_TIME_RANGE,
                NewsUMAP.min_similarity == settings.VISUALIZATION_SIMILARITY
            ).order_by(NewsUMAP.created_at.desc())
        )
        umap_data = result.scalars().first()

        if umap_data:
            return umap_data.visualization

        # If no pre-generated data, generate it now
        return await generate_umap_visualization(db)

    except Exception as e:
        logger.error(f"UMAP visualization error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate UMAP visualization: {str(e)}"
        )


# ============================================================================
# Preference Vector Endpoints
# ============================================================================

@router.get(
    "/preferences",
    response_model=List[PreferenceVectorResponse],
    tags=["Preferences"],
    summary="List preference vectors",
    description="Get all user preference vectors used for personalized news ranking.",
    status_code=status.HTTP_200_OK
)
async def list_preference_vectors(
    db: AsyncSession = Depends(get_db)
) -> List[PreferenceVectorResponse]:
    """
    List all preference vectors.

    Preference vectors represent user interests and are used to rank news items
    on the homepage. Each vector is an embedding generated from a text description
    of the user's interests.

    Returns preference vectors without embedding data (use GET /preferences/{id} for full data).
    """
    result = await db.execute(select(PreferenceVector))
    vectors = result.scalars().all()
    return vectors


@router.post(
    "/preferences",
    response_model=PreferenceVectorDetailResponse,
    tags=["Preferences"],
    summary="Create a preference vector",
    description="Create a new preference vector from a text description of your interests.",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Preference vector created successfully"},
        422: {"model": ErrorResponse, "description": "Failed to generate embedding"},
    }
)
async def create_preference_vector(
    vector_data: PreferenceVectorCreate,
    db: AsyncSession = Depends(get_db)
) -> PreferenceVectorDetailResponse:
    """
    Create a new preference vector.

    The description will be converted to a 1024-dimensional embedding vector
    using the Cohere API. This vector is then used to calculate similarity
    with news articles for personalized ranking.

    **Example descriptions:**
    - "I'm interested in artificial intelligence, machine learning, and robotics"
    - "Climate change research, renewable energy, and environmental policy"
    - "Financial markets, cryptocurrency, and economic indicators"

    **Tips:**
    - Be specific about your interests
    - Include related topics and synonyms
    - Longer descriptions (2-3 sentences) work better

    Returns the created preference vector including the embedding.
    """
    try:
        # Get embedding service
        embedding_service = get_embedding_service()

        # Generate embedding from description
        embedding = await embedding_service.get_embedding(vector_data.description)

        if not embedding:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to generate embedding for description"
            )

        # Create vector with embedding
        vector = PreferenceVector(
            title=vector_data.title,
            description=vector_data.description,
            embedding=embedding
        )
        db.add(vector)
        await db.commit()
        await db.refresh(vector)

        return vector

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating preference vector: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to create preference vector: {str(e)}"
        )


@router.get(
    "/preferences/{vector_id}",
    response_model=PreferenceVectorDetailResponse,
    tags=["Preferences"],
    summary="Get a specific preference vector",
    description="Retrieve details for a specific preference vector including its embedding.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Preference vector not found"},
    }
)
async def get_preference_vector(
    vector_id: int,
    db: AsyncSession = Depends(get_db)
) -> PreferenceVectorDetailResponse:
    """
    Get a specific preference vector by ID.

    Returns the full preference vector including the 1024-dimensional embedding.
    """
    result = await db.execute(
        select(PreferenceVector).filter(PreferenceVector.id == vector_id)
    )
    vector = result.scalar_one_or_none()

    if not vector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference vector with ID {vector_id} not found"
        )

    return vector


@router.put(
    "/preferences/{vector_id}",
    response_model=PreferenceVectorDetailResponse,
    tags=["Preferences"],
    summary="Update a preference vector",
    description="Update an existing preference vector's title and/or description. Updating the description will regenerate the embedding.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Preference vector not found"},
        422: {"model": ErrorResponse, "description": "Failed to generate embedding"},
    }
)
async def update_preference_vector(
    vector_id: int,
    vector_data: PreferenceVectorUpdate,
    db: AsyncSession = Depends(get_db)
) -> PreferenceVectorDetailResponse:
    """
    Update a preference vector.

    You can update the title, description, or both. If the description is updated,
    a new embedding will be generated automatically.

    **Note:** Changing the description will affect which news items are ranked
    highly for this preference.
    """
    try:
        # Get existing vector
        result = await db.execute(
            select(PreferenceVector).filter(PreferenceVector.id == vector_id)
        )
        vector = result.scalar_one_or_none()

        if not vector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preference vector with ID {vector_id} not found"
            )

        # Update fields
        if vector_data.title is not None:
            vector.title = vector_data.title

        if vector_data.description is not None:
            # Generate new embedding
            embedding_service = get_embedding_service()
            embedding = await embedding_service.get_embedding(vector_data.description)

            if not embedding:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Failed to generate embedding for updated description"
                )

            vector.description = vector_data.description
            vector.embedding = embedding

        vector.updated_at = func.now()
        await db.commit()
        await db.refresh(vector)

        return vector

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preference vector: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to update preference vector: {str(e)}"
        )


@router.delete(
    "/preferences/{vector_id}",
    response_model=PreferenceVectorDeleteResponse,
    tags=["Preferences"],
    summary="Delete a preference vector",
    description="Remove a preference vector from the system.",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Preference vector not found"},
    }
)
async def delete_preference_vector(
    vector_id: int,
    db: AsyncSession = Depends(get_db)
) -> PreferenceVectorDeleteResponse:
    """
    Delete a preference vector by ID.

    This will remove the preference vector from personalized news ranking.
    """
    result = await db.execute(
        select(PreferenceVector).filter(PreferenceVector.id == vector_id)
    )
    vector = result.scalar_one_or_none()

    if not vector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference vector with ID {vector_id} not found"
        )

    await db.delete(vector)
    await db.commit()

    return PreferenceVectorDeleteResponse(success=True, id=vector_id)
