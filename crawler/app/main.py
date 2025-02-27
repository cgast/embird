import asyncio
import time
import schedule
import logging
from datetime import datetime
from app.config import settings
from app.services.crawler import Crawler
from app.models.url import URLDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Initialize URL database
url_db = URLDatabase(settings.SQLITE_PATH)

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
