from datetime import datetime
from typing import List, Optional, Any, Dict
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, UniqueConstraint, JSON, Index
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
    last_seen_at = Column(DateTime(timezone=True), nullable=False, index=True)
    hit_count = Column(Integer, nullable=False, default=1)
    embedding = Column(Vector(1024), nullable=True)  # Using 1024 dimensions for Cohere embed-english-v3.0
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        # Add index on embedding for faster vector similarity calculations
        Index('idx_news_embedding', embedding, 
              postgresql_using='ivfflat',
              postgresql_ops={'embedding': 'vector_cosine_ops'},
              postgresql_with={'lists': 100}),
        # Add separate index on last_seen_at for faster timestamp filtering
        Index('idx_news_last_seen', last_seen_at.desc()),
    )
    
    def __repr__(self):
        return f"<NewsItem(id={self.id}, title={self.title}, url={self.url})>"


class NewsClusters(Base):
    """SQLAlchemy model for pre-generated news clusters."""
    __tablename__ = "news_clusters"
    
    id = Column(Integer, primary_key=True, index=True)
    hours = Column(Integer, nullable=False)
    min_similarity = Column(FLOAT, nullable=False)
    clusters = Column(JSON, nullable=False)  # Store clusters as JSON
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        # Add composite index for faster lookups of pre-generated clusters
        Index('idx_clusters_hours_similarity', hours, min_similarity),
        UniqueConstraint('hours', 'min_similarity', name='uix_hours_similarity'),
    )
    
    def __repr__(self):
        return f"<NewsClusters(hours={self.hours}, min_similarity={self.min_similarity})>"


class NewsUMAP(Base):
    """SQLAlchemy model for pre-generated UMAP visualizations."""
    __tablename__ = "news_umap"
    
    id = Column(Integer, primary_key=True, index=True)
    hours = Column(Integer, nullable=False)
    min_similarity = Column(FLOAT, nullable=False)  # Added min_similarity field
    visualization = Column(JSON, nullable=False)  # Store visualization data as JSON
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        # Add index on hours and min_similarity for faster lookups
        Index('idx_umap_hours_similarity', hours, min_similarity),
        UniqueConstraint('hours', 'min_similarity', name='uix_umap_hours_similarity'),
    )
    
    def __repr__(self):
        return f"<NewsUMAP(hours={self.hours}, min_similarity={self.min_similarity})>"


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
        model_exclude = {"embedding", "_sa_instance_state"}


class NewsClustersResponse(BaseModel):
    """Model for returning pre-generated clusters."""
    hours: int
    min_similarity: float
    clusters: Dict[int, List[NewsItemSimilarity]]
    created_at: datetime
    
    class Config:
        from_attributes = True


class NewsUMAPResponse(BaseModel):
    """Model for returning pre-generated UMAP visualization."""
    hours: int
    min_similarity: float
    visualization: List[dict]
    created_at: datetime
    
    class Config:
        from_attributes = True
