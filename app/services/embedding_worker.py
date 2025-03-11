#!/usr/bin/env python3
"""Standalone worker for embedding and visualization tasks."""
import asyncio
import logging
from app.services.embedding import embedding_service
from app.services.faiss_service import get_faiss_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    """Main worker function."""
    try:
        # Initialize FAISS service
        faiss_service = get_faiss_service()
        logger.info("FAISS service initialized")
        
        # Start background tasks
        logger.info("Starting embedding worker")
        await embedding_service.run_background_tasks()
    except Exception as e:
        logger.error(f"Embedding worker error: {str(e)}")
        raise
    finally:
        await embedding_service.stop_background_tasks()

if __name__ == "__main__":
    asyncio.run(main())
