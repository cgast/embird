from datetime import datetime
from typing import List, Optional, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, UniqueConstraint, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY, FLOAT
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel

Base = declarative_base()

class NewsItem(Base):
    """SQLAlchemy model for news items in PostgreSQL."""
    __tablename__ = "news"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    url = Column(String, nullable=False, unique=True)
    source_url = Column(String, nullable=False, index=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    hit_count = Column(Integer, nullable=False, default=1)
    embedding = Column(Vector(1024), nullable=True)  # Using 1024 dimensions for Cohere embed-english-v3.0
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<NewsItem(id={self.id}, title={self.title}, url={self.url})>"


class NewsUMAP(Base):
    """SQLAlchemy model for pre-generated UMAP visualizations."""
    __tablename__ = "news_umap"
    
    id = Column(Integer, primary_key=True, index=True)
    hours = Column(Integer, nullable=False, unique=True)
    visualization = Column(JSON, nullable=False)  # Store visualization data as JSON
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    def __repr__(self):
        return f"<NewsUMAP(hours={self.hours})>"



class NewsClusters(Base):
    """SQLAlchemy model for pre-generated news clusters."""
    __tablename__ = "news_clusters"
    
    id = Column(Integer, primary_key=True, index=True)
    hours = Column(Integer, nullable=False)
    min_similarity = Column(FLOAT, nullable=False)
    clusters = Column(JSON, nullable=False)  # Store clusters as JSON
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('hours', 'min_similarity', name='uix_hours_similarity'),
    )
    
    def __repr__(self):
        return f"<NewsClusters(hours={self.hours}, min_similarity={self.min_similarity})>"


# Pydantic models for API
class NewsItemBase(BaseModel):
    """Base model for news items."""
    title: str
    summary: Optional[str] = None
    url: str
    source_url: str


class NewsItemCreate(NewsItemBase):
    """Model for creating a new news item."""
    embedding: Optional[List[float]] = None


class NewsItemResponse(NewsItemBase):
    """Model for returning a news item."""
    id: int
    first_seen_at: datetime
    last_seen_at: datetime
    hit_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class NewsItemSimilarity(NewsItemResponse):
    """Model for returning a news item with similarity score."""
    similarity: float
    
    class Config:
        from_attributes = True
