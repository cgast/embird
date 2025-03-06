import asyncio
import feedparser
import logging
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.url import URL, URLDatabase
from shared.models.news import NewsItem, NewsItemCreate  # Updated import
from app.services.extractor import ContentExtractor
from app.services.embedding import EmbeddingService
from app.services.redis_client import get_redis_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up PostgreSQL connection
pg_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False
)
AsyncSessionLocal = sessionmaker(pg_engine, expire_on_commit=False, class_=AsyncSession)

class Crawler:
    """News crawler service."""

    def __init__(self, url_db: URLDatabase):
        """Initialize the crawler."""
        self.url_db = url_db
        self.extractor = ContentExtractor()
        self.embedding_service = EmbeddingService(settings.COHERE_API_KEY)
        self.http_client = httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True
        )
        self.semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)

    async def _cleanup_old_news(self, session: AsyncSession):
        """Clean up old news items based on retention settings."""
        try:
            # Delete items older than retention period
            retention_date = datetime.utcnow() - timedelta(days=settings.NEWS_RETENTION_DAYS)
            delete_stmt = delete(NewsItem).where(NewsItem.last_seen_at < retention_date)
            await session.execute(delete_stmt)

            # Get total count of items
            result = await session.execute(select(func.count(NewsItem.id)))
            total_items = result.scalar()

            # If we're over the max items limit, delete oldest items
            if total_items > settings.NEWS_MAX_ITEMS:
                items_to_delete = total_items - settings.NEWS_MAX_ITEMS
                subquery = select(NewsItem.id).order_by(NewsItem.last_seen_at.desc()).offset(settings.NEWS_MAX_ITEMS)
                await session.execute(
                    delete(NewsItem).where(NewsItem.id.in_(subquery))
                )

            await session.commit()
            logger.info("Completed news items cleanup")
        except Exception as e:
            logger.error(f"Error during news cleanup: {str(e)}")
            await session.rollback()

    async def crawl_url(self, url_item: URL):
        """Crawl a single URL."""
        try:
            if url_item.type == "rss":
                await self._crawl_rss(url_item)
            else:
                await self._crawl_homepage(url_item)
        except Exception as e:
            logger.error(f"Error crawling {url_item.url}: {str(e)}")

    async def _crawl_rss(self, url_item: URL):
        """Crawl an RSS feed."""
        try:
            async with self.semaphore:
                response = await self.http_client.get(url_item.url)
                response.raise_for_status()
            
            # Use feedparser to parse the RSS content
            feed = feedparser.parse(response.text)
            
            # Process each entry in the feed
            tasks = []
            for entry in feed.entries:
                # Extract required data
                title = entry.get("title", "")
                link = entry.get("link", "")
                
                # Skip entries without title or link
                if not title or not link:
                    continue
                
                # Process each item
                tasks.append(self._process_news_item(title, link, url_item.url))
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error crawling RSS feed {url_item.url}: {str(e)}")
        except Exception as e:
            logger.error(f"Error crawling RSS feed {url_item.url}: {str(e)}")

    async def _crawl_homepage(self, url_item: URL):
        """Crawl a homepage and extract news links."""
        try:
            async with self.semaphore:
                response = await self.http_client.get(url_item.url)
                response.raise_for_status()
            
            # Extract links using the extractor
            links = self.extractor.extract_links(response.text, url_item.url)
            
            # Process each link
            tasks = []
            for link_info in links:
                tasks.append(self._process_news_item(
                    link_info["title"], 
                    link_info["url"],
                    url_item.url
                ))
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error crawling homepage {url_item.url}: {str(e)}")
        except Exception as e:
            logger.error(f"Error crawling homepage {url_item.url}: {str(e)}")

    async def _fetch_content(self, url: str) -> Optional[Dict[str, str]]:
        """Fetch and extract content from a URL."""
        try:
            async with self.semaphore:
                response = await self.http_client.get(url)
                response.raise_for_status()
            
            # Extract content using the extractor
            content = self.extractor.extract_content(response.text, url)
            if not content:
                logger.warning(f"Failed to extract content from {url}")
                return None
                
            return content
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching content from {url}: {str(e)}\nFor more information check: https://httpstatuses.com/{e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {str(e)}")
            return None

    async def _process_news_item(self, title: str, url: str, source_url: str):
        """Process a news item link."""
        # Skip if title or URL is empty
        if not title or not url:
            return
        
        try:
            # Create a database session
            async with AsyncSessionLocal() as session:
                # Run cleanup before processing new items
                await self._cleanup_old_news(session)

                # Check if the URL already exists in the database
                result = await session.execute(select(NewsItem).filter(NewsItem.url == url))
                existing_item = result.scalars().first()
                
                if existing_item:
                    # Update existing item
                    existing_item.hit_count += 1
                    existing_item.last_seen_at = datetime.utcnow()
                    await session.commit()
                    
                    # Update the item in Redis too
                    try:
                        redis_client = await get_redis_client()
                        metadata = {
                            "title": existing_item.title,
                            "url": existing_item.url,
                            "source_url": existing_item.source_url
                        }
                        
                        # Convert numpy array to list if needed
                        embedding = None
                        if existing_item.embedding is not None:
                            # Check if it's a numpy array
                            if hasattr(existing_item.embedding, 'tolist'):
                                embedding = existing_item.embedding.tolist()
                            else:
                                embedding = existing_item.embedding
                            
                            # Only proceed if we have a valid embedding
                            if embedding is not None:
                                print(f"CRAWLER DEBUG: Attempting to store vector for existing item {existing_item.id}")
                                await redis_client.store_vector(
                                    news_id=existing_item.id,
                                    embedding=embedding,
                                    metadata=metadata
                                )
                                print(f"CRAWLER DEBUG: Successfully stored vector for existing item {existing_item.id}")
                    except Exception as redis_error:
                        print(f"CRAWLER DEBUG: Redis error when updating existing item: {redis_error}")
                    
                    logger.info(f"Updated existing news item: {title}")
                else:
                    # Get content and summary for new item
                    content_info = await self._fetch_content(url)
                    
                    if not content_info:
                        logger.warning(f"Failed to extract content from {url}")
                        return
                    
                    # Create embedding for the content
                    text_for_embedding = f"{title}. {content_info['summary']}"
                    embedding = await self.embedding_service.get_embedding(text_for_embedding)
                    
                    # Skip if embedding generation failed
                    if not embedding:
                        logger.warning(f"Failed to generate embedding for {url}")
                        return
                    
                    # Create new news item
                    now = datetime.utcnow()
                    news_item = NewsItem(
                        title=title,
                        summary=content_info["summary"],
                        url=url,
                        source_url=source_url,
                        first_seen_at=now,
                        last_seen_at=now,
                        hit_count=1,
                        embedding=embedding
                    )
                    
                    # Add to database
                    session.add(news_item)
                    await session.commit()
                    
                    # Also store in Redis for fast access
                    try:
                        redis_client = await get_redis_client()
                        metadata = {
                            "title": title,
                            "url": url,
                            "source_url": source_url
                        }
                        
                        # Ensure embedding is a list (not a numpy array)
                        embedding_list = None
                        if embedding is not None:
                            if hasattr(embedding, 'tolist'):
                                embedding_list = embedding.tolist()
                            else:
                                embedding_list = embedding
                        
                        # Only proceed if we have a valid embedding
                        if embedding_list is not None:
                            print(f"CRAWLER DEBUG: Attempting to store vector for new item {news_item.id}")
                            await redis_client.store_vector(
                                news_id=news_item.id,
                                embedding=embedding_list,
                                metadata=metadata
                            )
                            print(f"CRAWLER DEBUG: Successfully stored vector for new item {news_item.id}")
                    except Exception as redis_error:
                        print(f"CRAWLER DEBUG: Redis error when storing new item: {redis_error}")
                    
                    logger.info(f"Added new news item: {title}")
        
        except Exception as e:
            logger.error(f"Error processing news item {url}: {str(e)}")

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()
