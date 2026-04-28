---
name: review
description: |
  美轮美换新闻审核。对draft文章进行全面质量检查（翻译、来源、分类、去重），设置status为approved或skipped。每天可执行多次。
  触发词: baihua review, 百花 review, 审核新闻, review news
---

# 审核

Plugin root: `skills/newsletter-editor/`. All commands run from vault root.

Translation quality rules: see [references/translation-guide.md](../../references/translation-guide.md). Terminology: see `glossary.json`.

> **Pre-flight gate**：`publish.py` 启动时会自动跑 `validate_article()` 校验每篇 approved 文章——
> ai_title ≤18 中文字、不以媒体名开头、中文摘要字数符合 importance 分级（+10% 容忍）、
> 中文摘要/社交文案不含 Markdown（`**bold**`、`[text](url)`、`#` heading）。任何违规都会拒绝发布。
> 也就是说，本 checklist §3、§4 不再靠记忆——写完后 publish 时机器会复核一遍。
> 紧急情况可加 `--skip-validation` 临时绕过，但应当先修违规再重发。

## Review Checklist

For each `status: draft` article, run through all checks below. Fix issues inline; only flag to user if a judgment call is needed.

### 1. Source Attribution

- [ ] `source` must be the **original publication** (NYT, WSJ, Politico, etc.), not an aggregator (Political Wire, Memeorandum)
- [ ] `source_url` must point to the **original article**, not the aggregator page
- [ ] `source_url` must be clean — no tracking params (`utm_*`, `gift`, `fbclid`, etc.)
- [ ] If source is still PW/Memeorandum: trace to original, scrape it (see [scraping-fallback.md](../../references/scraping-fallback.md)), update `source` + `source_url`, and rewrite summary from the richer original content

### 1.5. Original Content Integrity

- [ ] `## Original Content` must contain the **full article text** (≥20 lines for a real article), not just an RSS headline + blurb
- [ ] Check frontmatter `thin_content: true` — if set, re-attempt scraping using [scraping-fallback.md](../../references/scraping-fallback.md):
  - If scraping succeeds: replace `## Original Content`, set `thin_content: false`, **verify 中文摘要 against new content and rewrite if needed**
  - If scraping still fails: flag to user — summary may be unreliable
- [ ] Even without `thin_content` flag: if `## Original Content` has < 20 lines or is missing entirely, treat as thin content and follow the steps above
- [ ] **Verify that all specific facts in 中文摘要 (names, numbers, dates, quotes) appear in `## Original Content`**. Flag any claims not traceable to Original Content — these may be hallucinated from model knowledge

### 2. Translation Quality

Check against [translation-guide.md](../../references/translation-guide.md) rules:

- [ ] **Accuracy**: numbers, names, dates, institutions unchanged from original
- [ ] **Fluency**: no 英文直译腔; natural Chinese word order; active voice
- [ ] **Terminology**: consistent within article; matches `glossary.json`
- [ ] **Person names**: first mention has English in parentheses（除免标注的知名领导人）
- [ ] **Punctuation**: Chinese punctuation throughout — 「」引号、中文逗号，、句号。（禁止 "" '' , .）
- [ ] **Single paragraph**: summary is one paragraph, no bullet lists
- [ ] **Coverage**: covers ≥3 of: who, what, impact, when
- [ ] **Length**: matches importance tier (⭐1-3: 80-120字, ⭐4-6: 100-160字, ⭐7-8: 140-200字, ⭐9-10: 180-240字)

### 3. Social Content (社交文案)

- [ ] 220-280字, info density close to summary (reader should understand the full story without clicking)
- [ ] No emoji, no links, no rhetorical questions at end
- [ ] Uses specific names + numbers for hook (not vague generalities)
- [ ] Ends with complete declarative sentence
- [ ] Tone: factual, no slang (不用「跑路」「割韭菜」「吓跑」)
- [ ] **禁用 Markdown 语法**：不用 `**xxx**` 粗体、`*xxx*` 斜体、`[text](url)` 链接——Threads/Bluesky 不渲染 Markdown，会显示字面星号（读者在手机上看到「**xxx**」而不是加粗）。要强调用「」书名号、换行或直接靠句式承载。同样的规则适用于**中文摘要**——虽然 Ghost 支持 Markdown，但保持两边一致、并且 publish.py 会把摘要也用作 summary fallback。

### 4. Frontmatter Completeness

All fields must be present and valid:

- [ ] `ai_title`: **硬上限 8-18 中文字**（先数字）；单一主谓结构；禁止多子句堆叠或把独家细节塞进标题；超 18 字必须砍（详见 translation-guide.md Title 节）
- [ ] `importance`: 1-10, reasonable for the news weight
- [ ] `category`: one of the valid categories (see translation-guide.md)
- [ ] `share` + `share_score`: set appropriately
- [ ] `ghost_access`: `"paid"` or `"free"`
- [ ] `date`: correct date

### 5. Dedup

Compare against approved articles **in the same date folder AND adjacent date folders** (critical for weekend editions).

**Same-day dedup**: Same event from different sources?
- No new info → `status: skipped`
- New developments → set `merge_into: <existing-filename>`, then `status: skipped`
- Different angle, independently valuable → keep both

**Cross-day dedup** (for multi-day/weekend editions):
Check if an older article is superseded by a newer one covering the same story's progression:

| Pattern | Action |
|---------|--------|
| Earlier: 谈判代表抵达 → Later: 谈判破裂 | Skip earlier |
| Earlier: 提案公布 → Later: 投票结果 | Skip earlier |
| Earlier: 军舰穿越 → Later: 封锁宣布 | Skip earlier |
| Same event, different publication | Merge into one |
| Same topic, genuinely different angles | Keep both |

For superseded articles: set `merge_into: <newer-filename>`, fold unique info into the newer article's 中文摘要.

**`merge_into` field usage**:
- Value: filename of the article that absorbs this one's content (e.g., `trump-blockade-hormuz.md`)
- Purpose: audit trail — tracks which article's unique info was folded where
- After setting `merge_into`: ensure the target article actually incorporates any unique details, then set `status: skipped`

### 6. Classify

Targets: ≥50% paid content, 15-20% share: true across all approved articles.

| Type | Criteria | `share` | `ghost_access` |
|------|----------|---------|----------------|
| **viral** | ⭐8+，必定分享 | `true` | `free` |
| **share-worthy** | ⭐7且传播力强（话题热度高、有冲突性、涉及广泛关注人物） | `true` | `free` |
| **deep** | ⭐7 niche/分析类，或⭐6以下 | `false` | `paid` |
| **skip** | 质量不足或重复 | — | — |

After batch review, verify share ratio is 15-20% and paid ratio ≥50%.

## Batch Presentation

After reviewing, present 5-10 articles at a time:

```
| # | ai_title | importance | category | share | decision | issues |
```

- `decision`: approved / skipped / needs discussion
- `issues`: brief note if any check failed (e.g., "source still PW", "title too long")

User confirms or adjusts before setting `status: approved`.

After batch: verify ≥50% approved articles are `ghost_access: paid`.

## 7. Coverage Gap Check (optional, after approving batch)

Scan Memeorandum front page for top stories not yet covered:

1. Fetch `https://www.memeorandum.com/` and scan headlines
2. Compare against approved articles by **topic** (not exact title match)
3. Flag any stories that look ⭐7+ and are missing as candidates for `/fetch <url>`
4. Priority: deaths, resignations, court rulings, major votes — these are easy to miss from RSS alone

## Advanced Operations

For rescue of skipped articles, batch operations, and weekend edition review, see [references/review-advanced.md](../../references/review-advanced.md).

## Organize

```bash
python3 skills/newsletter-editor/organize.py
```

Moves files to status subfolders (inbox/, draft/, approved/, skipped/).
