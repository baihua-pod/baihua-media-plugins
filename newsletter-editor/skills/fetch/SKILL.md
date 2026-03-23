---
name: fetch
description: |
  美轮美换新闻抓取+翻译。从Memeorandum和Political Wire抓取RSS，翻译中文摘要，追溯原始来源。每天可执行多次。
  触发词: baihua fetch, 百花 fetch, 抓取新闻, fetch news, 翻译新闻, translate, baihua run, 百花 run
---

# 抓取+翻译

Plugin root: `skills/newsletter-editor/`. All commands run from vault root.

## Step 1: Fetch

```bash
python3 skills/newsletter-editor/fetch_rss.py
```

**Auto-date detection**: If today's folder already has `newsletter.md` (compiled/published), the script automatically targets tomorrow's date. Override with `--date YYYY-MM-DD`.

**Direct subfolder saving**: New articles are saved directly into `inbox/` or `skipped/` subdirectories (no need to run `organize.py` after fetch).

Reads RSS from `config.json` (Memeorandum + Political Wire), scrapes via Jina Reader, deduplicates against subfolders, saves as `status: inbox`. New articles default to `ghost_access: "paid"`.

Both sources are aggregators. The fetch script extracts original article URLs and sets `source` from the original publication domain.

## Step 2: Translate

Claude translates all `status: inbox` articles. For each:

1. Read `## Original Content` and `glossary.json`
2. **Source attribution**: If source is still Political Wire or Memeorandum, trace to original publication (NYT, WSJ, Politico, etc.) and update `source` + `source_url`
3. Write `## 中文摘要` and `## 社交文案`
4. Set frontmatter: `status: draft`, `ai_title`, `importance` (1-10), `category`, `share`, `share_score`, `ghost_access: "paid"`
5. Report: "✓ [ai_title] (importance: X, category: Y)"

**PW articles must be scraped from original source URL**, not just the PW summary. PW pages only have 1-2 paragraph quotes. Fallback chain: Jina Reader → WebFetch → Chrome browser tools → Edge AppleScript → PW quotes (last resort).

```bash
# Edge AppleScript fallback
open -a "Microsoft Edge" "URL"
osascript -e 'tell application "Microsoft Edge" to execute active tab of first window javascript "document.body.innerText"'
```

### Batch workflow (10+ inbox)

1. Scan inbox files with shell one-liner for titles + sources
2. Skip duplicates and non-US politics in batch (`sed` to set `status: skipped`)
3. Extract original source URLs from PW/Memeorandum content
4. Batch-scrape originals via Jina Reader (parallel WebFetch when possible)
5. Translate remaining articles
6. Run `organize.py` once at the end

**Frontmatter note**: Always add `ghost_access: "paid"` — older files may be missing this field. Always `Read` a file before editing to get exact frontmatter structure.

## Step 3: Organize

```bash
python3 skills/newsletter-editor/organize.py
```

Moves files to status subfolders (inbox/, draft/, approved/, skipped/).

## Translation rules

See [references/translation-guide.md](../../references/translation-guide.md)

## Article File Format

```yaml
---
title: "Original English Title"
ai_title: "中文标题"
source: "NYT"
source_url: "https://..."
date: 2026-03-22
status: inbox|draft|approved|skipped
importance: 0-10
category: ""
share: true|false
share_score: 0-10
ghost_access: free|paid
merge_into: ""
published: []
---
```

## Common Issues

- **Jina 403/451**: Paywalled sites. Use fallback chain above.
- **Politico blocked**: Use Chrome browser tools or PW quotes.
- **Missing frontmatter**: Old files may lack `ghost_access`, `share_score`. Add all missing fields per template above.
- **Edit failures**: Always `Read` before `Edit` — old files may have unexpected frontmatter.
