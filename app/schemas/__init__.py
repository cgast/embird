"""
Pydantic schemas for EmBird API.

This module provides comprehensive request/response validation and OpenAPI documentation.
"""

from app.schemas.common import (
    ErrorResponse,
    SuccessResponse,
    PaginationParams,
    PaginatedResponse,
    HealthCheckResponse
)
from app.schemas.news import (
    NewsItemBase,
    NewsItemCreate,
    NewsItemResponse,
    NewsItemSimilarity,
    NewsSearchRequest,
    NewsSearchResponse,
    NewsClusterItem,
    NewsClusterResponse,
    NewsUMAPPoint,
    NewsUMAPResponse,
    NewsTrendingParams
)
from app.schemas.url import (
    URLBase,
    URLCreate,
    URLResponse,
    URLUpdate
)
from app.schemas.preference import (
    PreferenceVectorBase,
    PreferenceVectorCreate,
    PreferenceVectorResponse,
    PreferenceVectorUpdate
)

__all__ = [
    # Common
    "ErrorResponse",
    "SuccessResponse",
    "PaginationParams",
    "PaginatedResponse",
    "HealthCheckResponse",
    # News
    "NewsItemBase",
    "NewsItemCreate",
    "NewsItemResponse",
    "NewsItemSimilarity",
    "NewsSearchRequest",
    "NewsSearchResponse",
    "NewsClusterItem",
    "NewsClusterResponse",
    "NewsUMAPPoint",
    "NewsUMAPResponse",
    "NewsTrendingParams",
    # URL
    "URLBase",
    "URLCreate",
    "URLResponse",
    "URLUpdate",
    # Preference
    "PreferenceVectorBase",
    "PreferenceVectorCreate",
    "PreferenceVectorResponse",
    "PreferenceVectorUpdate",
]
