#!/usr/bin/env python3
"""
Export collected news to a professionally formatted PDF report using reportlab.
Supports Chinese fonts via system STSong or fallback Helvetica.
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, cm
    from reportlab.lib.colors import HexColor, black, white, grey
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, PageBreak, HRFlowable)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    print("reportlab not installed. Install: pip3 install reportlab", file=sys.stderr)


def register_fonts():
    """Register CJK-capable fonts for Chinese text."""
    try:
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        return 'STSong-Light'
    except Exception:
        pass

    # Try system fonts
    font_candidates = [
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
    ]
    for fp in font_candidates:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('CJKFont', fp))
                return 'CJKFont'
            except Exception:
                continue
    return 'Helvetica'


def load_data(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def now_beijing_str():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")


def build_pdf(data, output_path, font_name):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="每日财经新闻聚合报告",
        author="Financial News Collector",
    )

    styles = getSampleStyleSheet()
    W = A4[0] - 4*cm  # usable width

    # Custom styles
    title_style = ParagraphStyle('CNTitle', parent=styles['Title'],
                                  fontName=font_name, fontSize=18, leading=24,
                                  spaceAfter=6, alignment=TA_CENTER,
                                  textColor=HexColor('#1a1a2e'))
    subtitle_style = ParagraphStyle('CNSubtitle', parent=styles['Normal'],
                                     fontName=font_name, fontSize=9, leading=12,
                                     textColor=grey, alignment=TA_CENTER, spaceAfter=16)
    h2_style = ParagraphStyle('CNH2', parent=styles['Heading2'],
                               fontName=font_name, fontSize=13, leading=18,
                               textColor=HexColor('#e94560'), spaceBefore=16, spaceAfter=8)
    body_style = ParagraphStyle('CNBody', parent=styles['Normal'],
                                 fontName=font_name, fontSize=9, leading=14,
                                 spaceAfter=4, alignment=TA_JUSTIFY)
    source_style = ParagraphStyle('CNSource', parent=styles['Normal'],
                                   fontName=font_name, fontSize=7, leading=10,
                                   textColor=grey)
    footer_style = ParagraphStyle('CNFooter', parent=styles['Normal'],
                                   fontName=font_name, fontSize=7, leading=10,
                                   textColor=grey, alignment=TA_CENTER)

    story = []

    # ---- Title page header ----
    report_date = data.get("generated_at", now_beijing_str())
    time_range = data.get("time_range", "")
    item_count = data.get("item_count", len(data.get("items", [])))
    pending = data.get("pending_queries_count", 0)

    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("每日财经新闻聚合报告", title_style))
    story.append(Paragraph(
        f"生成时间: {report_date}　|　时间范围: {time_range or '前一日'}　|　新闻条数: {item_count}",
        subtitle_style))

    # Divider
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#e94560')))
    story.append(Spacer(1, 12))

    # ---- Source summary table ----
    if pending > 0:
        story.append(Paragraph(f"⚠️ {pending} 个来源需要 anysearch 补充搜索", body_style))
        story.append(Spacer(1, 8))

    # ---- Main content by category ----
    items = data.get("items", [])
    by_category = {}
    for item in items:
        cat = item.get("category", "other")
        by_category.setdefault(cat, []).append(item)

    category_labels = {
        "breaking_news": "⚡ 快讯 / 突发新闻",
        "comprehensive": "📋 综合财经新闻",
        "global_finance": "🌐 全球金融市场",
        "global_news": "📡 国际通讯社",
        "global_markets": "📈 全球市场行情",
        "securities": "📜 证券 / 监管新闻",
        "investment_research": "🏦 国际投行研报",
        "domestic_research": "🏢 国内券商研报",
        "cn_government": "🇨🇳 中国政府产业政策",
        "intl_government": "🌍 国际政府 / 央行政策",
    }

    # Determine if we need CJK-safe bullets
    cjk_bullet = "•" if font_name != 'Helvetica' else "-"

    for cat in sorted(by_category.keys()):
        cat_items = by_category[cat]
        label = category_labels.get(cat, cat)
        story.append(Paragraph(label, h2_style))

        for item in cat_items[:12]:
            title = item.get("title", "无标题").strip()
            url = item.get("url", "")
            summary = item.get("summary", "").strip()
            source = item.get("source_name", "")
            published = item.get("published", "")
            reliability = item.get("reliability", "")

            rel_star = {"highest": "★★★★★", "high": "★★★★", "medium": "★★★"}.get(reliability, "")

            # Title as bold
            t = f'<b>{title}</b>'
            story.append(Paragraph(t, body_style))

            # Source line
            src_line = f'{source}　|　{published}　{rel_star}' if source else published
            if src_line.strip():
                story.append(Paragraph(src_line, source_style))

            # Summary
            if summary and summary != title:
                clean = summary.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(clean[:250], body_style))

            story.append(Spacer(1, 6))

        story.append(Spacer(1, 8))

    # ---- Footer ----
    story.append(HRFlowable(width="100%", thickness=0.5, color=grey))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"本报告由 Financial News Collector 自动生成　|　{report_date}　|　仅供参考，不构成投资建议",
        footer_style))

    doc.build(story)
    return output_path


def main():
    if not HAS_REPORTLAB:
        print("Error: reportlab not installed. Run: pip3 install reportlab", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Export news data to PDF")
    parser.add_argument("input", help="Input JSON results file")
    parser.add_argument("--output", "-o", default="report.pdf", help="Output PDF path")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    data = load_data(args.input)
    font_name = register_fonts()
    print(f"Using font: {font_name}")

    path = build_pdf(data, args.output, font_name)
    size_kb = os.path.getsize(path) / 1024
    print(f"PDF generated: {path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
