---
name: compile
description: |
  美轮美换Newsletter编辑。将approved文章编译成newsletter.md，合并重复条目，支持手动添加文章。通常每天一次。
  触发词: baihua compile, 百花 compile, 编辑通讯, compile newsletter, 今日新闻, newsletter
---

# 编辑Newsletter

Plugin root: `skills/newsletter-editor/`. All commands run from vault root.

## Step 1: Generate

```bash
python3 skills/newsletter-editor/compile.py              # generate newsletter.md
python3 skills/newsletter-editor/compile.py --dry-run    # preview
python3 skills/newsletter-editor/compile.py --date 2026-03-22
```

`compile.py` reads all approved articles, groups by category (order defined in `CATEGORY_ORDER`), sorts by importance descending, writes `newsletter.md`. Format: `- **[ai_title]**：[中文摘要]（[Source](url)）` — source must be clickable link, no emoji.

## Step 2: Editorial Review

After `compile.py`, review `newsletter.md` for merge opportunities:

1. **Identify overlapping articles**: Same event covered by multiple sources → combine into one entry, preserve unique info from each, list all sources: `（[Source1](url1) / [Source2](url2)）`
2. **When NOT to merge**: Different angles that are independently valuable (e.g., NATO reaction vs Japan reaction vs China reaction — different reader interests, keep separate)
3. **Write as cohesive narrative**: Merged articles must read like a single news piece. Use transition words (「然而」「与此同时」「在外交层面」), no bold sub-headers within entries
4. **Update article count** in header after merges: `> 今日共 X 篇 | 免费 Y 篇 · 付费 Z 篇`
5. **Reorder if needed**: Move articles between sections if editorial judgment suggests better fit

## Manual Article Addition

For articles not in RSS (user sends a URL):

1. Scrape: WebFetch → Jina Reader → Edge AppleScript (fallback chain)
2. Create file in `approved/` with full frontmatter (see fetch skill for template)
3. Translate `## 中文摘要`, set all frontmatter fields
4. Add entry to `newsletter.md` in appropriate category

## Category Order

Canonical source: `compile.py` `CATEGORY_ORDER`. Current order:

伊朗战争 → 行政与特朗普 → 国会与立法 → 司法与法律 → 财经与特朗普关税 → 民生与经济 → 国际 → 民主党 → 媒体与文化 → 地方 → 其它

「伊朗战争」是临时类别，冲突结束后合并回「国际」并从 `compile.py` 移除。
