"""Crawler service entry point."""
import asyncio
import logging
from app.services.crawler import start_crawler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        # Create and run event loop
        loop = asyncio.get_event_loop()
        loop.create_task(start_crawler())
        logger.info("Starting crawler service...")
        loop.run_forever()
    except Exception as e:
        logger.error(f"Crawler service failed: {str(e)}")
        raise
