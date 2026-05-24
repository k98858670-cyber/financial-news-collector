#!/usr/bin/env python3
"""
GitHub Actions Daily Financial Brief
=====================================
Runs on GitHub Actions at 00:40 UTC (08:40 Beijing) daily.
1. Searches 37 sources via DuckDuckGo
2. Generates a formatted PDF report
3. Emails it to your phone with PDF attachment

Dependencies (auto-installed by workflow):
    pip install duckduckgo_search reportlab

GitHub Secrets required:
    EMAIL_SENDER   - your QQ/Gmail address
    EMAIL_PASSWORD - QQ auth code or Gmail app password
    EMAIL_TO       - recipient
"""

import json
import os
import sys
import time
import hashlib
import smtplib
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))

SOURCES = [
    {"id": "cls", "name": "财联社", "query": "site:cls.cn 最新财经快讯", "cat": "breaking_news", "lang": "zh", "rel": "high"},
    {"id": "sina_finance", "name": "新浪财经", "query": "site:finance.sina.com.cn 最新财经新闻", "cat": "comprehensive", "lang": "zh", "rel": "high"},
    {"id": "eastmoney", "name": "东方财富", "query": "site:eastmoney.com 最新要闻", "cat": "comprehensive", "lang": "zh", "rel": "high"},
    {"id": "wallstreetcn", "name": "华尔街见闻", "query": "site:wallstreetcn.com 最新资讯", "cat": "global_finance", "lang": "zh", "rel": "high"},
    {"id": "stcn", "name": "证券时报", "query": "site:stcn.com 最新证券新闻", "cat": "securities", "lang": "zh", "rel": "high"},
    {"id": "cs_com_cn", "name": "中国证券报", "query": "site:cs.com.cn 最新证券资讯", "cat": "securities", "lang": "zh", "rel": "high"},
    {"id": "yicai", "name": "第一财经", "query": "site:yicai.com 最新财经新闻", "cat": "comprehensive", "lang": "zh", "rel": "high"},
    {"id": "21jingji", "name": "21世纪经济报道", "query": "site:21jingji.com 最新财经", "cat": "comprehensive", "lang": "zh", "rel": "high"},
    {"id": "goldman_sachs", "name": "高盛研报", "query": "site:goldmansachs.com China research report", "cat": "investment_research", "lang": "en", "rel": "highest"},
    {"id": "jpmorgan", "name": "摩根大通研报", "query": "site:jpmorgan.com China market insights", "cat": "investment_research", "lang": "en", "rel": "highest"},
    {"id": "morgan_stanley", "name": "摩根士丹利研报", "query": "site:morganstanley.com China equity research", "cat": "investment_research", "lang": "en", "rel": "highest"},
    {"id": "citic_research", "name": "中信证券研究", "query": "中信证券 最新研报 A股策略", "cat": "domestic_research", "lang": "zh", "rel": "highest"},
    {"id": "cicc_research", "name": "中金公司研究", "query": "中金公司 最新研报 策略", "cat": "domestic_research", "lang": "zh", "rel": "highest"},
    {"id": "htsc_research", "name": "华泰证券研究", "query": "华泰证券 最新研报 行业分析", "cat": "domestic_research", "lang": "zh", "rel": "highest"},
    {"id": "gtja_research", "name": "国泰君安研究", "query": "国泰君安 最新研报 策略", "cat": "domestic_research", "lang": "zh", "rel": "highest"},
    {"id": "reuters", "name": "路透社", "query": "site:reuters.com China finance markets", "cat": "global_news", "lang": "en", "rel": "highest"},
    {"id": "bloomberg", "name": "彭博社", "query": "site:bloomberg.com China economy", "cat": "global_finance", "lang": "en", "rel": "highest"},
    {"id": "cnbc", "name": "CNBC", "query": "site:cnbc.com China Asia markets", "cat": "global_markets", "lang": "en", "rel": "high"},
    {"id": "wsj", "name": "华尔街日报", "query": "site:wsj.com China finance", "cat": "global_finance", "lang": "en", "rel": "highest"},
    {"id": "ft", "name": "金融时报", "query": "site:ft.com China markets", "cat": "global_finance", "lang": "en", "rel": "highest"},
    {"id": "gov_cn", "name": "中国政府网", "query": "site:gov.cn 产业政策 最新", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "ndrc", "name": "国家发改委", "query": "site:ndrc.gov.cn 产业政策", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "miit", "name": "工信部", "query": "site:miit.gov.cn 产业政策", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "mofcom", "name": "商务部", "query": "site:mofcom.gov.cn 公告", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "mof_cn", "name": "财政部", "query": "site:mof.gov.cn 政策 通知", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "pbc", "name": "中国人民银行", "query": "site:pbc.gov.cn 货币政策", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "csrc", "name": "证监会", "query": "site:csrc.gov.cn 公告", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "nfra", "name": "金融监管总局", "query": "site:nfra.gov.cn 通知", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "stats_cn", "name": "国家统计局", "query": "site:stats.gov.cn 数据发布", "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "federal_reserve", "name": "美联储", "query": "site:federalreserve.gov FOMC press release", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "us_treasury", "name": "美国财政部", "query": "site:home.treasury.gov sanctions", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "us_commerce", "name": "美国商务部", "query": "site:commerce.gov export control", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "ustr", "name": "USTR", "query": "site:ustr.gov China tariff", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "ecb", "name": "欧洲央行", "query": "site:ecb.europa.eu monetary policy", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "eu_commission", "name": "欧盟委员会", "query": "site:ec.europa.eu trade China", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "boe", "name": "英国央行", "query": "site:bankofengland.co.uk monetary policy", "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "boj", "name": "日本央行", "query": "site:boj.or.jp monetary policy", "cat": "intl_government", "lang": "en", "rel": "highest"},
]

SMTP_CONFIG = {
    "qq.com": {"host": "smtp.qq.com", "port": 465, "ssl": True},
    "gmail.com": {"host": "smtp.gmail.com", "port": 465, "ssl": True},
    "163.com": {"host": "smtp.163.com", "port": 465, "ssl": True},
}

CAT_LABELS = {
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


def now_bj():
    return datetime.now(BEIJING_TZ)


def generate_id(*parts):
    return hashlib.md5(":".join(parts).encode()).hexdigest()[:12]


def search_all(ddgs, sources, since_date, max_per=5):
    all_items = []
    total = len(sources)
    for i, src in enumerate(sources):
        query = f"{src['query']} 近1天" if "近" not in src["query"] else src["query"]
        if since_date:
            query = f"{query} after:{since_date}"
        print(f"  [{i+1}/{total}] {src['name']}...", end=" ", flush=True)
        try:
            raw = list(ddgs.text(query, max_results=max_per))
            count = 0
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
                    count += 1
            print(f"{count} items")
        except Exception as e:
            print(f"ERR: {e}")
        if i < total - 1:
            time.sleep(2)
    return all_items


def build_text_report(items, date_str):
    lines = [f"📰 每日财经要闻", f"日期: {date_str}", f"共搜集 {len(items)} 条新闻", ""]
    by_cat = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)
    cat_order = ["breaking_news", "cn_government", "intl_government", "comprehensive",
                 "global_news", "global_markets", "investment_research", "domestic_research",
                 "global_finance", "securities"]
    for cat in cat_order:
        if cat in by_cat:
            label = CAT_LABELS.get(cat, cat)
            lines.append(f"\n{label}")
            for item in by_cat[cat][:5]:
                src = item["source_name"]
                title = item["title"][:100]
                url = item.get("url", "")
                lines.append(f"  • [{src}] {title}")
                if url:
                    lines.append(f"    {url}")
    sources_hit = len(set(i["source_id"] for i in items))
    lines.append(f"\n\n📊 覆盖 {sources_hit}/{len(SOURCES)} 个来源")
    lines.append("\n---")
    lines.append("本报告由 Financial News Collector 自动生成（GitHub Actions）")
    return "\n".join(lines)


def build_pdf(items, date_str, pdf_path):
    """Generate a formatted PDF with Chinese support via Noto Sans CJK."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, grey
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, HRFlowable)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Try to register CJK font
    font_name = "Helvetica"
    cjk_fonts = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for fp in cjk_fonts:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont("CJK", fp))
                font_name = "CJK"
                break
            except Exception:
                pass

    # Try CID font fallback
    if font_name == "Helvetica":
        try:
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            font_name = "STSong-Light"
        except Exception:
            pass

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            title=f"每日财经新闻 {date_str}")

    styles = getSampleStyleSheet()
    title_s = ParagraphStyle('T', parent=styles['Title'], fontName=font_name,
                              fontSize=16, leading=22, spaceAfter=4, alignment=TA_CENTER,
                              textColor=HexColor('#1a1a2e'))
    sub_s = ParagraphStyle('S', parent=styles['Normal'], fontName=font_name,
                            fontSize=8, leading=10, textColor=grey, alignment=TA_CENTER, spaceAfter=12)
    h2_s = ParagraphStyle('H', parent=styles['Heading2'], fontName=font_name,
                           fontSize=11, leading=16, textColor=HexColor('#e94560'),
                           spaceBefore=12, spaceAfter=4)
    body_s = ParagraphStyle('B', parent=styles['Normal'], fontName=font_name,
                             fontSize=8, leading=12, spaceAfter=2, alignment=TA_JUSTIFY)
    src_s = ParagraphStyle('R', parent=styles['Normal'], fontName=font_name,
                            fontSize=6, leading=8, textColor=grey)
    foot_s = ParagraphStyle('F', parent=styles['Normal'], fontName=font_name,
                             fontSize=6, leading=8, textColor=grey, alignment=TA_CENTER)

    story = [Spacer(1, 0.5*cm),
             Paragraph(f"每日财经新闻聚合报告", title_s),
             Paragraph(f"日期: {date_str}　|　新闻条数: {len(items)}　|　自动生成", sub_s),
             HRFlowable(width="100%", thickness=1, color=HexColor('#e94560')),
             Spacer(1, 8)]

    by_cat = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

    cat_order = ["breaking_news", "cn_government", "intl_government", "comprehensive",
                 "global_news", "global_markets", "investment_research", "domestic_research",
                 "global_finance", "securities"]

    for cat in cat_order:
        if cat not in by_cat:
            continue
        label = CAT_LABELS.get(cat, cat)
        story.append(Paragraph(label, h2_s))
        for item in by_cat[cat][:6]:
            title = item["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            url = item["url"]
            summary = item.get("summary", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            source = item["source_name"]
            published = item.get("published", "")

            link_text = f'<font color="blue"><u><a href="{url}">{title}</a></u></font>'
            story.append(Paragraph(link_text, body_s))
            src_line = f"{source}　|　{published}" if published else source
            story.append(Paragraph(src_line, src_s))
            if summary and summary != title:
                story.append(Paragraph(summary[:200], body_s))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 4))

    story.append(HRFlowable(width="100%", thickness=0.5, color=grey))
    story.append(Spacer(1, 6))
    story.append(Paragraph("本报告由 Financial News Collector 自动生成　|　仅供参考，不构成投资建议", foot_s))

    doc.build(story)
    return pdf_path


def send_email(sender, password, to, subject, body, pdf_path=None):
    domain = sender.split("@")[-1].lower()
    smtp = SMTP_CONFIG.get(domain, {"host": f"smtp.{domain}", "port": 465, "ssl": True})

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f'attachment; filename="{os.path.basename(pdf_path)}"')
        msg.attach(part)

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
    print(f"[{now_bj().strftime('%Y-%m-%d %H:%M:%S')}] Daily Brief starting...")
    yesterday = (now_bj() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_str = now_bj().strftime("%Y-%m-%d")
    print(f"  Target date: {yesterday}")

    # 1. Search
    print(f"\n  [1/4] Searching {len(SOURCES)} sources...")
    from duckduckgo_search import DDGS
    ddgs = DDGS()
    items = search_all(ddgs, SOURCES, since_date=yesterday, max_per=5)
    ddgs.__exit__(None, None, None)
    print(f"  Total: {len(items)} items from {len(set(i['source_id'] for i in items))} sources")

    # 2. Build text summary
    print(f"\n  [2/4] Building report...")
    text_report = build_text_report(items, today_str)

    # 3. Generate PDF
    print(f"\n  [3/4] Generating PDF...")
    pdf_path = os.path.join(tempfile.gettempdir(), f"每日财经新闻_{today_str}.pdf")
    build_pdf(items, today_str, pdf_path)
    size_kb = os.path.getsize(pdf_path) / 1024
    print(f"  PDF: {pdf_path} ({size_kb:.1f} KB)")

    # 4. Send email
    print(f"\n  [4/4] Sending email...")
    sender = os.environ.get("EMAIL_SENDER", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    recipient = os.environ.get("EMAIL_TO", sender)

    if sender and password:
        send_email(sender, password, recipient,
                   f"📰 每日财经要闻 {today_str}", text_report, pdf_path)
        print(f"  Done! Email with PDF sent.")
    else:
        print("  ⚠️  EMAIL_SENDER/PASSWORD not set, SKIPPED")
        # Print report as fallback
        print(text_report)

    print(f"\n[{now_bj().strftime('%Y-%m-%d %H:%M:%S')}] All done!")


if __name__ == "__main__":
    main()
