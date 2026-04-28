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

Other arguments (`--date YYYY-MM-DD`) apply to both modes. If no `--date` is specified:
- **RSS mode**: uses `fetch_rss.py` auto-detection (targets tomorrow if today's `newsletter.md` exists)
- **Single article mode**: uses the same auto-detection logic — check if today's folder has `newsletter.md`; if so, target tomorrow

## Step 1A: RSS Batch Fetch

```bash
python3 skills/newsletter-editor/fetch_rss.py
```

**Auto-date detection**: If today's folder already has `newsletter.md` (compiled/published), the script automatically targets tomorrow's date. Override with `--date YYYY-MM-DD`.

**Direct subfolder saving**: New articles are saved directly into `inbox/` or `skipped/` subdirectories (no need to run `organize.py` after fetch).

Reads RSS from `config.json` (Memeorandum + Political Wire), scrapes via Jina Reader, deduplicates against subfolders, saves as `status: inbox`. New articles default to `ghost_access: "paid"`.

## Step 1B: Single Article Fetch

When a URL is provided as argument:

1. **Clean URL**: Strip tracking parameters (`utm_*`, `gift`, `fbclid`, `gclid`, `ref`, `smid`, `smtyp`) from the URL before saving as `source_url`. Keep only semantically meaningful params (e.g., `?page=2`)
2. **Scrape** the URL using the fallback chain in [references/scraping-fallback.md](../../references/scraping-fallback.md)
3. **Extract metadata**: title from page content, source from domain (e.g. `nytimes.com` → `NYT`)
4. **Generate filename**: slugify the title, truncate to 60 chars
5. **Create file** in the target date's `inbox/` with full frontmatter template (see Article File Format below), `## Original Content` populated with scraped text. If source_url basename is non-semantic (archive IDs, hashes, numeric slugs), set `ghost_slug` with a kebab-case English keyword slug (<=60 chars)
6. **Proceed to Step 2** (translate) immediately — do not wait for a separate translate cycle

Both sources are aggregators. The fetch script extracts original article URLs and sets `source` from the original publication domain.

## Step 2: Translate

Translation is performed by Claude directly (reading and editing files), not by the Python script.

**CRITICAL RULE: 中文摘要 and 社交文案 must be based SOLELY on `## Original Content`. Never supplement with model knowledge or training data. If Original Content is insufficient, scrape the full article first. If scraping fails, translate only what is available — do not invent or assume details.**

Claude translates all `status: inbox` articles. For each:

1. **Load glossary**: Read `glossary.json`. Grep `## Original Content` for glossary keys (person names, organizations, terms). Note all matches — these MUST use the glossary translation, no freelancing
2. **Load translation rules**: Before writing ai_title and 中文摘要, **also `Read` the "Common Errors" section of [references/translation-guide.md](../../references/translation-guide.md)**. The 8 rules there (媒体名《书名号》、机构中文全称、N 月 N 日、流畅新闻句、禁中英行话、保留场景细节、ai_title 正式头条、二级人物全名) are NOT all auto-enforced by validator — Claude must read and apply them at write time.
3. **Thin content detection + auto-fallback** (BEFORE translating):
   - If `## Original Content` has < 50 lines, OR only contains PW/Memeorandum quote paragraphs (look for `the [Source] reports` patterns), OR `source_url` still points to PW/Memeorandum:
     a. Extract the original source URL from the content (look for links in PW quotes, or derive from `source` field + article title)
     b. Update `source_url` to the original URL (strip tracking params — see Step 1B)
     c. Scrape full article using the fallback chain in [references/scraping-fallback.md](../../references/scraping-fallback.md)
     d. **MUST replace `## Original Content` with the full scraped text** when fallback succeeds. This is the audit trail — never leave Original Content empty/thin after successful scraping
     e. Remove `thin_content: true` from frontmatter if scraping succeeded
   - This step runs **automatically** during every fetch loop, not just manual invocations
4. **Source attribution**: If source is still Political Wire or Memeorandum, trace to original publication (NYT, WSJ, Politico, etc.) and update `source` + `source_url`
5. Write `## 中文摘要` and `## 社交文案` — **based only on `## Original Content`**, applying the rules loaded in step 2
6. **Punctuation auto-check** (MUST run after writing Chinese sections):
   - Scan 中文摘要 and 社交文案 for residual English punctuation
   - `, ` (English comma) → `，`; `. ` (English period in Chinese) → `。`; `""` `''` → `「」`
   - Do NOT touch `## Original Content` or frontmatter — only Chinese sections
   - Self-correct before proceeding
7. Set frontmatter: `status: draft`, `ai_title`, `importance` (1-10), `category`, `share`, `share_score`, `ghost_access: "paid"`
8. Report: "✓ [ai_title] (importance: X, category: Y)" — append "(thin)" if `thin_content: true`, "(enriched)" if fallback scraping was used

**PW articles must be scraped from original source URL**, not just the PW summary. PW pages only have 1-2 paragraph quotes. See [references/scraping-fallback.md](../../references/scraping-fallback.md) for the full fallback chain including Edge AppleScript chunked reading.

### Batch workflow (10+ inbox)

1. **Scan inbox** for titles + sources:
   ```bash
   for f in 📚\ Areas/Work/Baihua\ Media/The\ American\ Roulette/每日新闻通讯/YYYY-MM-DD/inbox/*.md; do
     echo "$(grep '^title:' "$f" | head -1) | $(grep '^source:' "$f" | head -1) | $f"
   done
   ```
2. **Skip non-US politics** in batch:
   ```bash
   sed -i '' 's/^status: inbox/status: skipped/' path/to/file.md
   ```
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
thin_content: false
merge_into: ""
published: []
---
```

`thin_content: true` means full article scraping failed and Original Content only has RSS blurb. Review stage will re-attempt scraping.

## Common Issues

- **Scraping failures**: See [references/scraping-fallback.md](../../references/scraping-fallback.md) for the full fallback chain and platform-specific notes.
- **Missing frontmatter**: Old files may lack `ghost_access`, `share_score`. Add all missing fields per template above.
- **Edit failures**: Always `Read` before `Edit` — old files may have unexpected frontmatter.
- **English punctuation in Chinese**: Most common translation error. Step 2.5 auto-check should catch it, but verify during review.
