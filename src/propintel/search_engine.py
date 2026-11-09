# src/propintel/search_engine.py
import urllib.parse
import hashlib
import logging
import feedparser
import httpx
from bs4 import BeautifulSoup
from propintel.db import get_db

logger = logging.getLogger(__name__)

# Core Lucknow real estate intelligence keywords
DISCOVERY_TOPICS = [
    "Lucknow real estate property circle rate",
    "Lucknow Development Authority LDA plot scheme rate",
    "UP RERA Lucknow project launch registry per sq ft",
    "Lucknow Awas Vikas Parishad flat plot rates",
    "Lucknow registry rate per sq ft revised"
]

def clean_html(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "lxml")
    for s in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        s.extract()
    return " ".join(soup.stripped_strings)[:6000]

def fetch_google_news_rss(query: str, max_items: int = 4) -> list[dict]:
    """
    Pulls structured, unblocked live real-time news via Google's official public RSS feed.
    No rate limits, no CAPTCHAs, guaranteed results.
    """
    encoded_q = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-IN&gl=IN&ceid=IN:en"
    
    feed = feedparser.parse(rss_url)
    results = []
    
    for entry in feed.entries[:max_items]:
        results.append({
            "url": entry.get("link", ""),
            "title": entry.get("title", ""),
            "snippet": entry.get("summary", "")
        })
    return results

def search_and_ingest(max_results_per_query: int = 3) -> int:
    total_new = 0
    timeout_config = httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=3.0)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    # Pull previously discovered localities to build micro-market queries dynamically
    with get_db() as c:
        known_localities = [r["name"] for r in c.execute("SELECT name FROM localities WHERE district='Lucknow' ORDER BY id DESC LIMIT 8").fetchall()]

    query_queue = list(DISCOVERY_TOPICS)
    for loc in known_localities:
        query_queue.append(f"{loc} Lucknow property rate sq ft")

    print(f"[*] Querying live intelligence feeds ({len(query_queue)} vectors)...")

    with httpx.Client(headers=headers, timeout=timeout_config, follow_redirects=True) as http_client:
        for q in query_queue:
            print(f"[Search Engine] Crawling: {q}")
            results = fetch_google_news_rss(q, max_items=max_results_per_query)

            for item in results:
                url = item.get("url")
                title = item.get("title", "")
                snippet = item.get("snippet", "")

                if not url:
                    continue

                # Strip HTML tags from RSS summary
                summary_text = BeautifulSoup(snippet, "lxml").get_text(separator=" ").strip()
                body_content = summary_text

                # Optional: try pulling article page text if quick, else fallback to summary
                try:
                    resp = http_client.get(url)
                    if resp.status_code == 200:
                        page_text = clean_html(resp.text)
                        if len(page_text) > 150:
                            body_content = f"{summary_text}\n\n{page_text}"
                except Exception:
                    pass

                content_hash = hashlib.sha256((url + title).encode("utf-8")).hexdigest()

                with get_db() as c:
                    cur = c.execute("""
                        INSERT OR IGNORE INTO raw_docs (source, url, title, body, content_hash)
                        VALUES ('live_rss_search', ?, ?, ?, ?)
                    """, (url, title, body_content, content_hash))
                    
                    if cur.rowcount > 0:
                        total_new += 1
                        print(f"  [+] Ingested: {title[:65]}...")

    return total_new