import re
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from readability import Document
from newspaper import Article

logger = logging.getLogger(__name__)

class ContentExtractor:
    """Service for extracting content and links from web pages."""
    
    def extract_content(self, html: str, url: str) -> Optional[Dict[str, str]]:
        """
        Extract content from an HTML page.
        
        Args:
            html: The HTML content
            url: The URL of the page
            
        Returns:
            Dictionary with extracted content or None if extraction failed
        """
        try:
            # Try using readability-lxml for extraction
            doc = Document(html)
            title = doc.title()
            summary = doc.summary()
            
            # Clean up the summary
            soup = BeautifulSoup(summary, "lxml")
            clean_text = soup.get_text(separator=' ', strip=True)
            
            # Fallback to newspaper3k if content is too short
            if len(clean_text) < 100:
                article = Article(url)
                article.set_html(html)
                article.parse()
                title = article.title
                clean_text = article.text
            
            # Truncate summary if it's too long
            max_summary_length = 2000
            if len(clean_text) > max_summary_length:
                clean_text = clean_text[:max_summary_length] + "..."
            
            return {
                "title": title,
                "summary": clean_text
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return None
    
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
            
            return items
            
        except Exception as e:
            logger.error(f"Error extracting RSS items: {str(e)}")
            return []