---
name: review
description: |
  美轮美换新闻审核。审核draft文章（去重、分类viral/deep），设置status为approved或skipped。每天可执行多次。
  触发词: baihua review, 百花 review, 审核新闻, review news
---

# 审核

Plugin root: `skills/newsletter-editor/`. All commands run from vault root.

## Step 1: Review drafts

Claude reviews all `status: draft` articles in batch.

**Dedup**: Compare against approved articles. Same event?
- No new info → `status: skipped`
- New developments → set `merge_into: <existing-filename>`, then `status: skipped`
- Different angle, independently valuable → keep both

**Classify** (target: ≥50% paid content):

| Type | Criteria | `share` | `ghost_access` |
|------|----------|---------|----------------|
| **viral** | ⭐8+或极具传播力的突发新闻 | `true` | `free` |
| **deep** | 有深度、niche、分析类，或⭐7以下 | `false` | `paid` |
| **skip** | 质量不足或重复 | — | — |

Social sharing bar is high: only ⭐8+ or genuinely viral breaking news goes to social media. Default to deep/paid. After batch review, verify ≥50% approved articles are `ghost_access: paid`.

**Batch present**: Show 5-10 articles at a time with title, importance, category, and 1-sentence rationale. User confirms or adjusts.

## Step 2: Organize

```bash
python3 skills/newsletter-editor/organize.py
```

Moves files to status subfolders (inbox/, draft/, approved/, skipped/).
