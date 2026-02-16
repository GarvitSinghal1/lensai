"""
RSS Feed Scraper — fetches articles from all configured RSS feeds in parallel.
"""

import feedparser
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import config
from scraper.rss_feeds import get_all_feeds
from utils.logger import log


def _parse_published_date(entry: dict) -> Optional[datetime]:
    """Extract and parse the published date from an RSS entry."""
    # feedparser normalizes dates into 'published_parsed' (time.struct_time)
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
    return None


def _fetch_single_feed(feed_info: dict) -> list[dict]:
    """Fetch and parse a single RSS feed. Returns list of article dicts."""
    name = feed_info["name"]
    url = feed_info["url"]
    
    try:
        parsed = feedparser.parse(url)
        
        if parsed.bozo and not parsed.entries:
            log.warning(f"Failed to parse feed '{name}': {parsed.bozo_exception}")
            return []
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=config.MAX_ARTICLE_AGE_HOURS)
        articles = []
        
        for entry in parsed.entries:
            pub_date = _parse_published_date(entry)
            
            # Skip old articles (if we can determine the date)
            if pub_date and pub_date < cutoff:
                continue
            
            article = {
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", entry.get("description", "")).strip(),
                "link": entry.get("link", ""),
                "published": pub_date.isoformat() if pub_date else None,
                "source_name": name,
                "source_region": feed_info["region"],
                "source_bias": feed_info["bias"],
                "source_url": url,
            }
            
            # Skip entries without title or link
            if article["title"] and article["link"]:
                articles.append(article)
        
        log.info(f"  ✓ {name}: {len(articles)} recent articles")
        return articles
        
    except Exception as e:
        log.error(f"  ✗ {name}: {e}")
        return []


def scrape_all_feeds() -> list[dict]:
    """
    Scrape all configured RSS feeds in parallel.
    Returns a flat list of article dicts, filtered by recency.
    """
    feeds = get_all_feeds()
    all_articles = []
    
    log.info(f"Scraping {len(feeds)} RSS feeds...")
    
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_single_feed, feed): feed
            for feed in feeds
        }
        
        for future in as_completed(futures):
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception as e:
                feed = futures[future]
                log.error(f"  ✗ {feed['name']}: unexpected error: {e}")
    
    # Deduplicate by URL (same article might appear in multiple feeds)
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article["link"] not in seen_urls:
            seen_urls.add(article["link"])
            unique_articles.append(article)
    
    dupes_removed = len(all_articles) - len(unique_articles)
    log.info(
        f"Scraping complete: {len(unique_articles)} unique articles "
        f"({dupes_removed} duplicate URLs removed)"
    )
    
    return unique_articles
