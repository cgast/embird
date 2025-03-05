import os
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
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
    
    # Data Retention Settings
    NEWS_RETENTION_DAYS: int = int(os.environ.get("NEWS_RETENTION_DAYS", 30))
    NEWS_MAX_ITEMS: int = int(os.environ.get("NEWS_MAX_ITEMS", 10000))
    
    # App Settings
    APP_NAME: str = "news-suck"
    DEBUG: bool = os.environ.get("DEBUG", "False").lower() in ("true", "1", "t")
    
    # Vector dimensions
    VECTOR_DIMENSIONS: int = 1024  # Cohere embed-english-v3.0
    
    # Ensure SQLite directory exists
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure SQLite directory exists
        sqlite_dir = Path(self.SQLITE_PATH).parent
        sqlite_dir.mkdir(parents=True, exist_ok=True)

settings = Settings()
