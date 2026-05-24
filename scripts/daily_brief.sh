#!/bin/bash
# ============================================================
# Daily Financial News Brief — Automated Morning Collection
# ============================================================
# Runs every weekday at 8:40 AM via launchd.
# Collects yesterday's financial news & policy.
#
# Output:
#   Local:  ~/Documents/每日财经新闻/YYYY-MM-DD/
#   iCloud: ~/Library/Mobile Documents/.../每日财经新闻/YYYY-MM-DD/
#   Email:  optional push to phone via QQ/Gmail/163
#
# Files per day:
#   ├── 每日财经新闻_YYYY-MM-DD.pdf
#   ├── 今日要闻.txt          (short summary for phone)
#   ├── results.json
#   ├── queries.json
#   └── pending.md
# ============================================================

set -euo pipefail

# ---- Config ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
LOCAL_OUTDIR="${HOME}/Documents/每日财经新闻/${TODAY}"
ICLOUD_BASE="${HOME}/Library/Mobile Documents/com~apple~CloudDocs/每日财经新闻"
ICLOUD_OUTDIR="${ICLOUD_BASE}/${TODAY}"
LOGFILE="${LOCAL_OUTDIR}/brief.log"

# Email config (set to empty to disable)
# QQ邮箱示例: EMAIL_TO="yourname@qq.com"
# Gmail示例:  EMAIL_TO="yourname@gmail.com"
EMAIL_TO="${FINANCE_BRIEF_EMAIL:-}"  # Set via: export FINANCE_BRIEF_EMAIL="xxx@qq.com"

mkdir -p "$LOCAL_OUTDIR"

# ---- Redirect output to log ----
exec > >(tee -a "$LOGFILE") 2>&1

echo "=============================================="
echo " Daily Financial News Brief"
echo " Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo " Target: yesterday (${YESTERDAY})"
echo " Local : ${LOCAL_OUTDIR}"
echo " iCloud: ${ICLOUD_OUTDIR}"
echo "=============================================="
echo ""

# ---- Step 1: Generate search queries ----
echo "[1/5] Generating search queries..."
python3 "${SCRIPT_DIR}/fetch_news.py" search --all --days 1 -o "${LOCAL_OUTDIR}/queries.json"
QUERY_COUNT=$(python3 -c "import json; print(json.load(open('${LOCAL_OUTDIR}/queries.json'))['query_count'])")
echo "  -> ${QUERY_COUNT} queries"
echo ""

# ---- Step 2: Direct RSS fetch ----
echo "[2/5] Direct RSS fetch..."
python3 "${SCRIPT_DIR}/daily_fetch.py" \
    --queries "${LOCAL_OUTDIR}/queries.json" \
    --output "${LOCAL_OUTDIR}/results.json" \
    --since "${YESTERDAY}" \
    --limit 15
echo ""

# ---- Step 3: Generate short summary (for phone notification) ----
echo "[3/5] Generating summary..."
python3 -c "
import json
with open('${LOCAL_OUTDIR}/results.json') as f:
    d = json.load(f)
items = d.get('items', [])
pending = d.get('pending_queries_count', 0)

lines = []
lines.append('📰 每日财经要闻')
lines.append(f'日期: ${TODAY} (搜集前一日新闻)')
lines.append(f'已获取: {len(items)} 条　|　待补充: {pending} 个来源')
lines.append('')

cats = {}
for item in items:
    c = item.get('category', 'other')
    cats.setdefault(c, []).append(item)
for c in ['breaking_news', 'cn_government', 'intl_government', 'comprehensive', 'global_news', 'global_markets']:
    if c in cats:
        for item in cats[c][:3]:
            src = item.get('source_name', '')
            title = item.get('title', '')[:80]
            lines.append(f'• [{src}] {title}')

if items:
    lines.append('')
    lines.append(f'📎 完整PDF: 每日财经新闻_${TODAY}.pdf (iCloud/每日财经新闻)')
if pending > 0:
    lines.append(f'⚠️ 打开Codex说\"完成今日财经简报\"补齐{pending}个来源')
with open('${LOCAL_OUTDIR}/今日要闻.txt', 'w') as f:
    f.write('\n'.join(lines))
print(f'  -> {len(items)} items summarized')
" 2>&1
echo ""

# ---- Step 4: Export PDF ----
echo "[4/5] Generating PDF..."
python3 "${SCRIPT_DIR}/export_pdf.py" \
    "${LOCAL_OUTDIR}/results.json" \
    -o "${LOCAL_OUTDIR}/每日财经新闻_${TODAY}.pdf"
echo ""

# ---- Step 5: Sync to iCloud + Email ----
echo "[5/5] Sync & notify..."

# iCloud sync
if [ -d "$ICLOUD_BASE" ]; then
    mkdir -p "$ICLOUD_OUTDIR"
    cp "${LOCAL_OUTDIR}/每日财经新闻_${TODAY}.pdf" "${ICLOUD_OUTDIR}/"
    cp "${LOCAL_OUTDIR}/今日要闻.txt" "${ICLOUD_OUTDIR}/"
    cp "${LOCAL_OUTDIR}/results.json" "${ICLOUD_OUTDIR}/"
    echo "  -> Synced to iCloud: ${ICLOUD_OUTDIR}"
else
    echo "  -> iCloud not available (skipped)"
fi

# Email push
if [ -n "${EMAIL_TO}" ]; then
    python3 "${SCRIPT_DIR}/push_email.py" \
        --to "${EMAIL_TO}" \
        --subject "📰 每日财经要闻 ${TODAY}" \
        --body-file "${LOCAL_OUTDIR}/今日要闻.txt" \
        --attach "${LOCAL_OUTDIR}/每日财经新闻_${TODAY}.pdf" 2>&1 || echo "  -> Email: skipped (config needed)"
else
    echo "  -> Email: not configured (set FINANCE_BRIEF_EMAIL)"
fi

# Pending notice
PENDING=$(python3 -c "import json; d=json.load(open('${LOCAL_OUTDIR}/results.json')); print(d.get('pending_queries_count',0))")
if [ "$PENDING" -gt 0 ]; then
    cat > "${LOCAL_OUTDIR}/pending.md" << EOF
# ⚠️ ${PENDING} 个来源待补充

在 Codex 中说"完成今日财经简报"即可自动补齐并重新生成 PDF。
EOF
fi

echo ""
echo "=============================================="
echo " ✅ Brief complete!"
echo " PDF  : ${LOCAL_OUTDIR}/每日财经新闻_${TODAY}.pdf"
echo " iCloud: ${ICLOUD_OUTDIR}/ (iPhone Files app)"
echo " Pending: ${PENDING} sources"
echo "=============================================="
