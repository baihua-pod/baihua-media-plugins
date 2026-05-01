---
name: compile
description: |
  美轮美换Newsletter编辑。将approved文章编译成newsletter.md，合并重复条目，支持手动添加文章和多日周末版。通常每天一次。
  触发词: baihua compile, 百花 compile, 编辑通讯, compile newsletter, 今日新闻, newsletter, 周末版
---

# 编辑Newsletter

Plugin root: `skills/newsletter-editor/`. All commands run from vault root.

## Step 1: Generate

```bash
python3 skills/newsletter-editor/compile.py              # generate newsletter.md (today)
python3 skills/newsletter-editor/compile.py --date 2026-03-22
python3 skills/newsletter-editor/compile.py --dates 2026-04-12,2026-04-13  # weekend edition
python3 skills/newsletter-editor/compile.py --dry-run    # preview without writing
```

`compile.py` reads all approved articles, groups by category (order defined in `CATEGORY_ORDER`), sorts by importance descending, writes `newsletter.md`. Format: `- **[ai_title]**：[中文摘要]（[Source](url)）` — source must be clickable link, no emoji.

**Multi-day mode** (`--dates`): Reads `approved/` from all specified date folders, deduplicates by `source_url`, outputs to the last date's folder. Header uses "周末版" format automatically.

**Learn mode** (`--learn`, dry-run by default): After Sirui has manually edited `newsletter.md`, run this to **propagate his edits back to source `approved/*.md`** so future compiles preserve them and Claude sees the corrections in subsequent translations.

```bash
python3 skills/newsletter-editor/compile.py --learn --date 2026-04-27           # dry-run: shows diff
python3 skills/newsletter-editor/compile.py --learn --date 2026-04-27 --apply   # actually rewrites source files
```

How `--learn` works:
1. Re-runs compile internally to get the "fresh from approved/*.md" baseline
2. Parses current `newsletter.md` (Sirui's edited version)
3. Matches entries by `source_url` (stable key)
4. For **single-source entries** that differ: rewrites source `approved/*.md`'s `ai_title` + 中文摘要, marks `learned_from_edit: YYYY-MM-DD` in frontmatter
5. **Skips multi-source merges** (entries with `（[A](u1) / [B](u2)）` — can't 1:1 backprop)
6. **Skips articles not in newsletter.md** (Sirui's editorial trims need separate `status: skipped` if you want them gone)

Audit trail: `git diff` on approved/*.md shows exactly what was rewritten.

## Step 2: Editorial Review

After `compile.py`, review `newsletter.md` for **merge** AND **prune** opportunities. Compile output is a superset; the published newsletter should be ~60-70% of it (e.g., 4/28 had 56 articles compiled → 37 published).

### 2.1 Merge

1. **Identify overlapping articles**: Same event covered by multiple sources → combine into one entry, preserve unique info from each, list all sources: `（[Source1](url1) / [Source2](url2)）`
2. **When NOT to merge**: Different angles that are independently valuable (e.g., NATO reaction vs Japan reaction vs China reaction — different reader interests, keep separate)
3. **Write as cohesive narrative**: Merged articles must read like a single news piece. Use transition words (「然而」「与此同时」「在外交层面」), no bold sub-headers within entries

### 2.2 Prune

Cut these 4 categories aggressively. The compile output is a working set, not a publish list:

1. **同主题过量覆盖**：同一事件 4+ 角度 → 留 1-2 条核心 + merge 进去，其余删（删除即从 newsletter.md 删行，不动 approved/*.md）
2. **付费深度分析**：除非⭐8+ 关键背景或独家解读，长篇付费分析（评论、专栏、深度报告）默认删——读者付费阅读率低
3. **小众话题**：⭐≤6 且与当日主线（伊朗/特朗普/国会/司法）无关的——州地方新闻、专业领域更新、文化新闻
4. **冗余跟进**：已有主条覆盖核心事实，跟进角度增量小（"X 还说了 Y"、"Z 也评论了"）

**判定标准**：删之前问「读者错过这条会不会缺重要信息？」如果主条已涵盖、或这是付费/小众/跟进——删。

### 2.3 Cleanup

4. **Update article count** in header after merges/cuts: `> 今日共 X 篇 | 免费 Y 篇 · 付费 Z 篇`
5. **Reorder if needed**: Move articles between sections if editorial judgment suggests better fit

**Note**: Step 2 edits only `newsletter.md`. Source `approved/*.md` stays untouched—`compile.py --learn --apply` will later backprop your **kept** entries' wording to source. Pruned entries do **not** propagate (by design—they were never in newsletter.md to learn from).

## Weekend / Multi-Day Edition

For weekend consolidation, see [references/weekend-workflow.md](../../references/weekend-workflow.md).

Key differences from daily editions:
- Use `--dates` flag to pull from multiple folders
- Header: `# 美轮美换 | X月Y-Z日周末版`
- Order articles **chronologically within categories** to tell a narrative arc (e.g., 谈判开始→谈判破裂→封锁宣布)
- Merge more aggressively — weekend readers want density over breadth

## Volume Targets

| Edition Type | Target Articles |
|-------------|----------------|
| Daily (weekday) | 20-25 |
| Weekend (2 days) | 35-40 |
| Holiday (3+ days) | 40-50 |

If below target after compile: rescue skipped articles (see review skill) or ask user to manually add articles via `/newsletter-editor:fetch <URL>`.

## Manual Article Addition

Use `/newsletter-editor:fetch <URL>` to scrape, translate, and create the article file. Then add the entry to `newsletter.md` in the appropriate category section.

## Category Order

Canonical source: `compile.py` `CATEGORY_ORDER`. Current order:

伊朗战争 → 行政与特朗普 → 国会与立法 → 司法与法律 → 财经与特朗普关税 → 民生与经济 → 国际 → 民主党 → 媒体与文化 → 地方 → 其它

「伊朗战争」是临时类别，冲突结束后合并回「国际」并从 `compile.py` 移除。

### Non-canonical → canonical normalization

`compile.py` ships with `CATEGORY_ALIASES` (see source). Articles whose frontmatter `category` is a non-canonical value (e.g. `政府人事`、`媒体与新闻自由`、`中期选举`、`能源与经济`) are **auto-mapped to the 11 canonical categories** at parse time. Unknown categories fall through to `其它` instead of creating stray sections at the end of the newsletter.

On each run, the compiler prints `↺ Normalized N non-canonical categories → canonical:` with a breakdown so you can see which alias fired how many times — useful for deciding whether a frequently-used alias should be promoted to canonical instead.

To add a new alias: edit `CATEGORY_ALIASES` in `compile.py`. To promote a common non-canonical value to a new canonical section: add it to `CATEGORY_ORDER` and (optionally) remove from `CATEGORY_ALIASES`.

## Frontmatter Note

`category` in article frontmatter should be an **unquoted YAML string** (e.g., `category: 伊朗战争`, not `category: "伊朗战争"`). While `yaml.safe_load` handles both, consistency prevents edge cases in string matching.
