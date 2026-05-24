#!/usr/bin/env python3
"""
============================================================
  Financial News Collector — GitHub Actions Daily Brief
============================================================
Runs at 08:40 Beijing time daily on GitHub Actions.

Pipeline:
  1. Search 41 sources via Google News RSS (POST, Lite fallback)
  2. LLM impact analysis via SiliconFlow (利好/利空/板块/个股)
  3. Generate PDF report (ReportLab + Noto Sans CJK)
  4. Generate DOCX report (python-docx)
  5. Generate Douyin carousel images (1080×1920, Pillow)
  6. Email to phone (QQ SMTP)

Dependencies: requests, reportlab, python-docx, Pillow
Secrets: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_TO, SF_API_KEY
"""

import os, sys, time, json, hashlib, re, smtplib, tempfile, textwrap
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import urllib.parse

import requests

BEIJING_TZ = timezone(timedelta(hours=8))

# ============================================================
# 41 Authoritative Sources
# ============================================================
SOURCES = [
    # ---- Chinese Media (10) ----
    {"id": "cls",           "name": "财联社",         "query": "财联社 最新财经快讯",       "cat": "breaking_news",      "lang": "zh", "rel": "high"},
    {"id": "sina_finance",  "name": "新浪财经",       "query": "新浪财经 最新财经新闻",     "cat": "comprehensive",      "lang": "zh", "rel": "high"},
    {"id": "eastmoney",     "name": "东方财富",       "query": "东方财富 最新财经要闻",     "cat": "comprehensive",      "lang": "zh", "rel": "high"},
    {"id": "wallstreetcn",  "name": "华尔街见闻",     "query": "华尔街见闻 最新资讯",       "cat": "global_finance",     "lang": "zh", "rel": "high"},
    {"id": "stcn",          "name": "证券时报",       "query": "证券时报 最新证券新闻",     "cat": "securities",         "lang": "zh", "rel": "high"},
    {"id": "cs_com_cn",     "name": "中国证券报",     "query": "中国证券报 最新证券资讯",   "cat": "securities",         "lang": "zh", "rel": "high"},
    {"id": "yicai",         "name": "第一财经",       "query": "第一财经 最新财经新闻",     "cat": "comprehensive",      "lang": "zh", "rel": "high"},
    {"id": "21jingji",      "name": "21世纪经济报道",  "query": "21世纪经济报道 最新财经",   "cat": "comprehensive",      "lang": "zh", "rel": "high"},
    {"id": "chinafundnews", "name": "中国基金报",     "query": "中国基金报 基金新闻",       "cat": "comprehensive",      "lang": "zh", "rel": "high"},
    {"id": "ce_cn",         "name": "经济日报",       "query": "经济日报 最新经济新闻",     "cat": "comprehensive",      "lang": "zh", "rel": "highest"},

    # ---- International Research (3) ----
    {"id": "goldman_sachs",  "name": "高盛研报",       "query": "Goldman Sachs China research report",        "cat": "investment_research", "lang": "en", "rel": "highest"},
    {"id": "jpmorgan",       "name": "摩根大通研报",    "query": "JPMorgan China market insights report",      "cat": "investment_research", "lang": "en", "rel": "highest"},
    {"id": "morgan_stanley", "name": "摩根士丹利研报",  "query": "Morgan Stanley China equity research",        "cat": "investment_research", "lang": "en", "rel": "highest"},

    # ---- Domestic Brokerage (4) ----
    {"id": "citic_research", "name": "中信证券研究",   "query": "中信证券 最新研报 A股策略",    "cat": "domestic_research",  "lang": "zh", "rel": "highest"},
    {"id": "cicc_research",  "name": "中金公司研究",   "query": "中金公司 最新研报 策略",        "cat": "domestic_research",  "lang": "zh", "rel": "highest"},
    {"id": "htsc_research",  "name": "华泰证券研究",   "query": "华泰证券 最新研报 行业分析",    "cat": "domestic_research",  "lang": "zh", "rel": "highest"},
    {"id": "gtja_research",  "name": "国泰君安研究",   "query": "国泰君安 最新研报 策略",        "cat": "domestic_research",  "lang": "zh", "rel": "highest"},

    # ---- International Media (5) ----
    {"id": "reuters",   "name": "路透社",     "query": "Reuters China finance markets latest news",  "cat": "global_news",     "lang": "en", "rel": "highest"},
    {"id": "bloomberg", "name": "彭博社",     "query": "Bloomberg China economy market news",        "cat": "global_finance",  "lang": "en", "rel": "highest"},
    {"id": "cnbc",      "name": "CNBC",      "query": "CNBC China Asia markets latest",             "cat": "global_markets",  "lang": "en", "rel": "high"},
    {"id": "wsj",       "name": "华尔街日报",  "query": "WSJ China finance economy news",            "cat": "global_finance",  "lang": "en", "rel": "highest"},
    {"id": "ft",        "name": "金融时报",   "query": "Financial Times China markets economy",     "cat": "global_finance",  "lang": "en", "rel": "highest"},

    # ---- Chinese Government (11) ----
    {"id": "gov_cn",   "name": "中国政府网",   "query": "中国政府网 最新产业政策",    "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "ndrc",     "name": "国家发改委",   "query": "国家发改委 最新产业政策",    "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "miit",     "name": "工信部",      "query": "工信部 最新产业政策",        "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "most_cn",  "name": "科技部",      "query": "科技部 最新科技政策",        "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "mofcom",   "name": "商务部",      "query": "商务部 最新贸易政策",        "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "mof_cn",   "name": "财政部",      "query": "财政部 最新财税政策",        "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "pbc",      "name": "中国人民银行", "query": "中国人民银行 货币政策",      "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "csrc",     "name": "证监会",      "query": "证监会 最新监管政策",        "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "nfra",     "name": "金融监管总局", "query": "金融监管总局 最新政策",      "cat": "cn_government", "lang": "zh", "rel": "highest"},
    {"id": "stats_cn", "name": "国家统计局",   "query": "国家统计局 最新经济数据",    "cat": "cn_government", "lang": "zh", "rel": "highest"},


    # ---- International Government (8) ----
    {"id": "federal_reserve", "name": "美联储",       "query": "Federal Reserve FOMC statement press release",     "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "us_treasury",     "name": "美国财政部",   "query": "US Treasury sanctions policy latest",             "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "us_sec",          "name": "美国SEC",     "query": "US SEC securities regulation China",              "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "us_commerce",     "name": "美国商务部",   "query": "US Commerce Department export control entity list","cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "ustr",            "name": "USTR",        "query": "USTR China tariff trade latest",                  "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "ecb",             "name": "欧洲央行",     "query": "ECB monetary policy decision press release",      "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "eu_commission",   "name": "欧盟委员会",   "query": "European Commission trade China anti-subsidy",    "cat": "intl_government", "lang": "en", "rel": "highest"},
    {"id": "boj",             "name": "日本央行",     "query": "Bank of Japan monetary policy statement",         "cat": "intl_government", "lang": "en", "rel": "highest"},
]
# Note: 英国央行 (boe) intentionally removed — rarely has direct China market impact.
# Total: 10 + 3 + 4 + 5 + 10 + 8 = 40 verified sources
# (科技部 added, 财政部 deduplicated from earlier error, 美国SEC restored)

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

CAT_ORDER = ["breaking_news", "cn_government", "intl_government", "comprehensive",
             "global_news", "global_markets", "investment_research", "domestic_research",
             "global_finance", "securities"]

SMTP_CFG = {
    "qq.com": ("smtp.qq.com", 465, True),
    "gmail.com": ("smtp.gmail.com", 465, True),
    "163.com": ("smtp.163.com", 465, True),
}

# ============================================================
# Utilities
# ============================================================
_session = None

def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        })
    return _session

def now_bj():
    return datetime.now(BEIJING_TZ)

def gen_id(*parts):
    return hashlib.md5(":".join(parts).encode()).hexdigest()[:12]

# ============================================================
# Google News RSS Search
# ============================================================

def google_news_search(query, max_results=8, retries=3):
    """Search Google News RSS — reliable globally, never blocked."""
    import xml.etree.ElementTree as ET
    sess = get_session()
    # Use Chinese locale for Chinese queries, English for English
    lang = "zh-CN" if any('一' <= c <= '鿿' for c in query) else "en-US"
    gl = "CN" if lang == "zh-CN" else "US"
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={lang}&gl={gl}&ceid={gl}:{lang.replace('-','')}"

    for attempt in range(retries):
        try:
            r = sess.get(url, timeout=20)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.text)
            items = root.findall(".//item")
            results = []
            for item in items[:max_results]:
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                pub_el = item.find("pubDate")
                source_el = item.find("source")

                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link = link_el.text.strip() if link_el is not None and link_el.text else ""
                desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                pub = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
                source = source_el.text.strip() if source_el is not None and source_el.text else ""

                # Clean Google News redirect URL to get real URL
                if "news.google.com" in link:
                    # Try to extract real URL from query params
                    import urllib.parse
                    parsed = urllib.parse.urlparse(link)
                    qs = urllib.parse.parse_qs(parsed.query)
                    real_url = qs.get("url", [link])[0]
                    link = real_url

                if title:
                    results.append({
                        "title": title, "href": link, "body": desc,
                        "published": pub, "source": source
                    })
            if results:
                return results
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(2)
    return []


def search_all(since_date, max_per=5):
    """Search all sources with progress tracking."""
    all_items = []
    failures = []
    total = len(SOURCES)

    for i, src in enumerate(SOURCES):
        query = src["query"]
        print(f"  [{i+1}/{total}] {src['name']:<12s} ", end="", flush=True)
        try:
            raw = google_news_search(query, max_results=max_per)
        except Exception as e:
            raw = []
            failures.append(src["name"])

        count = 0
        for r in raw:
            title = r.get("title", "")
            href = r.get("href", "")
            body = r.get("body", "")
            if title:
                # Strip HTML tags from title/body
                clean_title = re.sub(r'<[^>]+>', '', title)[:200]
                clean_body = re.sub(r'<[^>]+>', '', body)[:300]
                all_items.append({
                    "id": gen_id(src["id"], title, href),
                    "title": clean_title, "url": href, "summary": clean_body,
                    "source_id": src["id"], "source_name": src["name"],
                    "category": src["cat"], "lang": src["lang"], "reliability": src["rel"],
                })
                count += 1
        print(f"{count}")

        if i < total - 1:
            time.sleep(2)

    return all_items, failures


# ============================================================
# LLM Impact Analysis (SiliconFlow)
# ============================================================

def analyze_impact(items):
    """Use SiliconFlow LLM to tag each item: 利好/利空/中性 + sectors + stocks."""
    api_key = os.environ.get("SF_API_KEY", "")
    if not api_key:
        print("  ⚠️  SF_API_KEY not set — skipping impact analysis")
        return items

    print(f"  Analyzing {len(items)} items via SiliconFlow...")
    batch_size = 20
    analyzed = []

    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        batch_text = "\n".join(
            f"[{i}] {item['source_name']}: {item['title']}"
            for i, item in enumerate(batch))

        prompt = f"""Analyze these Chinese & global financial headlines for capital market impact.
Output a JSON array with one object per item:
[
  {{"idx": 0, "impact": "利好/利空/中性", "direction": "positive/negative/neutral",
    "sectors": ["sector1"], "stocks": ["stock1 ticker"],
    "reasoning": "1-sentence impact in Chinese"}}
]

Headlines:
{batch_text}

Output ONLY valid JSON array, nothing else."""

        try:
            resp = requests.post(
                "https://api.siliconflow.cn/v1/chat/completions",
                json={
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3, "max_tokens": 4000,
                },
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=90)
            content = resp.json()["choices"][0]["message"]["content"]

            # Extract JSON array
            js = content.find("[")
            je = content.rfind("]") + 1
            if js >= 0 and je > js:
                analyses = json.loads(content[js:je])
                for a in analyses:
                    idx = a.get("idx", -1)
                    if 0 <= idx < len(batch):
                        batch[idx]["impact"] = a.get("impact", "中性")
                        batch[idx]["direction"] = a.get("direction", "neutral")
                        batch[idx]["sectors"] = ", ".join(a.get("sectors", []))
                        batch[idx]["stocks"] = ", ".join(a.get("stocks", []))
                        batch[idx]["reasoning"] = a.get("reasoning", "")
        except Exception as e:
            print(f"    Batch {start} error: {e}")

        analyzed.extend(batch)
        print(f"    [{start+1}-{min(start+batch_size, len(items))}] done")
        if start + batch_size < len(items):
            time.sleep(1)

    return analyzed


# ============================================================
# Report Generators
# ============================================================

def text_report(items, date_str, failures):
    analyzed = sum(1 for i in items if i.get("impact"))
    lines = [
        f"📰 每日财经要闻",
        f"日期: {date_str}",
        f"共搜集 {len(items)} 条新闻 · {analyzed} 条已分析市场影响",
        f"失败来源: {len(failures)}" if failures else "",
        "",
    ]
    by_cat = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

    for cat in CAT_ORDER:
        if cat not in by_cat:
            continue
        lines.append(f"\n{CAT_LABELS.get(cat, cat)}")
        for item in by_cat[cat][:5]:
            impact = f" {item.get('impact','')}" if item.get("impact") else ""
            lines.append(f"  • [{item['source_name']}]{impact} {item['title'][:100]}")
            if item.get("reasoning"):
                lines.append(f"    💡 {item['reasoning'][:120]}")
            if item.get("stocks"):
                lines.append(f"    📈 关注: {item['stocks'][:150]}")
            if item.get("url"):
                lines.append(f"    {item['url']}")

    hits = len(set(i["source_id"] for i in items))
    lines.append(f"\n\n📊 覆盖 {hits}/{len(SOURCES)} 个来源")
    if failures:
        lines.append(f"⚠️ 搜索失败: {', '.join(failures)}")
    lines.append("\n---\n自动生成 · GitHub Actions")
    return "\n".join(lines)


def build_pdf(items, date_str, pdf_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, grey
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_name = "Helvetica"
    for fp in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
               "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"]:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont("CJK", fp))
                font_name = "CJK"
                break
            except: pass
    if font_name == "Helvetica":
        try:
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            font_name = "STSong-Light"
        except: pass

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    ts = ParagraphStyle('T', parent=styles['Title'], fontName=font_name,
                         fontSize=16, leading=22, spaceAfter=4, alignment=TA_CENTER,
                         textColor=HexColor('#1a1a2e'))
    ss = ParagraphStyle('S', parent=styles['Normal'], fontName=font_name,
                         fontSize=8, leading=10, textColor=grey, alignment=TA_CENTER, spaceAfter=12)
    hs = ParagraphStyle('H', parent=styles['Heading2'], fontName=font_name,
                         fontSize=11, leading=16, textColor=HexColor('#e94560'),
                         spaceBefore=12, spaceAfter=4)
    bs = ParagraphStyle('B', parent=styles['Normal'], fontName=font_name,
                         fontSize=8, leading=12, spaceAfter=2, alignment=TA_JUSTIFY)
    rs = ParagraphStyle('R', parent=styles['Normal'], fontName=font_name,
                         fontSize=6, leading=8, textColor=grey)

    story = [Spacer(1, 0.5*cm),
             Paragraph("每日财经新闻聚合报告", ts),
             Paragraph(f"日期: {date_str}　|　新闻: {len(items)} 条", ss),
             HRFlowable(width="100%", thickness=1, color=HexColor('#e94560')),
             Spacer(1, 8)]

    by_cat = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

    for cat in CAT_ORDER:
        if cat not in by_cat: continue
        story.append(Paragraph(CAT_LABELS.get(cat, cat), hs))
        for item in by_cat[cat][:6]:
            title = item["title"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            url = item.get("url","")
            impact = item.get("impact","")
            if impact:
                c = "#22c55e" if "利好" in impact else ("#ef4444" if "利空" in impact else "#888")
                title = f'{title} <font color="{c}">【{impact}】</font>'
            link = f'<font color="blue"><u><a href="{url}">{title}</a></u></font>' if url else title
            story.append(Paragraph(link, bs))
            src = item["source_name"]
            if item.get("reasoning"):
                src += f" | 💡 {item['reasoning']}"
            story.append(Paragraph(src, rs))
            if item.get("summary") and item["summary"] != item["title"]:
                s = item.get("summary", "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            if s and s != item["title"]:
                story.append(Paragraph(s[:200], bs))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 4))

    story.append(HRFlowable(width="100%", thickness=0.5, color=grey))
    story.append(Spacer(1, 6))
    story.append(Paragraph("自动生成 · GitHub Actions · 仅供参考", rs))
    doc.build(story)


def build_docx(items, date_str, docx_path):
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    style = doc.styles['Normal']
    style.font.size = Pt(10)

    title = doc.add_heading('每日财经新闻聚合报告', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph(f'日期: {date_str}　|　新闻: {len(items)} 条')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.size = Pt(9)
    p.runs[0].font.color.rgb = RGBColor(128,128,128)
    doc.add_paragraph()

    by_cat = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

    for cat in CAT_ORDER:
        if cat not in by_cat: continue
        doc.add_heading(CAT_LABELS.get(cat, cat), level=1)
        for item in by_cat[cat][:6]:
            impact = item.get("impact","")
            if impact:
                imp_p = doc.add_paragraph(f'【{impact}】')
                imp_p.runs[0].font.size = Pt(9)
                imp_p.runs[0].font.color.rgb = RGBColor(34,197,94) if "利好" in impact else (RGBColor(239,68,68) if "利空" in impact else RGBColor(136,136,136))
            pp = doc.add_paragraph()
            pp.paragraph_format.space_after = Pt(2)
            r = pp.add_run(f'• {item["title"]}')
            r.bold = True; r.font.size = Pt(9)
            ps = doc.add_paragraph(f'  {item["source_name"]}')
            ps.runs[0].font.size = Pt(7)
            ps.runs[0].font.color.rgb = RGBColor(160,160,160)
            if item.get("reasoning"):
                pr = doc.add_paragraph(f'  💡 {item["reasoning"]}')
                pr.runs[0].font.size = Pt(8)
            if item.get("stocks"):
                pk = doc.add_paragraph(f'  📈 {item["stocks"]}')
                pk.runs[0].font.size = Pt(8)
            if item.get("summary") and item["summary"] != item["title"]:
                pm = doc.add_paragraph(f'  {item["summary"][:200]}')
                pm.runs[0].font.size = Pt(8)
    doc.save(docx_path)


def build_douyin_images(items, date_str, out_dir):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1080, 1920
    paths = []

    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    title_f = body_f = small_f = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                title_f = ImageFont.truetype(fp, 56)
                body_f = ImageFont.truetype(fp, 32)
                small_f = ImageFont.truetype(fp, 24)
                break
            except: pass
    if not title_f:
        title_f = body_f = small_f = ImageFont.load_default()

    BG, ACCENT, GOLD, WHITE, LGRAY, CARD = (
        (18,18,36), (233,69,96), (255,200,60), (255,255,255), (180,180,190), (30,30,55))

    # Cover
    img = Image.new("RGB", (W,H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([(0,0),(W,8)], fill=ACCENT)
    d.text((80,200), date_str, fill=LGRAY, font=small_f)
    t = "每日财经要闻"
    tw = d.textbbox((0,0), t, font=title_f)[2]
    d.text(((W-tw)//2, 280), t, fill=WHITE, font=title_f)
    sub = f"共 {len(items)} 条 · {len(set(i['source_id'] for i in items))} 个来源"
    sw = d.textbbox((0,0), sub, font=body_f)[2]
    d.text(((W-sw)//2, 380), sub, fill=GOLD, font=body_f)
    d.line([(340,460),(740,460)], fill=ACCENT, width=3)
    by_cat = {}
    for item in items: by_cat.setdefault(item["category"], []).append(item)
    y = 540
    for cat in CAT_ORDER:
        if cat in by_cat:
            d.text((120,y), f"{CAT_LABELS.get(cat,cat)}　{len(by_cat[cat])} 条", fill=LGRAY, font=small_f)
            y += 50
    cv = os.path.join(out_dir, "douyin_00_cover.png")
    img.save(cv, quality=95); paths.append(cv)

    # Category slides
    si = 1
    for cat in CAT_ORDER:
        if cat not in by_cat: continue
        ci = by_cat[cat][:5]
        img = Image.new("RGB", (W,H), BG)
        d = ImageDraw.Draw(img)
        d.rectangle([(0,0),(W,160)], fill=CARD)
        d.text((80,40), CAT_LABELS.get(cat,cat), fill=ACCENT, font=title_f)
        d.text((80,110), f"{len(ci)} 条重要新闻", fill=LGRAY, font=small_f)
        y = 220
        for item in ci:
            ch = 280
            if y + ch > H-100: ch = H-100-y
            d.rectangle([(40,y),(W-40,y+ch)], fill=CARD, outline=(60,60,80))
            imp = item.get("impact","")
            if imp:
                ic = (34,197,94) if "利好" in imp else ((239,68,68) if "利空" in imp else LGRAY)
                d.text((80,y+20), f"【{imp}】", fill=ic, font=small_f)
                yo = 50
            else: yo = 0
            d.text((80,y+20), item["source_name"], fill=GOLD, font=small_f)
            tw = textwrap.fill(item["title"], width=30)
            d.text((80,y+60+yo), tw, fill=WHITE, font=body_f)
            if item.get("summary",""):
                sw = textwrap.fill(item["summary"][:120], width=40)
                d.text((80,y+160+yo), sw, fill=LGRAY, font=small_f)
            y += ch + 30
        fp = os.path.join(out_dir, f"douyin_{si:02d}_{cat}.png")
        img.save(fp, quality=95); paths.append(fp)
        si += 1
    return paths


def send_email(sender, password, to, subject, body, attachments=None):
    domain = sender.split("@")[-1].lower()
    host, port, ssl = SMTP_CFG.get(domain, (f"smtp.{domain}", 465, True))
    msg = MIMEMultipart()
    msg["From"] = sender; msg["To"] = to; msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if attachments:
        for ap in attachments:
            if ap and os.path.exists(ap):
                with open(ap, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(ap)}"')
                msg.attach(part)
    if ssl:
        srv = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        srv = smtplib.SMTP(host, port, timeout=30); srv.starttls()
    try:
        srv.login(sender, password)
        srv.sendmail(sender, [to], msg.as_string())
        print(f"  Email -> {to}")
    finally:
        srv.quit()


# ============================================================
# Main Pipeline
# ============================================================

def main():
    print(f"[{now_bj().strftime('%Y-%m-%d %H:%M:%S')}] Daily Brief starting...")
    yesterday = (now_bj() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_str = now_bj().strftime("%Y-%m-%d")
    print(f"  Target date: {yesterday}")
    print(f"  Sources: {len(SOURCES)}")

    # ---- 1. Search ----
    print(f"\n[1/5] Searching {len(SOURCES)} sources (Google News)...")
    items, failures = search_all(since_date=yesterday, max_per=5)
    hits = len(set(i["source_id"] for i in items))
    print(f"  -> {len(items)} items from {hits}/{len(SOURCES)} sources"
          + (f" ({len(failures)} failed)" if failures else ""))

    # ---- 2. Impact Analysis ----
    print(f"\n[2/5] Analyzing capital market impact...")
    items = analyze_impact(items)

    # ---- 3. Reports ----
    print(f"\n[3/5] Generating reports...")
    report = text_report(items, today_str, failures)

    tmp = tempfile.gettempdir()
    pdf_path = os.path.join(tmp, f"每日财经新闻_{today_str}.pdf")
    build_pdf(items, today_str, pdf_path)
    print(f"  PDF: {os.path.getsize(pdf_path)/1024:.1f} KB")

    docx_path = os.path.join(tmp, f"每日财经新闻_{today_str}.docx")
    build_docx(items, today_str, docx_path)
    print(f"  DOCX: {os.path.getsize(docx_path)/1024:.1f} KB")

    douyin_dir = tempfile.mkdtemp(prefix="douyin_")
    douyin_paths = build_douyin_images(items, today_str, douyin_dir)
    print(f"  Douyin: {len(douyin_paths)} slides")

    # ---- 4. Email ----
    print(f"\n[4/5] Sending email...")
    sender = os.environ.get("EMAIL_SENDER", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    recipient = os.environ.get("EMAIL_TO", sender)

    if sender and password:
        all_att = [pdf_path, docx_path] + douyin_paths
        send_email(sender, password, recipient,
                   f"📰 每日财经要闻 {today_str}", report, all_att)
    else:
        print("  SKIP: email not configured")

    print(f"\n[{now_bj().strftime('%Y-%m-%d %H:%M:%S')}] Done!")


if __name__ == "__main__":
    main()
