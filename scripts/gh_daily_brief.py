#!/usr/bin/env python3
"""
GitHub Actions Daily Financial Brief
=====================================
Runs on GitHub Actions at 00:40 UTC (08:40 Beijing) daily.
Collects news from 39 sources via DuckDuckGo search, generates
a summary report, and emails it to your phone.

Dependencies (auto-installed by workflow):
    pip install duckduckgo_search reportlab

Secrets to set in GitHub:
    EMAIL_SENDER   - your QQ/Gmail address
    EMAIL_PASSWORD - QQ auth code or Gmail app password
    EMAIL_TO       - recipient (usually same as sender)
"""

import json
import os
import sys
import time
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from pathlib import Path

BEIJING_TZ = timezone(timedelta(hours=8))

# ---- Source config (embedded so workflow doesn't need file I/O) ----
SOURCES = [
    # Chinese Media
    {"id": "cls", "name": "财联社", "query": "site:cls.cn 最新财经快讯", "cat": "breaking_news", "lang": "zh", "rel": "high"},
    {"id": "sina_finance", "name": "新浪财经", "query": "site:finance.sina.com.cn 最新财经新闻", "cat": "comprehensive", "lang": "zh", "rel": "high"},
    {"id": "eastmoney", "name": "东方财富", "query": "site:eastmoney.com 最新要闻", "cat": "comprehensive", "lang": "zh", "rel": "high"},
    {"id": "wallstreetcn", "name": "华尔街见闻", "query": "site:wallstreetcn.com 最新资讯", "cat": "global_finance", "lang": "zh", "rel": "high"},
    {"id": "stcn", "name": "证券时报", "query": "site:stcn.com 最新证券新闻", "cat": "securities", "lang": "zh", "rel": "high"},
    {"id": "cs_com_cn", "name": "中国证券报", "query": "site:cs.com.cn 最新证券资讯", "cat": "securities", "lang": "zh", "rel": "high"},
    {"id": "yicai", "name": "第一财经", "query": "site:yicai.com 最新财经新闻", "cat": "comprehensive", "lang": "zh", "rel": "high"},
    {"id": "21jingji", "name": "21世纪经济报道", "query": "site:21jingji.com 最新财经", "cat": "comprehensive", "lang": "zh", "rel": "high"},
    # Research Reports
    {"id": "goldman_sachs", "name": "高盛研报", "query": "site:goldmansachs.com China research report", "cat": "investment_research", "lang": "en", "rel": "highest"},
    {"id": "jpmorgan", "name": "摩根大通研报", "query": "site:jpmorgan.com China market insights", "cat": "investment_research", "lang": "en", "rel": "highest"},
    {"id": "morgan_stanley", "name": "摩根士丹利研报", "query": "site:morganstanley.com China equity research", "cat": "investment_research", "lang": "en", "rel": "highest"},
    {"id": "citic_research", "name": "中信证券研究", "query": "中信证券 最新研报 A股策略", "cat": "domestic_research", "lang": "zh", "rel": "highest"},
    {"id": "cicc_research", "name": "中金公司研究", "query": "中金公司 最新研报 策略", "cat": "domestic_research", "lang": "zh", "rel": "highest"},
    {"id": "htsc_research", "name": "华泰证券研究", "query": "华泰证券 最新研报 行业分析", "cat": "domestic_research", "lang": "zh", "rel": "highest"},
    {"id": "gtja_research", "name": "国泰君安研究", "query": "国泰君安 最新研报 策略", "cat": "domestic_research", "lang": "zh", "rel": "highest"},
    # International Media
    {"id": "reuters", "name": "路透社", "query": "site:reuters.com China finance markets latest", "cat": "global_news", "lang": "en", "rel": "highest"},
    {"id": "bloomberg", "name": "彭博社", "query": "site:bloomberg.com China economy market", "cat": "global_finance", "lang": "en", "rel": "highest"},
    {"id": "cnbc", "name": "CNBC", "query": "site:cnbc.com China Asia markets latest", "cat": "global_markets", "lang": "en", "rel": "high"},
    {"id": "wsj", "name": "华尔街日报", "query": "site:wsj.com China finance economy", "cat": "global_finance", "lang": "en", "rel": "highest"},
    {"id": "ft", "name": "金融时报", "query": "site:ft.com China markets economy", "cat": "global_finance", "lang": "en", "rel": "highest"},
    # Chinese Government
    {"id": "gov_cn", "name": "中国政府网", "query": "site:gov.cn 产业政策 最新", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "ndrc", "name": "国家发改委", "query": "site:ndrc.gov.cn 产业政策 通知", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "miit", "name": "工信部", "query": "site:miit.gov.cn 产业政策 通知公告", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "mofcom", "name": "商务部", "query": "site:mofcom.gov.cn 政策 公告", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "mof_cn", "name": "财政部", "query": "site:mof.gov.cn 政策 通知", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "pbc", "name": "中国人民银行", "query": "site:pbc.gov.cn 货币政策 公告", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "csrc", "name": "证监会", "query": "site:csrc.gov.cn 公告 政策", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "nfra", "name": "金融监管总局", "query": "site:nfra.gov.cn 政策 通知", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "stats_cn", "name": "国家统计局", "query": "site:stats.gov.cn 数据发布", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    # International Government
    {"id": "federal_reserve", "name": "美联储", "query": "site:federalreserve.gov FOMC press release", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "us_treasury", "name": "美国财政部", "query": "site:home.treasury.gov sanctions policy", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "us_commerce", "name": "美国商务部", "query": "site:commerce.gov export control entity list China", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "ustr", "name": "USTR", "query": "site:ustr.gov China tariff trade", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "ecb", "name": "欧洲央行", "query": "site:ecb.europa.eu monetary policy decision", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "eu_commission", "name": "欧盟委员会", "query": "site:ec.europa.eu trade China anti-subsidy", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "boe", "name": "英国央行", "query": "site:bankofengland.co.uk monetary policy", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "boj", "name": "日本央行", "query": "site:boj.or.jp monetary policy statement", "cat": "intl_government", "lang": "en", "rel": "highest"},
]

SMTP_CONFIG = {
    "qq.com": {"host": "smtp.qq.com", "port": 465, "ssl": True},
    "gmail.com": {"host": "smtp.gmail.com", "port": 465, "ssl": True},
    "163.com": {"host": "smtp.163.com", "port": 465, "ssl": True},
}


def now_bj():
    return datetime.now(BEIJING_TZ)


def generate_id(*parts):
    return hashlib.md5(":".join(parts).encode()).hexdigest()[:12]


def search_all(ddgs, sources, since_date, max_per=5):
    """Search all sources and return structured results."""
    all_items = []
    total = len(sources)

    for i, src in enumerate(sources):
        query = f"{src['query']} 近1天" if "近" not in src["query"] else src["query"]
        if since_date:
            query = f"{query} after:{since_date}"

        print(f"  [{i+1}/{total}] {src['name']}...", end=" ", flush=True)
        try:
            raw = list(ddgs.text(query, max_results=max_per))
            for r in raw:
                title = r.get("title", "")
                href = r.get("href", "")
                body = r.get("body", "")
                if title:
                    all_items.append({
                        "id": generate_id(src["id"], title, href),
                        "title": title[:200],
                        "url": href,
                        "summary": body[:300],
                        "source_id": src["id"],
                        "source_name": src["name"],
                        "category": src["cat"],
                        "lang": src["lang"],
                        "reliability": src["rel"],
                    })
            print(f"{len([x for x in all_items if x['source_id']==src['id']])} items")
        except Exception as e:
            print(f"ERROR: {e}")

        if i < total - 1:
            time.sleep(2)

    return all_items


def build_report(items, date_str):
    """Build plain-text summary for email body."""
    lines = []
    lines.append(f"📰 每日财经要闻")
    lines.append(f"日期: {date_str}")
    lines.append(f"共搜集 {len(items)} 条新闻")
    lines.append("")

    by_cat = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

    cat_labels = {
        "breaking_news": "⚡ 快讯/突发",
        "comprehensive": "📋 综合财经",
        "global_finance": "🌐 全球金融",
        "global_news": "📡 国际通讯社",
        "global_markets": "📈 全球市场",
        "securities": "📜 证券监管",
        "investment_research": "🏦 国际投行",
        "domestic_research": "🏢 国内券商",
        "cn_government": "🇨🇳 中国政策",
        "intl_government": "🌍 国际政策",
    }

    for cat in ["breaking_news", "cn_government", "intl_government", "comprehensive",
                 "global_news", "global_markets", "investment_research", "domestic_research",
                 "global_finance", "securities"]:
        if cat in by_cat:
            label = cat_labels.get(cat, cat)
            lines.append(f"\n{label}")
            for item in by_cat[cat][:5]:
                src = item["source_name"]
                title = item["title"][:100]
                lines.append(f"  • [{src}] {title}")

    sources_hit = len(set(i["source_id"] for i in items))
    lines.append(f"\n\n📊 覆盖 {sources_hit}/37 个来源")
    lines.append("\n---")
    lines.append("本报告由 Financial News Collector 自动生成（GitHub Actions）")

    return "\n".join(lines)


def send_email(sender, password, to, subject, body):
    domain = sender.split("@")[-1].lower()
    smtp = SMTP_CONFIG.get(domain, {"host": f"smtp.{domain}", "port": 465, "ssl": True})

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if smtp["ssl"]:
        server = smtplib.SMTP_SSL(smtp["host"], smtp["port"], timeout=30)
    else:
        server = smtplib.SMTP(smtp["host"], smtp["port"], timeout=30)
        server.starttls()

    try:
        server.login(sender, password)
        server.sendmail(sender, [to], msg.as_string())
        print(f"  Email sent to {to}")
    finally:
        server.quit()


def main():
    print(f"[{now_bj().strftime('%Y-%m-%d %H:%M:%S')}] Starting...")
    print()

    # Get yesterday's date
    yesterday = (now_bj() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_str = now_bj().strftime("%Y-%m-%d")
    print(f"  Target: {yesterday} (yesterday)")
    print(f"  Sources: {len(SOURCES)}")
    print()

    # Search
    from duckduckgo_search import DDGS
    ddgs = DDGS()
    print("  Searching...")
    items = search_all(ddgs, SOURCES, since_date=yesterday, max_per=5)
    ddgs.__exit__(None, None, None)
    print(f"\n  Total: {len(items)} items")
    print()

    # Build report
    report = build_report(items, today_str)
    print("  Report preview:")
    for line in report.split("\n")[:15]:
        print(f"    {line}")
    print()

    # Send email
    sender = os.environ.get("EMAIL_SENDER", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    recipient = os.environ.get("EMAIL_TO", sender)

    if sender and password:
        print("  Sending email...")
        send_email(sender, password, recipient,
                   f"📰 每日财经要闻 {today_str}", report)
    else:
        print("  ⚠️  EMAIL_SENDER/EMAIL_PASSWORD not set, skipping email")
        print(report)

    print(f"\n[{now_bj().strftime('%Y-%m-%d %H:%M:%S')}] Done!")


if __name__ == "__main__":
    main()
