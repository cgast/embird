"""Preference vector Pydantic schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class PreferenceVectorBase(BaseModel):
    """Base schema for preference vectors."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short, descriptive title for the preference vector",
        examples=["Technology News", "Climate Science", "Financial Markets"]
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Detailed description of the user's interests (used to generate embedding)",
        examples=[
            "I'm interested in artificial intelligence, machine learning, and deep learning breakthroughs",
            "Climate change research, environmental policy, and renewable energy developments"
        ]
    )

    @field_validator('title', 'description')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that fields are not empty or whitespace."""
        v = v.strip()
        if not v:
            raise ValueError('Field cannot be empty or whitespace')
        return v


class PreferenceVectorCreate(PreferenceVectorBase):
    """Schema for creating a new preference vector."""

    class Config:
        json_schema_extra = {
            "example": {
                "title": "AI & Machine Learning",
                "description": "Latest developments in artificial intelligence, neural networks, and machine learning applications"
            }
        }


class PreferenceVectorUpdate(BaseModel):
    """Schema for updating a preference vector."""

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Updated title"
    )
    description: Optional[str] = Field(
        None,
        min_length=1,
        max_length=5000,
        description="Updated description (will regenerate embedding)"
    )

    @field_validator('title', 'description')
    @classmethod
    def validate_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate that fields are not empty if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('Field cannot be empty or whitespace')
        return v


class PreferenceVectorResponse(PreferenceVectorBase):
    """Schema for preference vector response."""

    id: int = Field(
        ...,
        description="Unique identifier for the preference vector",
        examples=[1, 5, 42]
    )
    embedding: Optional[List[float]] = Field(
        None,
        description="1024-dimensional embedding vector (typically not returned in list views)",
        exclude=True  # Exclude from serialization by default to reduce payload size
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the preference vector was created"
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when the preference vector was last updated"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 5,
                "title": "AI & Machine Learning",
                "description": "Latest developments in artificial intelligence, neural networks, and machine learning applications",
                "created_at": "2025-10-20T10:00:00Z",
                "updated_at": "2025-10-25T12:00:00Z"
            }
        }


class PreferenceVectorDetailResponse(PreferenceVectorResponse):
    """Schema for detailed preference vector response (includes embedding)."""

    embedding: Optional[List[float]] = Field(
        None,
        min_length=1024,
        max_length=1024,
        description="1024-dimensional embedding vector (Cohere embed-english-v3.0)"
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 5,
                "title": "AI & Machine Learning",
                "description": "Latest developments in AI...",
                "embedding": [0.123, -0.456, 0.789, "... (1024 dimensions)"],
                "created_at": "2025-10-20T10:00:00Z",
                "updated_at": "2025-10-25T12:00:00Z"
            }
        }


class PreferenceVectorDeleteResponse(BaseModel):
    """Schema for preference vector deletion response."""

    success: bool = Field(
        True,
        description="Indicates successful deletion"
    )
    id: int = Field(
        ...,
        description="ID of the deleted preference vector"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "id": 5
            }
        }
