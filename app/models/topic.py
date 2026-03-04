"""Topic model for multi-topic support."""
import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, validator
from sqlalchemy import Column, Integer, String, Text, DateTime, func

from app.models.news import Base


class Topic(Base):
    """SQLAlchemy model for topics in PostgreSQL."""
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Topic(id={self.id}, name={self.name}, slug={self.slug})>"


# Pydantic models

class TopicBase(BaseModel):
    """Base model for topics."""
    name: str
    slug: str
    description: Optional[str] = None

    @validator('slug')
    def validate_slug(cls, v):
        v = v.strip().lower()
        if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        if len(v) < 1 or len(v) > 100:
            raise ValueError('Slug must be between 1 and 100 characters')
        return v

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()


class TopicCreate(TopicBase):
    """Model for creating a new topic."""
    pass


class TopicResponse(TopicBase):
    """Model for returning a topic."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
