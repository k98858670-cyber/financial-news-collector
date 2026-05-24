#!/usr/bin/env python3
"""
Financial News Collector - Main Aggregation Script
===================================================
Collects financial news & policy from 39 authoritative Chinese and international sources:
  - Chinese media (8), Research reports (7), International media (5)
  - Chinese government policy (10 agencies), International government policy (9 bodies)

Three collection modes:
  1. 'search'  - Generate search queries for use with anysearch/web-search skill (PRIMARY)
  2. 'report'  - Generate a formatted Markdown report from collected data
  3. 'list'    - Display all configured sources

Usage:
    python3 fetch_news.py list
    python3 fetch_news.py search --all --days 3
    python3 fetch_news.py search --policy --days 7
    python3 fetch_news.py search --category cn_government --keyword "新能源" --hours 24
    python3 fetch_news.py report results.json -o report.md

Time control:
    --days N    Collect news from the last N days (default: 7)
    --hours N   Collect news from the last N hours (overrides --days)
"""

import json
import os
import sys
import argparse
import hashlib
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_FILE = os.path.join(SCRIPT_DIR, "sources.json")
BEIJING_TZ = timezone(timedelta(hours=8))

DEFAULT_DAYS = 7


def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def now_beijing():
    return datetime.now(BEIJING_TZ)


def now_beijing_str():
    return now_beijing().strftime("%Y-%m-%d %H:%M:%S")


def generate_id(*parts):
    return hashlib.md5(":".join(parts).encode()).hexdigest()[:12]


def all_sources(sources_data):
    for group_name, group in sources_data["sources"].items():
        if isinstance(group, list):
            for src in group:
                yield src
        elif isinstance(group, dict):
            for subgroup in group.values():
                if isinstance(subgroup, list):
                    for src in subgroup:
                        yield src


def sources_by_category(sources_data, categories):
    cat_set = set(c.strip() for c in categories.split(","))
    for src in all_sources(sources_data):
        if src.get("category") in cat_set:
            yield src


def sources_by_id(sources_data, ids):
    id_set = set(s.strip() for s in ids.split(","))
    for src in all_sources(sources_data):
        if src["id"] in id_set:
            yield src


def sources_by_group(sources_data, group_name):
    group = sources_data["sources"].get(group_name, {})
    if isinstance(group, list):
        yield from group
    elif isinstance(group, dict):
        for subgroup in group.values():
            if isinstance(subgroup, list):
                yield from subgroup


def time_description(days, hours):
    """Human-readable time range description in Chinese."""
    if hours:
        if hours <= 1:
            return "近1小时"
        elif hours < 24:
            return f"近{hours}小时"
        else:
            days = hours // 24
            return f"近{days}天"
    if days == 1:
        return "今日"
    elif days <= 7:
        return f"近{days}天"
    else:
        return f"近{days}天"


def build_time_constraint(now, days, hours):
    """Build time constraint metadata for search."""
    if hours:
        since = now - timedelta(hours=hours)
    else:
        since = now - timedelta(days=days)

    desc = time_description(days, hours)
    return {
        "time_range": desc,
        "since_date": since.strftime("%Y-%m-%d"),
        "since_iso": since.isoformat(),
        "search_hint": (
            f"Filter results to the last {days} days. "
            f"Use date filters in search: after:{since.strftime('%Y-%m-%d')} or equivalent. "
            f"Prefer results published after {since.strftime('%Y-%m-%d')}."
        ),
    }


# --- Commands ---

def cmd_list(args):
    sources_data = load_sources()
    filters = {
        "cn_policy": ["cn_government"],
        "intl_policy": ["intl_government"],
        "all_policy": ["cn_government", "intl_government"],
    }
    cat_filter = filters.get(args.filter)
    source_filter = args.source

    print("=" * 78)
    title = "  Financial News Collector — All Sources"
    if args.filter:
        title = f"  Financial News Collector — Filter: {args.filter}"
    print(title)
    print("=" * 78)

    for group_name, group in sources_data["sources"].items():
        labels = {
            "chinese_media": "🇨🇳 Chinese Media",
            "research_reports": "📊 Research Reports",
            "international_media": "🌍 International Media",
            "government_policy": "🏛️  Government & Policy",
        }
        label = labels.get(group_name, group_name)

        if isinstance(group, list):
            items = group
            if cat_filter:
                items = [s for s in items if s["category"] in cat_filter]
            if source_filter:
                items = [s for s in items if s["id"] in source_filter]
            if items:
                _print_source_table(label, items)
        elif isinstance(group, dict):
            subgroup_items = []
            for sub_name, sub_list in group.items():
                sub_label = {
                    "chinese_government": "  ├─ 中国政府机构",
                    "international_government": "  ├─ 国际政府/央行",
                }.get(sub_name, f"  ├─ {sub_name}")
                filtered = sub_list
                if cat_filter:
                    filtered = [s for s in filtered if s["category"] in cat_filter]
                if source_filter:
                    filtered = [s for s in filtered if s["id"] in source_filter]
                if filtered:
                    subgroup_items.append((sub_label, filtered))
            if subgroup_items:
                print(f"\n  {label}")
                for sub_label, sub_items in subgroup_items:
                    _print_source_table(sub_label, sub_items)


def _print_source_table(label, items):
    print(f"\n  {label}")
    print(f"  {'ID':<22} {'Name':<14} {'Method':<8} {'Reliability':<10}")
    print(f"  {'-'*22} {'-'*14} {'-'*8} {'-'*10}")
    for src in items:
        print(f"  {src['id']:<22} {src['name']:<14} {src['fetch_method']:<8} {src['reliability']:<10}")


def cmd_search(args):
    sources_data = load_sources()
    now = now_beijing()
    days = args.days if args.days else DEFAULT_DAYS
    hours = args.hours
    time_info = build_time_constraint(now, days, hours)

    targets = []
    if args.all:
        targets = list(all_sources(sources_data))
    elif args.source_id:
        targets = list(sources_by_id(sources_data, args.source_id))
    elif args.category:
        targets = list(sources_by_category(sources_data, args.category))
    elif args.group:
        targets = list(sources_by_group(sources_data, args.group))
    elif args.policy:
        targets = list(sources_by_category(sources_data, "cn_government,intl_government"))
    else:
        targets = list(all_sources(sources_data))

    if not targets:
        print("No sources matched.", file=sys.stderr)
        sys.exit(1)

    queries = []
    for src in targets:
        base_kw = args.keyword if args.keyword else src.get("search_query",
                                                             f"最新 {src['name']} 政策法规")
        # Append time hint to keyword for recency
        if hours:
            time_kw = f"近{hours}小时"
        else:
            time_kw = f"近{days}天"
        full_keyword = f"{base_kw} {time_kw}" if time_kw not in base_kw else base_kw

        queries.append({
            "source_id": src["id"],
            "source_name": src["name"],
            "search_query": full_keyword,
            "url": src["url"],
            "category": src["category"],
            "reliability": src["reliability"],
            "lang": src["lang"],
        })

    output = {
        "generated_at": now_beijing_str(),
        "time_range": time_info["time_range"],
        "since_date": time_info["since_date"],
        "query_count": len(queries),
        "time_search_hint": time_info["search_hint"],
        "instruction": (
            f"Collect news from the last {time_info['time_range']}. "
            "Use the anysearch skill (batch search) to execute these queries. "
            "Apply date filter: only keep results published after "
            f"{time_info['since_date']}. "
            "After collecting results, pipe the JSON output to 'fetch_news.py report' for formatting."
        ),
        "queries": queries,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Generated {len(queries)} queries ({time_info['time_range']}) -> {args.output}")
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_report(args):
    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    items = data.get("items", data.get("results", []))
    if not items:
        print("No news items found in input.", file=sys.stderr)
        sys.exit(1)

    time_range = data.get("time_range", "")
    lines = []
    lines.append(f"# 📰 财经新闻与政策聚合报告")
    lines.append(f"> 生成时间: {now_beijing_str()}")
    if time_range:
        lines.append(f"> 时间范围: {time_range}")
    lines.append(f"> 新闻条数: {len(items)}")
    lines.append("")

    by_category = {}
    for item in items:
        cat = item.get("category", "other")
        by_category.setdefault(cat, []).append(item)

    category_labels = {
        "breaking_news": "⚡ 快讯/突发新闻",
        "comprehensive": "📋 综合财经新闻",
        "global_finance": "🌐 全球金融市场",
        "global_news": "📡 国际通讯社",
        "global_markets": "📈 全球市场行情",
        "securities": "📜 证券/监管新闻",
        "investment_research": "🏦 国际投行研报",
        "domestic_research": "🏢 国内券商研报",
        "cn_government": "🇨🇳 中国政府产业政策",
        "intl_government": "🌍 国际政府/央行政策",
    }

    for cat, cat_items in sorted(by_category.items()):
        label = category_labels.get(cat, f"📌 {cat}")
        lines.append(f"## {label}")
        lines.append("")
        for item in cat_items[:15]:
            title = item.get("title", "无标题")
            url = item.get("url", "")
            summary = item.get("summary", item.get("snippet", ""))
            source = item.get("source_name", item.get("source", ""))
            reliability = item.get("reliability", "")
            published = item.get("published", item.get("date", ""))

            rel_icon = {"highest": "🟢", "high": "🔵"}.get(reliability, "⚪")

            lines.append(f"- {rel_icon} **[{title}]({url})**")
            if source:
                lines.append(f"  - 来源: {source} | {published}")
            if summary:
                lines.append(f"  - {summary[:200]}")
            lines.append("")

    report = "\n".join(lines)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to {args.output}")
    else:
        print(report)


def main():
    parser = argparse.ArgumentParser(
        description="Financial News Collector — aggregate news & policy from 39 authoritative sources"
    )
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="List all available news sources")
    list_p.add_argument("--filter", choices=["cn_policy", "intl_policy", "all_policy"],
                        help="Filter sources by policy type")
    list_p.add_argument("--source", help="Filter by source ID")

    search_p = sub.add_parser("search", help="Generate search queries for anysearch/web-search")
    search_p.add_argument("--all", action="store_true", help="All sources")
    search_p.add_argument("--policy", action="store_true", help="All government/policy sources only")
    search_p.add_argument("--source-id", help="Comma-separated source IDs")
    search_p.add_argument("--category", help="Comma-separated categories")
    search_p.add_argument("--group", help="Top-level group name (e.g. government_policy)")
    search_p.add_argument("--keyword", "-k", help="Custom search keyword")
    search_p.add_argument("--days", "-d", type=int, default=DEFAULT_DAYS,
                          help=f"Collect news from last N days (default: {DEFAULT_DAYS})")
    search_p.add_argument("--hours", type=int,
                          help="Collect news from last N hours (overrides --days)")
    search_p.add_argument("--output", "-o", help="Save queries to JSON file")

    report_p = sub.add_parser("report", help="Generate Markdown report from collected data")
    report_p.add_argument("input", nargs="?", help="Input JSON file (or stdin)")
    report_p.add_argument("--output", "-o", help="Save report to file")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
