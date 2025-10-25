"""URL management Pydantic schemas."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class URLBase(BaseModel):
    """Base schema for URLs."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL to crawl (RSS feed or homepage)",
        examples=[
            "https://techcrunch.com/feed/",
            "https://news.ycombinator.com/rss",
            "https://example.com"
        ]
    )
    type: Literal["rss", "homepage"] = Field(
        ...,
        description="Type of URL: 'rss' for RSS feeds, 'homepage' for website homepages",
        examples=["rss", "homepage"]
    )

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class URLCreate(URLBase):
    """Schema for creating a new URL."""

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://techcrunch.com/feed/",
                "type": "rss"
            }
        }


class URLUpdate(BaseModel):
    """Schema for updating a URL."""

    url: Optional[str] = Field(
        None,
        min_length=1,
        max_length=2048,
        description="Updated URL"
    )
    type: Optional[Literal["rss", "homepage"]] = Field(
        None,
        description="Updated type"
    )

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate URL format if provided."""
        if v is not None:
            v = v.strip()
            if not v.startswith(('http://', 'https://')):
                raise ValueError('URL must start with http:// or https://')
        return v


class URLResponse(URLBase):
    """Schema for URL response."""

    id: int = Field(
        ...,
        description="Unique identifier for the URL",
        examples=[1, 42, 123]
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the URL was added to the system"
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the URL was last modified"
    )
    last_crawled_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the URL was last crawled (null if never crawled)"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 42,
                "url": "https://techcrunch.com/feed/",
                "type": "rss",
                "created_at": "2025-10-20T10:00:00Z",
                "updated_at": "2025-10-25T12:00:00Z",
                "last_crawled_at": "2025-10-25T11:30:00Z"
            }
        }


class URLDeleteResponse(BaseModel):
    """Schema for URL deletion response."""

    success: bool = Field(
        True,
        description="Indicates successful deletion"
    )
    id: int = Field(
        ...,
        description="ID of the deleted URL"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "id": 42
            }
        }
