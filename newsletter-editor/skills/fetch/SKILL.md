---
name: fetch
description: |
  美轮美换新闻抓取+翻译。从Memeorandum和Political Wire抓取RSS，或抓取单独URL。翻译中文摘要，追溯原始来源。每天可执行多次。
  触发词: baihua fetch, 百花 fetch, 抓取新闻, fetch news, 翻译新闻, translate, baihua run, 百花 run
---

# 抓取+翻译

Plugin root: `skills/newsletter-editor/`. All commands run from vault root.

## Mode Detection

Check ARGUMENTS for a URL (starts with `http://` or `https://`):
- **URL present** → Single Article Mode (skip RSS, go to Step 1B)
- **No URL** → RSS Batch Mode (Step 1A)

Other arguments (`--date YYYY-MM-DD`) apply to both modes.

## Step 1A: RSS Batch Fetch

```bash
python3 skills/newsletter-editor/fetch_rss.py
```

**Auto-date detection**: If today's folder already has `newsletter.md` (compiled/published), the script automatically targets tomorrow's date. Override with `--date YYYY-MM-DD`.

**Direct subfolder saving**: New articles are saved directly into `inbox/` or `skipped/` subdirectories (no need to run `organize.py` after fetch).

Reads RSS from `config.json` (Memeorandum + Political Wire), scrapes via Jina Reader, deduplicates against subfolders, saves as `status: inbox`. New articles default to `ghost_access: "paid"`.

## Step 1B: Single Article Fetch

When a URL is provided as argument:

1. **Scrape** the URL using fallback chain: Jina Reader (`https://r.jina.ai/<URL>` via WebFetch) → WebFetch direct → Chrome browser tools → Edge AppleScript
2. **Extract metadata**: title from page content, source from domain (e.g. `nytimes.com` → `NYT`)
3. **Generate filename**: slugify the title, truncate to 60 chars
4. **Create file** in the target date's `inbox/` with full frontmatter template (see Article File Format below), `## Original Content` populated with scraped text
5. **Proceed to Step 2** (translate) immediately — do not wait for a separate translate cycle

Both sources are aggregators. The fetch script extracts original article URLs and sets `source` from the original publication domain.

## Step 2: Translate

Claude translates all `status: inbox` articles. For each:

1. Read `## Original Content` and `glossary.json`
2. **Thin content detection + auto-fallback** (BEFORE translating):
   - If `## Original Content` has < 50 lines, OR only contains PW/Memeorandum quote paragraphs (look for `the [Source] reports` patterns), OR `source_url` still points to PW/Memeorandum:
     a. Extract the original source URL from the content (look for links in PW quotes, or derive from `source` field + article title)
     b. Update `source_url` to the original URL
     c. **Fallback chain to scrape full article**:
        1. Jina Reader: `WebFetch("https://r.jina.ai/<original_url>")`
        2. WebFetch direct: `WebFetch("<original_url>")`
        3. Edge AppleScript (see below) — works for paywalled sites if user is logged in
        4. PW quotes as last resort — translate with what's available, but add `<!-- thin_content: true -->` comment after Original Content header so review can flag it
     d. Replace `## Original Content` with the full scraped article
   - This step runs **automatically** during every fetch loop, not just manual invocations
3. **Source attribution**: If source is still Political Wire or Memeorandum, trace to original publication (NYT, WSJ, Politico, etc.) and update `source` + `source_url`
4. Write `## 中文摘要` and `## 社交文案`
5. Set frontmatter: `status: draft`, `ai_title`, `importance` (1-10), `category`, `share`, `share_score`, `ghost_access: "paid"`
6. Report: "✓ [ai_title] (importance: X, category: Y)" — append "(enriched)" if fallback scraping was used

**PW articles must be scraped from original source URL**, not just the PW summary. PW pages only have 1-2 paragraph quotes.

```bash
# Edge AppleScript fallback — wait 5s for page load
open -a "Microsoft Edge" "URL"
sleep 5
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
