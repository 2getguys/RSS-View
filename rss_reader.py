import feedparser
from typing import List, Dict, Optional
from datetime import datetime

def get_latest_articles(feed_url: str, count: int = 1) -> List[Dict[str, str]]:
    """
    Fetches the latest articles from an RSS feed based on publication date.

    Args:
        feed_url: The URL of the RSS feed.
        count: Number of latest articles to fetch (default: 1).

    Returns:
        A list containing the most recent articles (up to 'count' items).
    """
    feed = feedparser.parse(feed_url)

    if feed.bozo:
        print(f"Error parsing feed: {feed.bozo_exception}")
        return []

    if not feed.entries:
        print("No entries found in the feed.")
        return []

    # Sort entries by publication date (most recent first)
    sorted_entries = sorted(feed.entries, key=lambda x: x.get('published_parsed', (0,)), reverse=True)
    
    # Take the requested number of most recent articles
    latest_entries = sorted_entries[:count]
    
    articles = []
    for entry in latest_entries:
        articles.append({
            'title': entry.title,
            'link': entry.link
        })
    
    return articles

