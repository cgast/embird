from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, validator
import numpy as np
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from pgvector.sqlalchemy import Vector

from app.models.news import Base

class PreferenceVectorBase(BaseModel):
    """Base model for PreferenceVector."""
    title: str
    description: str
    
    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @validator('description')
    def validate_description(cls, v):
        if not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip()

class PreferenceVectorCreate(PreferenceVectorBase):
    """Model for creating a new preference vector."""
    pass

class PreferenceVector(Base):
    """SQLAlchemy model for preference vectors in PostgreSQL."""
    __tablename__ = "preference_vectors"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=True)  # Using 1024 dimensions for Cohere embed-english-v3.0
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<PreferenceVector(id={self.id}, title={self.title})>"

class PreferenceVectorResponse(PreferenceVectorBase):
    """Model for returning a preference vector."""
    id: int
    embedding: Optional[List[float]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
