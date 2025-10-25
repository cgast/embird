"""Common Pydantic schemas used across the API."""

from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    detail: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Resource not found", "Invalid request parameters"]
    )
    error_code: Optional[str] = Field(
        None,
        description="Machine-readable error code for client handling",
        examples=["RESOURCE_NOT_FOUND", "VALIDATION_ERROR"]
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the error occurred"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "News item not found",
                "error_code": "RESOURCE_NOT_FOUND",
                "timestamp": "2025-10-25T12:00:00Z"
            }
        }


class SuccessResponse(BaseModel):
    """Standard success response for operations without specific return data."""

    success: bool = Field(
        True,
        description="Indicates successful operation"
    )
    message: Optional[str] = Field(
        None,
        description="Optional success message",
        examples=["Operation completed successfully"]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "URL deleted successfully"
            }
        }


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    offset: int = Field(
        0,
        ge=0,
        description="Number of items to skip",
        examples=[0, 20, 100]
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of items to return (1-1000)",
        examples=[10, 50, 100]
    )


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: List[T] = Field(
        ...,
        description="List of items for current page"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of items available"
    )
    offset: int = Field(
        ...,
        ge=0,
        description="Current offset"
    )
    limit: int = Field(
        ...,
        ge=1,
        description="Items per page"
    )
    has_more: bool = Field(
        ...,
        description="Whether more items are available"
    )

    @classmethod
    def create(cls, items: List[T], total: int, offset: int, limit: int):
        """Factory method to create paginated response."""
        return cls(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
            has_more=(offset + len(items)) < total
        )


class HealthCheckResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(
        ...,
        description="Overall system status",
        examples=["healthy", "degraded", "unhealthy"]
    )
    version: str = Field(
        ...,
        description="Application version",
        examples=["1.0.0"]
    )
    services: Dict[str, str] = Field(
        ...,
        description="Status of individual services",
        examples=[{
            "database": "healthy",
            "faiss": "healthy",
            "embedding": "healthy"
        }]
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "services": {
                    "database": "healthy",
                    "faiss": "healthy",
                    "embedding": "healthy"
                },
                "timestamp": "2025-10-25T12:00:00Z"
            }
        }
