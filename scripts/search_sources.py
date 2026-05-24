#!/usr/bin/env python3
"""
Automated Web Search for Financial News Sources
================================================
Searches all configured sources via DuckDuckGo, replacing the need for
manual anysearch agent interaction.

Called by daily_brief.sh — fully automated, no Codex needed.

Rate limiting: 3s between queries to avoid blocking.
"""

import json
import os
import sys
import time
import hashlib
import argparse
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False


def now_beijing_str():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def generate_id(*parts):
    return hashlib.md5(":".join(parts).encode()).hexdigest()[:12]


def search_query(ddgs, query_text, source_id, source_name, category, lang, reliability, since_date, max_results=5):
    """Search a single query and return structured results."""
    results = []
    try:
        # Add time constraint to query
        full_query = query_text
        if since_date:
            full_query = f"{query_text} after:{since_date}"

        raw = list(ddgs.text(full_query, max_results=max_results))
        for r in raw:
            title = r.get("title", "")[:200]
            href = r.get("href", "")
            body = r.get("body", "")[:300]

            if not title:
                continue

            results.append({
                "id": generate_id(source_id, title, href),
                "title": title,
                "url": href,
                "summary": body,
                "published": "",  # DDG doesn't always return dates
                "source_id": source_id,
                "source_name": source_name,
                "category": category,
                "lang": lang,
                "reliability": reliability,
                "fetch_method": "web_search",
            })
    except Exception as e:
        print(f"    Search error: {e}", file=sys.stderr)

    return results


def main():
    parser = argparse.ArgumentParser(description="Automated web search for news sources")
    parser.add_argument("--queries", "-q", required=True, help="Path to queries.json")
    parser.add_argument("--output", "-o", default="results.json", help="Output JSON file")
    parser.add_argument("--since", help="Only search news after this date (YYYY-MM-DD)")
    parser.add_argument("--max-per-source", type=int, default=5, help="Max results per source")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between queries (seconds)")
    parser.add_argument("--limit", type=int, default=0, help="Limit total queries (0=all)")
    args = parser.parse_args()

    if not HAS_DDGS:
        print("Error: duckduckgo_search not installed.", file=sys.stderr)
        print("Run: pip3 install duckduckgo_search", file=sys.stderr)
        sys.exit(1)

    with open(args.queries, "r", encoding="utf-8") as f:
        qdata = json.load(f)

    queries = qdata.get("queries", [])
    if args.limit > 0:
        queries = queries[:args.limit]

    total = len(queries)
    print(f"[{now_beijing_str()}] Searching {total} sources...")
    print(f"  Since: {args.since or 'no filter'}")
    print(f"  Delay: {args.delay}s between queries")
    print(f"  Max/source: {args.max_per_source}")
    print()

    all_items = []
    ddgs = DDGS()

    for i, q in enumerate(queries):
        sid = q["source_id"]
        sname = q["source_name"]
        print(f"  [{i+1}/{total}] {sname} ...", end=" ", flush=True)

        items = search_query(
            ddgs,
            q["search_query"],
            sid, sname,
            q.get("category", ""),
            q.get("lang", ""),
            q.get("reliability", ""),
            args.since,
            max_results=args.max_per_source,
        )
        all_items.extend(items)
        print(f"{len(items)} results")

        if i < total - 1:
            time.sleep(args.delay)

    ddgs.__exit__(None, None, None)

    output = {
        "collected_at": now_beijing_str(),
        "since_date": args.since or qdata.get("since_date", ""),
        "time_range": qdata.get("time_range", ""),
        "item_count": len(all_items),
        "sources_searched": total,
        "items": all_items,
        "pending_queries_count": 0,
        "pending_queries": [],
        "pending_note": "All sources searched automatically.",
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    sources_found = len(set(i["source_id"] for i in all_items))
    print(f"\n[{now_beijing_str()}] Done!")
    print(f"  Total items: {len(all_items)}")
    print(f"  Sources with results: {sources_found}/{total}")
    print(f"  Output: {args.output}")


if __name__ == "__main__":
    main()
