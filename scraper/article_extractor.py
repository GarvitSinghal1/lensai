"""
Article Content Extractor — downloads and extracts full text from article URLs.
"""

import time
import requests
from typing import Optional

import config
from utils.logger import log

# Try newspaper3k first, fall back to BeautifulSoup
try:
    from newspaper import Article as NewspaperArticle
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False
    log.warning("newspaper3k not available, using BeautifulSoup fallback")

from bs4 import BeautifulSoup


def _extract_with_newspaper(url: str) -> Optional[dict]:
    """Extract article content using newspaper3k."""
    if not HAS_NEWSPAPER:
        return None
    
    try:
        article = NewspaperArticle(url)
        article.download()
        article.parse()
        
        if not article.text or len(article.text) < 100:
            return None
        
        return {
            "full_text": article.text,
            "top_image": article.top_image or "",
            "authors": article.authors or [],
        }
    except Exception as e:
        log.debug(f"newspaper3k failed for {url}: {e}")
        return None


def _extract_with_bs4(url: str) -> Optional[dict]:
    """Extract article content using BeautifulSoup as fallback."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=config.SCRAPE_TIMEOUT)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        
        # Try common article body selectors
        body = None
        for selector in [
            "article",
            '[class*="article-body"]',
            '[class*="story-body"]',
            '[class*="content-body"]',
            '[class*="post-content"]',
            "main",
        ]:
            body = soup.select_one(selector)
            if body:
                break
        
        if not body:
            body = soup.find("body")
        
        if not body:
            return None
        
        # Extract paragraphs
        paragraphs = body.find_all("p")
        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        if len(text) < 100:
            return None
        
        # Try to find main image
        img_tag = soup.find("meta", property="og:image")
        top_image = img_tag["content"] if img_tag and img_tag.get("content") else ""
        
        return {
            "full_text": text,
            "top_image": top_image,
            "authors": [],
        }
    except Exception as e:
        log.debug(f"BS4 fallback failed for {url}: {e}")
        return None


def extract_article(url: str) -> Optional[dict]:
    """
    Extract full article content from a URL.
    Tries newspaper3k first, falls back to BeautifulSoup.
    """
    result = _extract_with_newspaper(url)
    if result:
        return result
    
    return _extract_with_bs4(url)


def extract_articles_batch(articles: list[dict], max_per_topic: int = 10) -> list[dict]:
    """
    Extract full text for a batch of articles (from the same topic cluster).
    Rate-limited to avoid getting blocked.
    Returns articles with 'full_text' field added.
    """
    enriched = []
    
    for i, article in enumerate(articles[:max_per_topic]):
        url = article.get("link", "")
        if not url:
            continue
        
        log.debug(f"  Extracting [{i+1}/{min(len(articles), max_per_topic)}]: {url[:80]}...")
        
        content = extract_article(url)
        if content:
            article_copy = article.copy()
            article_copy["full_text"] = content["full_text"]
            article_copy["top_image"] = content.get("top_image", "")
            article_copy["authors"] = content.get("authors", [])
            enriched.append(article_copy)
        
        # Rate limit
        if i < len(articles) - 1:
            time.sleep(config.SCRAPE_DELAY)
    
    log.info(f"  Extracted full text from {len(enriched)}/{len(articles)} articles")
    return enriched
