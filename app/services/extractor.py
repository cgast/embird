import re
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from readability import Document
from newspaper import Article
from newspaper.article import ArticleException

logger = logging.getLogger(__name__)

class ContentExtractor:
    """Service for extracting content and links from web pages."""
    
    def __init__(self):
        self.min_content_length = 100
        self.max_summary_length = 2000
    
    def extract_content(self, html: str, url: str) -> Optional[Dict[str, str]]:
        """
        Extract content from an HTML page using multiple methods.
        
        Args:
            html: The HTML content
            url: The URL of the page
            
        Returns:
            Dictionary with extracted content or None if extraction failed
        """
        if not html:
            logger.warning(f"Empty HTML content for {url}")
            return None
            
        content = None
        
        # Try readability-lxml first
        try:
            content = self._extract_with_readability(html)
            if content and len(content["summary"]) >= self.min_content_length:
                logger.info(f"Successfully extracted content from {url} using readability-lxml")
                return content
            else:
                logger.debug(f"Readability extraction too short for {url}, trying newspaper3k")
        except Exception as e:
            logger.warning(f"Readability extraction failed for {url}: {str(e)}")
        
        # Fallback to newspaper3k
        try:
            content = self._extract_with_newspaper(html, url)
            if content and len(content["summary"]) >= self.min_content_length:
                logger.info(f"Successfully extracted content from {url} using newspaper3k")
                return content
            else:
                logger.warning(f"Newspaper extraction too short for {url}")
        except Exception as e:
            logger.warning(f"Newspaper extraction failed for {url}: {str(e)}")
        
        # If we have any content, even if short, return it
        if content and content["summary"]:
            logger.info(f"Returning short content for {url} (length: {len(content['summary'])})")
            return content
            
        logger.error(f"All content extraction methods failed for {url}")
        return None
    
    def _extract_with_readability(self, html: str) -> Optional[Dict[str, str]]:
        """Extract content using readability-lxml."""
        doc = Document(html)
        title = doc.title()
        summary = doc.summary()
        
        # Clean up the summary
        soup = BeautifulSoup(summary, "lxml")
        clean_text = self._clean_text(soup.get_text())
        
        return {
            "title": title,
            "summary": self._truncate_text(clean_text)
        }
    
    def _extract_with_newspaper(self, html: str, url: str) -> Optional[Dict[str, str]]:
        """Extract content using newspaper3k."""
        article = Article(url)
        article.set_html(html)
        article.parse()
        
        # Get the text content
        text = article.text
        if not text:
            return None
            
        clean_text = self._clean_text(text)
        
        return {
            "title": article.title,
            "summary": self._truncate_text(clean_text)
        }
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text content."""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove common noise patterns
        noise_patterns = [
            r'Share this:', 
            r'Follow us on Twitter',
            r'Like us on Facebook',
            r'Subscribe to our newsletter',
            r'Comments?',
            r'©\s*\d{4}',  # Copyright notices
            r'All rights reserved',
            r'Terms of [Ss]ervice',
            r'Privacy [Pp]olicy'
        ]
        
        for pattern in noise_patterns:
            text = re.sub(pattern, '', text)
        
        return text.strip()
    
    def _truncate_text(self, text: str) -> str:
        """Truncate text to maximum length."""
        if len(text) > self.max_summary_length:
            return text[:self.max_summary_length] + "..."
        return text
    
    def extract_links(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """
        Extract links from an HTML page.
        
        Args:
            html: The HTML content
            base_url: The base URL for resolving relative links
            
        Returns:
            List of dictionaries containing link info (title, url)
        """
        links = []
        
        try:
            soup = BeautifulSoup(html, "lxml")
            
            # Get domain of the base URL for filtering
            base_domain = urlparse(base_url).netloc
            
            # Find all links
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                
                # Skip empty links
                if not href or href.startswith("#"):
                    continue
                
                # Resolve relative URLs
                absolute_url = urljoin(base_url, href)
                
                # Skip URLs from different domains
                url_domain = urlparse(absolute_url).netloc
                if not url_domain.endswith(base_domain) and base_domain not in url_domain:
                    continue
                
                # Skip non-http URLs
                if not absolute_url.startswith(("http://", "https://")):
                    continue
                
                # Get title from text or title attribute
                title = a_tag.get_text(strip=True) or a_tag.get("title", "")
                if not title:
                    continue
                
                # Get content around the link to improve title quality
                parent = a_tag.parent
                context = ""
                if parent:
                    context = parent.get_text(strip=True)
                    if len(context) > 100:
                        context = context[:100]
                
                # Use context if title is too short
                if len(title) < 10 and len(context) > len(title):
                    title = context
                
                # Add link if not already in the list and title is not too short
                if len(title) >= 5:
                    link_info = {"title": title, "url": absolute_url}
                    if link_info not in links:
                        links.append(link_info)
            
            logger.info(f"Extracted {len(links)} links from {base_url}")
            return links
            
        except Exception as e:
            logger.error(f"Error extracting links from {base_url}: {str(e)}")
            return []
    
    def extract_rss_items(self, rss_content: str) -> List[Dict[str, str]]:
        """
        Extract items from RSS content.
        
        Args:
            rss_content: The RSS content
            
        Returns:
            List of dictionaries containing RSS item info
        """
        items = []
        
        try:
            soup = BeautifulSoup(rss_content, "xml")
            
            # Get all items/entries
            for item in soup.find_all(["item", "entry"]):
                # Extract title
                title_tag = item.find(["title"])
                title = title_tag.get_text(strip=True) if title_tag else ""
                
                # Extract link
                link_tag = item.find(["link"])
                link = ""
                if link_tag:
                    if link_tag.has_attr("href"):
                        link = link_tag.get("href")
                    else:
                        link = link_tag.get_text(strip=True)
                
                # Extract description/summary
                description_tag = item.find(["description", "summary", "content"])
                description = description_tag.get_text(strip=True) if description_tag else ""
                
                # Only add if title and link are not empty
                if title and link:
                    items.append({
                        "title": title,
                        "url": link,
                        "description": description
                    })
            
            logger.info(f"Extracted {len(items)} RSS items")
            return items
            
        except Exception as e:
            logger.error(f"Error extracting RSS items: {str(e)}")
            return []
