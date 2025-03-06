import asyncio
import time
import schedule
import logging
from datetime import datetime
from app.config import settings
from app.services.crawler import Crawler
from app.models.url import URLDatabase
from app.services.visualization import generate_clusters
from app.services.db import get_db
from shared.models.news import NewsClusters  # Updated import
from sqlalchemy import select, update, func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Initialize URL database
url_db = URLDatabase(settings.SQLITE_PATH)

async def update_clusters(db):
    """Update pre-generated clusters in the database."""
    logger.info("Generating news clusters")
    try:
        # Generate clusters with default parameters
        clusters_data = await generate_clusters(db)
        
        # Check if clusters exist
        stmt = select(NewsClusters).filter(
            NewsClusters.hours == 24,  # Default time window
            NewsClusters.min_similarity == 0.2  # Default similarity threshold
        )
        result = await db.execute(stmt)
        existing_clusters = result.scalar_one_or_none()
        
        if existing_clusters:
            # Update existing clusters
            stmt = update(NewsClusters).where(
                NewsClusters.hours == 24,
                NewsClusters.min_similarity == 0.2
            ).values(
                clusters=clusters_data,
                created_at=func.now()
            )
            await db.execute(stmt)
        else:
            # Create new clusters
            new_clusters = NewsClusters(
                hours=24,  # Default time window
                min_similarity=0.2,  # Default similarity threshold
                clusters=clusters_data
            )
            db.add(new_clusters)
        
        await db.commit()
        logger.info("Successfully updated news clusters")
    except Exception as e:
        logger.error(f"Error generating clusters: {str(e)}")
        # Rollback on error
        await db.rollback()

async def crawl_all_urls():
    """Crawl all URLs in the database."""
    logger.info("Starting crawl job")
    
    # Initialize crawler
    crawler = Crawler(url_db=url_db)
    
    # Get all URLs
    urls = url_db.get_urls_to_crawl()
    
    if not urls:
        logger.info("No URLs to crawl")
        return
    
    logger.info(f"Found {len(urls)} URLs to crawl")
    
    # Crawl each URL
    for url_item in urls:
        try:
            logger.info(f"Crawling URL: {url_item.url}")
            await crawler.crawl_url(url_item)
            # Update last crawled time
            url_db.update_url_crawl_time(url_item.id)
            logger.info(f"Successfully crawled URL: {url_item.url}")
        except Exception as e:
            logger.error(f"Error crawling URL {url_item.url}: {str(e)}")
    
    logger.info("Crawl job completed")
    
    # Update clusters after crawling
    async with get_db() as db:
        await update_clusters(db)

async def main():
    """Main function to start the crawler service."""
    logger.info("Starting news-suck service")
    
    # Run initial crawl
    await crawl_all_urls()
    
    # Schedule recurring crawl using asyncio
    logger.info(f"Scheduling crawl job every {settings.CRAWLER_INTERVAL} seconds")
    
    while True:
        # Run crawl job
        await crawl_all_urls()
        # Wait for next interval
        await asyncio.sleep(settings.CRAWLER_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
