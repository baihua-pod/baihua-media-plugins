---
name: review
description: |
  美轮美换新闻审核。对draft文章进行全面质量检查（翻译、来源、分类、去重），设置status为approved或skipped。每天可执行多次。
  触发词: baihua review, 百花 review, 审核新闻, review news
---

# 审核

Plugin root: `skills/newsletter-editor/`. All commands run from vault root.

Translation quality rules: see [references/translation-guide.md](../../references/translation-guide.md). Terminology: see `glossary.json`.

## Review Checklist

For each `status: draft` article, run through all checks below. Fix issues inline; only flag to user if a judgment call is needed.

### 1. Source Attribution

- [ ] `source` must be the **original publication** (NYT, WSJ, Politico, etc.), not an aggregator (Political Wire, Memeorandum)
- [ ] `source_url` must point to the **original article**, not the aggregator page
- [ ] If source is still PW/Memeorandum: trace to original, scrape it (Jina → WebFetch → browser fallback), update `source` + `source_url`, and rewrite summary from the richer original content

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

- [ ] 120-280 chars, info density close to summary
- [ ] No emoji, no links, no rhetorical questions at end
- [ ] Uses specific names + numbers for hook (not vague generalities)
- [ ] Ends with complete declarative sentence
- [ ] Tone: factual, no slang (不用「跑路」「割韭菜」「吓跑」)

### 4. Frontmatter Completeness

All fields must be present and valid:

- [ ] `ai_title`: 8-18 Chinese chars, not a literal translation of English title
- [ ] `importance`: 1-10, reasonable for the news weight
- [ ] `category`: one of the valid categories (see translation-guide.md)
- [ ] `share` + `share_score`: set appropriately
- [ ] `ghost_access`: `"paid"` or `"free"`
- [ ] `date`: correct date

### 5. Dedup

Compare against approved articles. Same event?
- No new info → `status: skipped`
- New developments → set `merge_into: <existing-filename>`, then `status: skipped`
- Different angle, independently valuable → keep both

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

## Organize

```bash
python3 skills/newsletter-editor/organize.py
```

Moves files to status subfolders (inbox/, draft/, approved/, skipped/).
