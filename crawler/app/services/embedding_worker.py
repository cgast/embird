"""
Worker service that runs continuously to manage embeddings and vector operations
"""
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import json

from app.config import settings
from app.models.news import NewsItem, NewsClusters, NewsUMAP
from app.services.embedding import EmbeddingService
from app.services.redis_client import get_redis_client
from app.services.visualization import generate_umap_visualization

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up PostgreSQL connection
pg_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False
)
AsyncSessionLocal = sessionmaker(pg_engine, expire_on_commit=False, class_=AsyncSession)

class EmbeddingWorker:
    """Worker service for managing embeddings and vector operations."""
    
    def __init__(self):
        """Initialize the embedding worker."""
        self.embedding_service = EmbeddingService(settings.COHERE_API_KEY)
        self.running = False
    
    async def sync_vectors_to_redis(self):
        """Sync recent vectors from PostgreSQL to Redis."""
        try:
            async with AsyncSessionLocal() as session:
                # Get recent news items (last 24 hours)
                time_filter = datetime.utcnow() - timedelta(hours=settings.REDIS_TTL // 3600)
                stmt = select(NewsItem).filter(
                    NewsItem.last_seen_at >= time_filter,
                    NewsItem.embedding.is_not(None)
                )
                
                result = await session.execute(stmt)
                news_items = result.scalars().all()
                
                # Get Redis client
                redis_client = await get_redis_client()
                
                # Sync each item to Redis
                for item in news_items:
                    # Store vector in Redis
                    metadata = {
                        "title": item.title,
                        "url": item.url,
                        "source_url": item.source_url
                    }
                    
                    await redis_client.store_vector(
                        news_id=item.id,
                        embedding=item.embedding,
                        metadata=metadata
                    )
                
                logger.info(f"Synced {len(news_items)} vectors to Redis")
        except Exception as e:
            logger.error(f"Error syncing vectors to Redis: {str(e)}")
    
    async def update_visualizations(self):
        """Update pre-generated visualizations."""
        try:
            # Create a database session
            async with AsyncSessionLocal() as session:
                # Get Redis client for cluster generation
                redis_client = await get_redis_client()
                
                # Define the time ranges and similarities we want to pre-generate
                time_ranges = [24, 48, 72]  # 24, 48, and 72 hours
                similarities = [0.5, 0.6, 0.7]  # 50%, 60%, and 70% similarity
                
                # Update clusters
                for hours in time_ranges:
                    # Generate UMAP visualization
                    umap_data = await generate_umap_visualization(session, hours)
                    
                    # Check if UMAP visualization exists
                    stmt = select(NewsUMAP).filter(NewsUMAP.hours == hours)
                    result = await session.execute(stmt)
                    existing_umap = result.scalar_one_or_none()
                    
                    if existing_umap:
                        # Update existing visualization
                        stmt = update(NewsUMAP).where(NewsUMAP.hours == hours).values(
                            visualization=umap_data,
                            created_at=func.now()
                        )
                        await session.execute(stmt)
                    else:
                        # Create new visualization
                        umap_viz = NewsUMAP(
                            hours=hours,
                            visualization=umap_data
                        )
                        session.add(umap_viz)
                    
                    # Generate and store clusters for different similarities
                    for min_similarity in similarities:
                        # Generate clusters using Redis
                        clusters_data = await redis_client.get_clusters(hours, min_similarity)
                        
                        if not clusters_data:
                            logger.info(f"No clusters found for {hours}h, {min_similarity} similarity")
                            continue
                        
                        # Check if clusters exist
                        stmt = select(NewsClusters).filter(
                            NewsClusters.hours == hours,
                            NewsClusters.min_similarity == min_similarity
                        )
                        result = await session.execute(stmt)
                        existing_clusters = result.scalar_one_or_none()
                        
                        if existing_clusters:
                            # Update existing clusters
                            stmt = update(NewsClusters).where(
                                NewsClusters.hours == hours,
                                NewsClusters.min_similarity == min_similarity
                            ).values(
                                clusters=clusters_data,
                                created_at=func.now()
                            )
                            await session.execute(stmt)
                        else:
                            # Create new clusters
                            clusters = NewsClusters(
                                hours=hours,
                                min_similarity=min_similarity,
                                clusters=clusters_data
                            )
                            session.add(clusters)
                
                await session.commit()
                logger.info("Successfully updated pre-generated visualizations")
        
        except Exception as e:
            logger.error(f"Error updating visualizations: {str(e)}")
    
    async def run(self):
        """Run the embedding worker continuously."""
        self.running = True
        
        try:
            while self.running:
                logger.info("Running embedding worker cycle")
                
                # Sync vectors to Redis
                await self.sync_vectors_to_redis()
                
                # Update pre-generated visualizations
                await self.update_visualizations()
                
                # Sleep for a while before next cycle
                logger.info(f"Embedding worker cycle completed, sleeping for {settings.CRAWLER_INTERVAL // 4} seconds")
                await asyncio.sleep(settings.CRAWLER_INTERVAL // 4)  # Run more frequently than crawler
        
        except Exception as e:
            logger.error(f"Error in embedding worker: {str(e)}")
            self.running = False
    
    async def stop(self):
        """Stop the embedding worker."""
        self.running = False


async def main():
    """Main function to start the embedding worker."""
    logger.info("Starting embedding worker service")
    
    worker = EmbeddingWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())