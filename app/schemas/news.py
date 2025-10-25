"""News-related Pydantic schemas."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


class NewsItemBase(BaseModel):
    """Base schema for news items."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="News article title",
        examples=["Breaking: Major Development in AI Research"]
    )
    summary: Optional[str] = Field(
        None,
        max_length=5000,
        description="News article summary or excerpt",
        examples=["Scientists announce breakthrough in natural language processing..."]
    )
    url: str = Field(
        ...,
        description="URL to the original article",
        examples=["https://example.com/news/article-123"]
    )
    source_url: str = Field(
        ...,
        description="URL of the source (RSS feed or homepage)",
        examples=["https://example.com/rss", "https://example.com"]
    )

    @field_validator('url', 'source_url')
    @classmethod
    def validate_urls(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class NewsItemCreate(NewsItemBase):
    """Schema for creating a news item."""

    embedding: Optional[List[float]] = Field(
        None,
        min_length=1024,
        max_length=1024,
        description="1024-dimensional embedding vector (Cohere embed-english-v3.0)"
    )


class NewsItemResponse(NewsItemBase):
    """Schema for news item response."""

    id: int = Field(
        ...,
        description="Unique identifier for the news item",
        examples=[12345]
    )
    first_seen_at: datetime = Field(
        ...,
        description="Timestamp when the article was first discovered"
    )
    last_seen_at: datetime = Field(
        ...,
        description="Timestamp when the article was last seen during crawling"
    )
    hit_count: int = Field(
        ...,
        ge=1,
        description="Number of times this article was encountered",
        examples=[1, 5, 10]
    )
    created_at: datetime = Field(
        ...,
        description="Database record creation timestamp"
    )
    updated_at: datetime = Field(
        ...,
        description="Database record last update timestamp"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 12345,
                "title": "AI Breakthrough: New Language Model Sets Records",
                "summary": "Researchers unveil a revolutionary approach to natural language understanding...",
                "url": "https://technews.example.com/ai-breakthrough-2025",
                "source_url": "https://technews.example.com/rss",
                "first_seen_at": "2025-10-25T08:00:00Z",
                "last_seen_at": "2025-10-25T12:00:00Z",
                "hit_count": 3,
                "created_at": "2025-10-25T08:00:00Z",
                "updated_at": "2025-10-25T12:00:00Z"
            }
        }


class NewsItemSimilarity(NewsItemResponse):
    """Schema for news item with similarity score."""

    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity score (0.0 to 1.0)",
        examples=[0.85, 0.92, 0.78]
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 12345,
                "title": "AI Breakthrough: New Language Model Sets Records",
                "summary": "Researchers unveil a revolutionary approach...",
                "url": "https://technews.example.com/ai-breakthrough-2025",
                "source_url": "https://technews.example.com/rss",
                "first_seen_at": "2025-10-25T08:00:00Z",
                "last_seen_at": "2025-10-25T12:00:00Z",
                "hit_count": 3,
                "created_at": "2025-10-25T08:00:00Z",
                "updated_at": "2025-10-25T12:00:00Z",
                "similarity": 0.92
            }
        }


class NewsSearchRequest(BaseModel):
    """Schema for news search request."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query (semantic search using embeddings)",
        examples=["artificial intelligence breakthroughs", "climate change policy"]
    )
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum number of results to return",
        examples=[10, 20, 50]
    )
    min_similarity: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for results",
        examples=[0.5, 0.7, 0.8]
    )

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and clean query."""
        v = v.strip()
        if not v:
            raise ValueError('Query cannot be empty or whitespace')
        return v


class NewsSearchResponse(BaseModel):
    """Schema for news search response."""

    query: str = Field(
        ...,
        description="The search query that was executed"
    )
    results: List[NewsItemSimilarity] = Field(
        ...,
        description="List of matching news items with similarity scores"
    )
    total_results: int = Field(
        ...,
        ge=0,
        description="Total number of results found"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "artificial intelligence",
                "results": [
                    {
                        "id": 12345,
                        "title": "AI Breakthrough: New Language Model",
                        "similarity": 0.92,
                        "url": "https://example.com/article"
                    }
                ],
                "total_results": 15
            }
        }


class NewsClusterItem(BaseModel):
    """Schema for a news item within a cluster."""

    id: int = Field(..., description="News item ID")
    title: str = Field(..., description="News item title")
    summary: Optional[str] = Field(None, description="News item summary")
    url: str = Field(..., description="Article URL")
    source_url: str = Field(..., description="Source URL")
    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity to cluster centroid"
    )
    hit_count: int = Field(..., ge=1, description="Hit count")
    first_seen_at: str = Field(..., description="First seen timestamp (ISO format)")
    last_seen_at: str = Field(..., description="Last seen timestamp (ISO format)")
    created_at: str = Field(..., description="Created timestamp (ISO format)")
    updated_at: str = Field(..., description="Updated timestamp (ISO format)")


class NewsClusterResponse(BaseModel):
    """Schema for news clusters response."""

    clusters: Dict[str, List[NewsClusterItem]] = Field(
        ...,
        description="Dictionary mapping cluster IDs to lists of news items"
    )
    hours: int = Field(
        ...,
        description="Time range in hours used for clustering"
    )
    min_similarity: float = Field(
        ...,
        description="Minimum similarity threshold used"
    )
    total_clusters: int = Field(
        ...,
        ge=0,
        description="Total number of clusters found"
    )
    total_items: int = Field(
        ...,
        ge=0,
        description="Total number of news items across all clusters"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "clusters": {
                    "0": [
                        {
                            "id": 1,
                            "title": "AI Research Breakthrough",
                            "similarity": 0.95,
                            "url": "https://example.com/article1"
                        }
                    ]
                },
                "hours": 48,
                "min_similarity": 0.55,
                "total_clusters": 15,
                "total_items": 87
            }
        }


class NewsUMAPPoint(BaseModel):
    """Schema for a single UMAP visualization point."""

    id: int = Field(..., description="News item ID")
    title: str = Field(..., description="News item title")
    url: str = Field(..., description="Article URL")
    source_url: str = Field(..., description="Source URL")
    x: float = Field(..., description="X coordinate in 2D UMAP space")
    y: float = Field(..., description="Y coordinate in 2D UMAP space")
    cluster_id: Optional[int] = Field(
        None,
        description="Cluster ID if this point belongs to a cluster"
    )
    timestamp: str = Field(..., description="Article timestamp (ISO format)")


class NewsUMAPResponse(BaseModel):
    """Schema for UMAP visualization response."""

    points: List[NewsUMAPPoint] = Field(
        ...,
        description="List of news items with 2D coordinates"
    )
    hours: int = Field(
        ...,
        description="Time range in hours used for visualization"
    )
    total_points: int = Field(
        ...,
        ge=0,
        description="Total number of points in visualization"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "points": [
                    {
                        "id": 1,
                        "title": "AI Breakthrough",
                        "url": "https://example.com/article",
                        "source_url": "https://example.com/rss",
                        "x": 0.23,
                        "y": -0.45,
                        "cluster_id": 0,
                        "timestamp": "2025-10-25T12:00:00Z"
                    }
                ],
                "hours": 48,
                "total_points": 250
            }
        }


class NewsTrendingParams(BaseModel):
    """Schema for trending news parameters."""

    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum number of trending items to return"
    )
    hours: int = Field(
        24,
        ge=1,
        le=168,
        description="Time window in hours (max 1 week)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "limit": 20,
                "hours": 48
            }
        }
