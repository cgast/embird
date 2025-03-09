import os
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "news-suck"
    DEBUG: bool = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")
    
    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/newsdb")
    SQLITE_PATH: str = os.environ.get("SQLITE_PATH", "/app/data/urls.db")
    
    # Redis settings
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
    REDIS_TTL: int = int(os.environ.get("REDIS_TTL", 86400))  # 24 hours in seconds
    REDIS_PREFIX: str = os.environ.get("REDIS_PREFIX", "news:")
    
    # API Keys
    COHERE_API_KEY: str = os.environ.get("COHERE_API_KEY", "")
    
    # Crawler Settings
    CRAWLER_INTERVAL: int = int(os.environ.get("CRAWLER_INTERVAL", 3600))  # 1 hour in seconds
    NEWS_RETENTION_DAYS: int = int(os.environ.get("NEWS_RETENTION_DAYS", 30))  # Keep news for 30 days
    NEWS_MAX_ITEMS: int = int(os.environ.get("NEWS_MAX_ITEMS", 10000))  # Maximum number of news items to keep
    
    # Crawler Concurrency settings
    MAX_CONCURRENT_REQUESTS: int = int(os.environ.get("MAX_CONCURRENT_REQUESTS", 5))
    REQUEST_TIMEOUT: int = int(os.environ.get("REQUEST_TIMEOUT", 30))  # seconds
    
    # User agent for crawler
    USER_AGENT: str = os.environ.get(
        "USER_AGENT", 
        "NewsBot Crawler/1.0 (https://github.com/yourusername/news-crawler)"
    )
    
    # Vector dimensions
    VECTOR_DIMENSIONS: int = 1024  # Cohere embed-english-v3.0

    # Visualization Settings
    VISUALIZATION_TIME_RANGE: int = int(os.environ.get("VISUALIZATION_TIME_RANGE", 48))  # hours
    VISUALIZATION_SIMILARITY: float = float(os.environ.get("VISUALIZATION_SIMILARITY", 0.6))  # similarity threshold
    
    # Ensure SQLite directory exists
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure SQLite directory exists
        sqlite_dir = Path(self.SQLITE_PATH).parent
        sqlite_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()
