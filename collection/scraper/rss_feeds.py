"""
RSS Feed definitions for reputable news sources.
Organized by region with source metadata.
"""

# Each feed: (name, url, region, bias_label)
# bias_label is informational only — used for diversity in cross-referencing
RSS_FEEDS = [
    # ─── Global / Wire Services ────────────────────────────
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews", "Global", "center"),
    ("AP News Top", "https://rsshub.app/apnews/topics/apf-topnews", "Global", "center"),
    
    # ─── UK ────────────────────────────────────────────────
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "UK", "center"),
    ("BBC Top Stories", "https://feeds.bbci.co.uk/news/rss.xml", "UK", "center"),
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", "UK", "center"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "UK", "center"),
    ("The Guardian World", "https://www.theguardian.com/world/rss", "UK", "center-left"),
    
    # ─── US ────────────────────────────────────────────────
    ("CNN Top Stories", "http://rss.cnn.com/rss/edition.rss", "US", "center-left"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml", "US", "center"),
    ("CBS News", "https://www.cbsnews.com/latest/rss/main", "US", "center"),
    
    # ─── India ─────────────────────────────────────────────
    ("Times of India", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "India", "center"),
    ("NDTV Top Stories", "https://feeds.feedburner.com/ndtvnews-top-stories", "India", "center"),
    ("The Hindu National", "https://www.thehindu.com/news/national/feeder/default.rss", "India", "center-left"),
    ("Hindustan Times", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", "India", "center"),
    
    # ─── Middle East ───────────────────────────────────────
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "Middle East", "center"),
    
    # ─── Europe ────────────────────────────────────────────
    ("Deutsche Welle", "https://rss.dw.com/rdf/rss-en-all", "Germany", "center"),
    ("France 24", "https://www.france24.com/en/rss", "France", "center"),
    
    # ─── Asia-Pacific ──────────────────────────────────────
    ("ABC Australia", "https://www.abc.net.au/news/feed/51120/rss.xml", "Australia", "center"),
    ("NHK World", "https://www3.nhk.or.jp/rss/news/cat0.xml", "Japan", "center"),
    ("SCMP", "https://www.scmp.com/rss/91/feed", "Hong Kong", "center"),
    
    # ─── Science & Tech ───────────────────────────────────
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "US", "center"),
    ("TechCrunch", "https://techcrunch.com/feed/", "US", "center"),
]


def get_all_feeds() -> list[dict]:
    """Return all RSS feeds as a list of dicts."""
    return [
        {
            "name": name,
            "url": url,
            "region": region,
            "bias": bias,
        }
        for name, url, region, bias in RSS_FEEDS
    ]


def get_feed_count() -> int:
    """Return total number of configured feeds."""
    return len(RSS_FEEDS)
