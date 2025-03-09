import re
import logging
from urllib.parse import urlparse, urljoin
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and normalizing."""
    if not text:
        return ""
    
    # Replace multiple whitespace with a single space
    cleaned = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()
    # Replace HTML entities
    cleaned = cleaned.replace('&nbsp;', ' ')
    cleaned = cleaned.replace('&amp;', '&')
    cleaned = cleaned.replace('&lt;', '<')
    cleaned = cleaned.replace('&gt;', '>')
    cleaned = cleaned.replace('&quot;', '"')
    cleaned = cleaned.replace('&#39;', "'")
    
    return cleaned

def is_valid_url(url: str) -> bool:
    """Check if a URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def normalize_url(url: str, base_url: str = None) -> Optional[str]:
    """Normalize a URL by resolving relative paths and removing fragments."""
    try:
        if not url:
            return None
        
        # Handle relative URLs
        if base_url and not urlparse(url).netloc:
            url = urljoin(base_url, url)
        
        # Parse the URL
        parsed = urlparse(url)
        
        # Reconstruct the URL without fragments
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # Add query parameters if they exist
        if parsed.query:
            normalized = f"{normalized}?{parsed.query}"
        
        return normalized
    except Exception as e:
        logger.error(f"Error normalizing URL {url}: {str(e)}")
        return None

def extract_domain(url: str) -> Optional[str]:
    """Extract the domain from a URL."""
    try:
        if not url:
            return None
        
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return None

def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to a maximum length."""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Try to truncate at a sentence or paragraph boundary
    truncated = text[:max_length]
    
    # Look for the last sentence boundary
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    
    # If we found a sentence boundary in the last 20% of the text, use it
    if last_period > max_length * 0.8:
        return truncated[:last_period + 1]
    elif last_newline > max_length * 0.8:
        return truncated[:last_newline]
    
    # Otherwise just truncate and add ellipsis
    return truncated + "..."