import asyncio
import feedparser
import logging
import httpx
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.url import URL, URLDatabase
from app.models.news import NewsItem, NewsItemCreate
from app.services.extractor import ContentExtractor
from app.services.embedding import EmbeddingService

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
            # Delete items older than retention period using timezone-aware UTC time
            retention_date = datetime.now(timezone.utc) - timedelta(days=settings.NEWS_RETENTION_DAYS)
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
            # Update last_crawled_at after successful crawl
            self.url_db.update_url_crawl_time(url_item.id)
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
                    # Update existing item with timezone-aware UTC time
                    existing_item.hit_count += 1
                    existing_item.last_seen_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info(f"Updated existing news item: {title}")
                else:
                    # Get content and summary for new item
                    content_info = await self._fetch_content(url)
                    
                    if not content_info:
                        logger.warning(f"Failed to extract content from {url}")
                        return
                    
                    # Create embedding based on settings
                    text_for_embedding = title if settings.EMBED_TITLE_ONLY else f"{title}. {content_info['summary']}"
                    embedding = await self.embedding_service.get_embedding(text_for_embedding)
                    
                    # Skip if embedding generation failed
                    if not embedding:
                        logger.warning(f"Failed to generate embedding for {url}")
                        return
                    
                    # Create new news item with timezone-aware UTC time
                    now = datetime.now(timezone.utc)
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
                    logger.info(f"Added new news item: {title}")
        
        except Exception as e:
            logger.error(f"Error processing news item {url}: {str(e)}")

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()

# Global instance
crawler = None

async def start_crawler():
    """Start the crawler service."""
    global crawler
    from app.services.db import url_db
    
    try:
        # Initialize crawler
        crawler = Crawler(url_db)
        logger.info("Crawler service initialized")
        
        while True:
            # Get all URLs to crawl
            urls = url_db.get_all_urls()
            
            # Crawl each URL
            for url in urls:
                await crawler.crawl_url(url)
            
            # Sleep for the configured interval
            logger.info(f"Crawler cycle completed, sleeping for {settings.CRAWLER_INTERVAL} seconds")
            await asyncio.sleep(settings.CRAWLER_INTERVAL)
            
    except Exception as e:
        logger.error(f"Crawler service error: {str(e)}")
        if crawler:
            await crawler.close()

async def stop_crawler():
    """Stop the crawler service."""
    global crawler
    if crawler:
        await crawler.close()
        logger.info("Crawler service stopped")
