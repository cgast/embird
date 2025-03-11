import sqlite3
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, validator

class URLBase(BaseModel):
    """Base model for URL."""
    url: str
    type: str  # 'rss' or 'homepage'
    
    @validator('type')
    def validate_type(cls, v):
        if v not in ['rss', 'homepage']:
            raise ValueError('Type must be either "rss" or "homepage"')
        return v
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class URLCreate(URLBase):
    """Model for creating a new URL."""
    pass

class URL(URLBase):
    """Model for a URL retrieved from the database."""
    id: int
    created_at: datetime
    updated_at: datetime
    last_crawled_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class URLDatabase:
    """SQLite database operations for URL management."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._create_tables()
    
    def _create_tables(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_crawled_at TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_url(self, url_data: URLCreate) -> URL:
        """Add a new URL to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Use timezone-aware UTC time
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute(
            '''
            INSERT INTO urls (url, type, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ''',
            (url_data.url, url_data.type, now, now)
        )
        
        url_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return URL(
            id=url_id,
            url=url_data.url,
            type=url_data.type,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
            last_crawled_at=None
        )
    
    def get_all_urls(self) -> List[URL]:
        """Get all URLs from the database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM urls ORDER BY id DESC')
        rows = cursor.fetchall()
        
        urls = []
        for row in rows:
            url = URL(
                id=row['id'],
                url=row['url'],
                type=row['type'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at']),
                last_crawled_at=datetime.fromisoformat(row['last_crawled_at']) if row['last_crawled_at'] else None
            )
            urls.append(url)
        
        conn.close()
        return urls
    
    def get_url_by_id(self, url_id: int) -> Optional[URL]:
        """Get a URL by its ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM urls WHERE id = ?', (url_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        url = URL(
            id=row['id'],
            url=row['url'],
            type=row['type'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            last_crawled_at=datetime.fromisoformat(row['last_crawled_at']) if row['last_crawled_at'] else None
        )
        
        conn.close()
        return url
    
    def update_url_crawl_time(self, url_id: int) -> bool:
        """Update the last crawled time for a URL."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Use timezone-aware UTC time
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute(
            '''
            UPDATE urls
            SET last_crawled_at = ?, updated_at = ?
            WHERE id = ?
            ''',
            (now, now, url_id)
        )
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return rows_affected > 0
    
    def delete_url(self, url_id: int) -> bool:
        """Delete a URL by its ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM urls WHERE id = ?', (url_id,))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return rows_affected > 0
    
    def get_urls_to_crawl(self) -> List[URL]:
        """Get all URLs that need to be crawled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM urls')
        rows = cursor.fetchall()
        
        urls = []
        for row in rows:
            url = URL(
                id=row['id'],
                url=row['url'],
                type=row['type'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at']),
                last_crawled_at=datetime.fromisoformat(row['last_crawled_at']) if row['last_crawled_at'] else None
            )
            urls.append(url)
        
        conn.close()
        return urls
