#!/usr/bin/env python3
"""
Daily News Fetcher — Direct RSS collection
===========================================
Fetches news from sources with stable RSS feeds (Reuters, CNBC).
For all other sources, tracking is handled via anysearch queries.

The morning pipeline:
  1. fetch_news.py search --all --days 1  → generates queries.json
  2. daily_fetch.py (this script)          → RSS direct fetch + tracks pending
  3. export_pdf.py                         → PDF from whatever we have
  4. User opens Codex, runs anysearch      → fills in remaining sources
"""

import json
import os
import sys
import hashlib
import argparse
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BEIJING_TZ = timezone(timedelta(hours=8))

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

# Verified RSS feeds
RSS_SOURCES = [
    {
        "source_id": "cnbc",
        "source_name": "CNBC",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "category": "global_markets",
        "lang": "en",
        "reliability": "high",
    },
]


def now_beijing():
    return datetime.now(BEIJING_TZ)


def now_beijing_str():
    return now_beijing().strftime("%Y-%m-%d %H:%M:%S")


def generate_id(*parts):
    return hashlib.md5(":".join(parts).encode()).hexdigest()[:12]


def fetch_rss(cfg, since_date=None, limit=15):
    """Fetch from a single RSS source."""
    if not HAS_FEEDPARSER:
        return []

    print(f"  [{cfg['source_id'].upper()}] {cfg['source_name']} RSS ...")
    try:
        feed = feedparser.parse(cfg["url"])
    except Exception as e:
        print(f"    Error: {e}")
        return []

    if feed.bozo and not feed.entries:
        print(f"    Feed error: {feed.bozo_exception}")
        return []

    items = []
    for entry in feed.entries[:limit]:
        pub_str = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub_dt = datetime(*entry.published_parsed[:6])
            pub_str = pub_dt.strftime("%Y-%m-%d %H:%M")

        # Time filter
        if since_date and pub_str and pub_str[:10] < since_date:
            continue

        title = entry.get("title", "")[:200]
        link = entry.get("link", "")
        summary = (entry.get("summary", entry.get("description", "")))[:300]

        items.append({
            "id": generate_id(cfg["source_id"], title, link),
            "title": title,
            "url": link,
            "summary": summary,
            "published": pub_str,
            "source_id": cfg["source_id"],
            "source_name": cfg["source_name"],
            "category": cfg["category"],
            "lang": cfg["lang"],
            "reliability": cfg["reliability"],
            "fetch_method": "rss",
        })

    print(f"    Got {len(items)} items")
    return items


def fetch_all(since_date=None, limit=15):
    """Fetch all RSS sources."""
    all_items = []
    for cfg in RSS_SOURCES:
        try:
            items = fetch_rss(cfg, since_date=since_date, limit=limit)
            all_items.extend(items)
        except Exception as e:
            print(f"  [{cfg['source_id']}] Unexpected error: {e}")
    return all_items


def main():
    parser = argparse.ArgumentParser(description="Daily RSS news fetcher")
    parser.add_argument("--queries", "-q", help="Path to queries.json for pending tracking")
    parser.add_argument("--output", "-o", default="results.json", help="Output JSON file")
    parser.add_argument("--since", help="Only keep items after this date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=15, help="Items per RSS feed")
    args = parser.parse_args()

    print(f"[{now_beijing_str()}] Starting RSS fetch...")
    print(f"  Since: {args.since or 'no filter'}")
    print()

    results = fetch_all(since_date=args.since, limit=args.limit)
    fetched_ids = {r["source_id"] for r in results}

    # Load queries to determine pending
    pending_queries = []
    if args.queries and os.path.exists(args.queries):
        with open(args.queries, "r", encoding="utf-8") as f:
            qdata = json.load(f)
        pending_queries = [q for q in qdata.get("queries", []) if q["source_id"] not in fetched_ids]

    # Also try to import items from queries.json if it has results from anysearch
    # (for when the user runs anysearch and feeds results back)
    existing_from_queries = []
    if args.queries and os.path.exists(args.queries):
        with open(args.queries, "r", encoding="utf-8") as f:
            qdata = json.load(f)
        # Merge any pre-existing results
        existing_from_queries = qdata.get("items", qdata.get("results", []))

    all_items = results + existing_from_queries

    output = {
        "collected_at": now_beijing_str(),
        "since_date": args.since or "",
        "item_count": len(all_items),
        "rss_sources": sorted(fetched_ids),
        "items": all_items,
        "pending_queries_count": len(pending_queries),
        "pending_queries": pending_queries,
        "pending_note": (
            f"{len(pending_queries)} sources need anysearch. "
            "Open Codex and say: '搜集今日财经新闻' to complete the brief."
        ) if pending_queries else "All sources covered.",
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[{now_beijing_str()}] Done: {len(all_items)} items -> {args.output}")
    if pending_queries:
        print(f"  ⚠️  {len(pending_queries)} sources pending (need anysearch)")
        print(f"  Pending: {', '.join(q['source_name'] for q in pending_queries[:8])}...")


if __name__ == "__main__":
    main()
