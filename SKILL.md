---
name: financial-news-collector
description: >
  Collect real-time financial news and government policy from 35+ authoritative Chinese
  and international sources. Covers: Chinese media (财联社, 新浪财经, 东方财富, 华尔街见闻,
  证券时报, 中国证券报, 第一财经, 21世纪经济报道), global investment bank research
  (高盛, 摩根大通, 摩根士丹利), domestic brokerage research (中信, 中金, 华泰, 国泰君安),
  international wire services and media (路透社, 彭博社, CNBC, 华尔街日报, 金融时报),
  Chinese government policy agencies (中国政府网, 发改委, 工信部, 科技部, 商务部, 财政部,
  央行, 证监会, 金融监管总局, 统计局), and international government/central banks
  (美联储, 美国财政部, SEC, 商务部, USTR, 欧洲央行, 欧盟委员会, 英国央行, 日本央行).
  Use when the user asks to: gather financial news, monitor market-moving policy/regulation,
  collect research reports, track industry policy changes, compile daily news/policy digests,
  research sectors or companies, or build financial monitoring workflows. Triggers on:
  财经新闻, 搜集新闻, 产业政策, 政府政策, 法规, 市场快讯, 新闻聚合, 研报搜集,
  financial news, policy monitoring, market news aggregation, 投研新闻, 今日财经,
  每日财经要闻, 政策跟踪, 监管动态.
---

# Financial News Collector

## Overview

Collect timely, authentic financial news and government policy from 35+ authoritative sources:
Chinese media, international wire services, global investment bank research, domestic brokerage
reports, Chinese government agencies, and international central banks/regulators. Designed for
investors who need comprehensive, cross-verified market and policy intelligence.

## Quick Start



**Time control**: Default is . Use  for last N days,  for last N hours (overrides days). For real-time monitoring: .

## Core Workflow

### Step 1 — Generate Search Queries

Run `python3 scripts/fetch_news.py search` with appropriate flags:
- `--all` — all 35+ sources
- `--policy` — government/policy sources only (19 sources)
- `--category cn_government` — Chinese government agencies only
- `--category intl_government` — international government/central banks only
- `--keyword "关键词"` — add custom search terms

### Step 2 — Execute Searches via anysearch

Use the **anysearch** skill to execute the generated queries in parallel batches (5-8 per batch).
For each query result, extract: title, URL, snippet/summary, publication date, source attribution.

### Step 3 — Aggregate & Deduplicate

Collect results into a JSON array:
```json
{
  "title": "...",
  "url": "...",
  "summary": "...",
  "source_name": "...",
  "source_id": "...",
  "category": "...",
  "reliability": "...",
  "published": "..."
}
```

### Step 4 — Generate Report

```bash
python3 scripts/fetch_news.py report results.json -o report.md
```

## Source Categories

| Category | Count | Sources |
|----------|-------|---------|
| `breaking_news` | 1 | 财联社 |
| `comprehensive` | 4 | 新浪财经, 东方财富, 第一财经, 21世纪经济报道 |
| `securities` | 2 | 证券时报, 中国证券报 |
| `global_finance` | 4 | 华尔街见闻, 彭博社, 华尔街日报, 金融时报 |
| `global_news` | 1 | 路透社 |
| `global_markets` | 1 | CNBC |
| `investment_research` | 3 | 高盛, 摩根大通, 摩根士丹利 |
| `domestic_research` | 4 | 中信, 中金, 华泰, 国泰君安 |
| `cn_government` | 10 | 🇨🇳 国务院, 发改委, 工信部, 科技部, 商务部, 财政部, 央行, 证监会, 金融监管总局, 统计局 |
| `intl_government` | 9 | 🌍 美联储, 美财政部, SEC, 美商务部, USTR, 欧洲央行, 欧盟委员会, 英国央行, 日本央行 |

## Policy Authenticity Rules

When processing government policy content:

1. **Primary source first**: A policy announcement from 新华社 or media → trace it to the original .gov.cn/.gov document. Cite the official URL, not the media article.
2. **Document identification**: For Chinese policy, note 文号 (document number)、发文机关 (issuing body)、发布日期 and 生效日期.
3. **Impact assessment**: For each policy, briefly assess which sectors/companies are affected and how.
4. **Cross-reference**: Media interpretation of a policy should be cross-checked against the original document text — media can sensationalize or misread.
5. **Central bank events**: FOMC, ECB, BOJ, PBOC rate decisions → capture the decision, vote split (if any), forward guidance, and market reaction.

## Specialized Workflows

### Daily Policy Brief

```bash
python3 scripts/fetch_news.py search --policy -o policy.json
# Execute via anysearch, then:
python3 scripts/fetch_news.py report policy_results.json -o policy_brief.md
```

### Industry Policy Deep-Dive

```bash
python3 scripts/fetch_news.py search --category cn_government --keyword "新能源汽车" -o ev.json
python3 scripts/fetch_news.py search --category cn_government --keyword "半导体 集成电路" -o chip.json
```

### Global Macro Policy Radar

```bash
python3 scripts/fetch_news.py search --category intl_government -o global_policy.json
```

### Full Daily Digest (Media + Policy)

```bash
python3 scripts/fetch_news.py search --all -o full.json
# Execute via anysearch, filter, then report
```

### Regulatory Watch (A-share focused)

```bash
python3 scripts/fetch_news.py search --category cn_government --keyword "证监会 IPO 监管" -o reg.json
python3 scripts/fetch_news.py search --category cn_government --keyword "央行 货币政策" -o pbc.json
```

### US-China Trade Policy Tracking

```bash
python3 scripts/fetch_news.py search --source-id us_commerce,ustr,mofcom --keyword "关税 出口管制 实体清单"
```

## Time Range Control

The skill enforces news recency with `--days` (default: 7) or `--hours` flags:

| Flag | Example | Effect |
|------|---------|--------|
|  | 今日新闻 | Only news from today |
|  | 近3天 | Last 3 days |
|  | 近7天 (默认) | Last week |
|  | 近30天 | Last month |
|  | 近1小时 | Real-time monitoring |
|  | 近6小时 | Intraday updates |
|  | 近24小时 | Last trading day |

The time constraint is embedded in:
- Search query keywords (e.g. "近3天 新能源 政策")
- JSON output  field for downstream filtering
-  instructing anysearch to apply date filters

**Best practices:**
- Breaking news / intraday trading:  or 
- Daily market brief: 
- Weekly digest:  (default)
- Monthly policy review: 


## Daily Automated Brief (macOS)

### One-time setup



### What happens every morning

1. **08:40** —  triggers automatically
2. Generates 39 search queries targeting all sources (yesterday news)
3. Fetches directly available RSS feeds (CNBC etc.)
4. Exports PDF to 
5. Writes  listing sources that need anysearch completion

### After you open Codex

Say "完成今日财经简报" — Codex reads , runs anysearch on pending sources,
appends results to , and re-generates the PDF with full coverage.

### Manual run

==============================================
 Daily Financial News Brief
 Date: 2026-05-24 16:17:07
 Target: yesterday (2026-05-23)
 Output: /Users/mofurong/Documents/每日财经新闻/2026-05-24
==============================================

[1/4] Generating search queries for all sources...
Generated 39 queries (今日) -> /Users/mofurong/Documents/每日财经新闻/2026-05-24/queries.json
  -> 39 queries generated

[2/4] Direct fetching (RSS + API from cls/reuters/cnbc)...
[2026-05-24 16:17:07] Starting RSS fetch...
  Since: 2026-05-23

  [CNBC] CNBC RSS ...
    Got 13 items

[2026-05-24 16:17:08] Done: 13 items -> /Users/mofurong/Documents/每日财经新闻/2026-05-24/results.json
  ⚠️  38 sources pending (need anysearch)
  Pending: 财联社, 新浪财经, 东方财富, 华尔街见闻, 证券时报, 中国证券报, 第一财经, 21世纪经济报道...

[3/4] Generating PDF report...
Using font: STSong-Light
PDF generated: /Users/mofurong/Documents/每日财经新闻/2026-05-24/每日财经新闻_2026-05-24.pdf (6.9 KB)

[4/4] Checking pending sources...
  -> 38 sources pending (see pending.md)

==============================================
 ✅ Brief complete!
 PDF : /Users/mofurong/Documents/每日财经新闻/2026-05-24/每日财经新闻_2026-05-24.pdf
 Data: /Users/mofurong/Documents/每日财经新闻/2026-05-24/results.json (13 items)
 Pending: 38 sources
==============================================

### Disable



## Source Configuration

All sources in `scripts/sources.json` (v2.0). Each entry:
- `id`, `name`, `fetch_method`, `url`, `search_query`
- `category`: news category for grouping
- `subcategory`: finer-grained grouping (e.g. `central_bank`, `trade_policy`)
- `reliability`: all government sources are `highest`
- `lang`: `zh` | `en`

To add a source: insert an entry following the existing schema.

## Bundled Resources

### scripts/sources.json (v2.0)
35+ sources: media (13) + research reports (7) + government policy (19).

### scripts/fetch_news.py (v2.0)
Three-mode CLI with `--policy`, `--filter`, `--group` flags for policy-specific workflows.

### references/sources.md
Detailed profiles for every source: positioning, authority, key content, capital market impact, search tips.
