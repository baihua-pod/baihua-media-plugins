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

### 2.5 Writing Quality (AI味 + 翻译腔)

Full checklist: [references/writing-quality.md](../../references/writing-quality.md). Scan for:

- [ ] **No AI高频词**: 「至关重要」「不可或缺」「格局」「标志着」「蓬勃发展」「深入」
- [ ] **No被动滥用**: 「被认为」「被视为」在非受害语境应改主动
- [ ] **No万能动词**: 「作出」「进行」「展开」→ 直接用动词
- [ ] **No三连排比**: 「不仅...而且...更...」结构拆掉
- [ ] **No「的」字链**: 连续两个以上「的」拆句
- [ ] **中文语序**: 先因后果、条件句在前，无倒装从句
- [ ] **代词精简**: 主语没换不重复「他」「她」
- [ ] **No空洞总结**: 无「综上所述」「值得注意的是」等无信息量的句子

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

Target: ≥50% paid content, 15-25% share across all approved articles.

| Type | Criteria | `share` | `ghost_access` |
|------|----------|---------|----------------|
| **viral** | ⭐8+或极具传播力的突发新闻 | `true` | `free` |
| **share** | ⭐6+且有传播力（话题热度高、涉及广泛关注人物、有冲突性、数据抓眼球） | `true` | `paid` |
| **deep** | niche、分析类、⭐5以下 | `false` | `paid` |
| **skip** | 质量不足或重复 | — | — |

Share 目标 15-25%：⭐8+ 必定 share，⭐6-7 中选择传播力强的（不必全部 free，share+paid 也可以）。⭐5 以下默认 deep/paid。

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
