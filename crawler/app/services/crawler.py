import asyncio
import feedparser
import logging
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select
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
    """News sucker service."""

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

    async def crawl_url(self, url_item: URL):
        """Crawl a single URL."""
        if url_item.type == "rss":
            await self._crawl_rss(url_item)
        else:
            await self._crawl_homepage(url_item)

    async def _crawl_rss(self, url_item: URL):
        """Crawl an RSS feed."""
        try:
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
            
        except Exception as e:
            logger.error(f"Error crawling RSS feed {url_item.url}: {str(e)}")
            raise

    async def _crawl_homepage(self, url_item: URL):
        """Crawl a homepage and extract news links."""
        try:
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
            
        except Exception as e:
            logger.error(f"Error crawling homepage {url_item.url}: {str(e)}")
            raise

    async def _process_news_item(self, title: str, url: str, source_url: str):
        """Process a news item link."""
        # Skip if title or URL is empty
        if not title or not url:
            return
        
        try:
            # Create a database session
            async with AsyncSessionLocal() as session:
                # Check if the URL already exists in the database
                result = await session.execute(select(NewsItem).filter(NewsItem.url == url))
                existing_item = result.scalars().first()
                
                if existing_item:
                    # Update existing item
                    existing_item.hit_count += 1
                    existing_item.last_seen_at = datetime.utcnow()
                    await session.commit()
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
                    logger.info(f"Added new news item: {title}")
        
        except Exception as e:
            logger.error(f"Error processing news item {url}: {str(e)}")

    async def _fetch_content(self, url: str) -> Optional[Dict[str, str]]:
        """Fetch and extract content from a URL."""
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            # Extract content using the extractor
            return self.extractor.extract_content(response.text, url)
            
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {str(e)}")
            return None
