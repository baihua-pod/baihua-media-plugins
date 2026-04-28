# Weekend / Multi-Day Edition Workflow

When consolidating multiple days into a single newsletter (e.g., Saturday + Sunday → weekend edition).

## When to Use

- Weekend editions (Saturday + Sunday)
- Holiday periods (2+ days without publishing)
- Any time the user asks to merge multiple days

## Step 1: Identify Date Range

Determine which date folders to consolidate. The newsletter.md goes into the **latest** date folder.

```
Example: 2026-04-12 (Sat) + 2026-04-13 (Sun) → newsletter.md in 2026-04-13/
```

## Step 2: Cross-Day Dedup

Compare approved articles across all days. Common supersession patterns:

| Earlier Article | Later Article | Action |
|----------------|---------------|--------|
| 谈判代表抵达 | 谈判破裂 | Skip earlier, keep later |
| 军舰穿越海峡 | 封锁宣布 | Skip earlier, keep later |
| 提案公布 | 投票结果 | Skip earlier, keep later |
| 不同来源同一事件 | — | Merge into one entry |

For each superseded article:
1. Set `status: skipped` on the older article
2. Set `merge_into: <newer-article-filename>` if unique info should be folded in
3. Fold any unique details from the older article into the newer one's 中文摘要

For independently valuable coverage of the same event (different angles, different impacts), keep both.

## Step 3: Compile Multi-Day

Use compile.py with `--dates` to pull from multiple folders:

```bash
python3 skills/newsletter-editor/compile.py --dates 2026-04-12,2026-04-13
```

This reads `approved/` from all specified date folders, deduplicates by `source_url`, and outputs to the last date's `newsletter.md`.

If compile.py doesn't support the needed combination, write newsletter.md manually following the standard format.

## Step 4: Editorial Review (Enhanced)

Weekend editions need extra editorial attention:

1. **Narrative arcs**: Within categories (especially 伊朗战争, 行政与特朗普), order articles chronologically to tell a story across the weekend
2. **Merge aggressively**: Weekend readers want density. If two articles cover the same story from different days, merge into one cohesive entry with all sources
3. **Progressive updates**: For fast-moving stories, the newsletter entry should reflect the **latest state** while noting key developments: 「周六特朗普宣布X，周日军方收窄为Y」
4. **Header format**: Use `周末版` label and actual date range:
   ```
   # 美轮美换 | 4月12-13日周末版
   > 本期共 X 篇 | 免费 Y 篇 · 付费 Z 篇
   ```

## Step 5: Volume Targets

| Edition Type | Target Articles | Notes |
|-------------|----------------|-------|
| Daily (weekday) | 20-25 | Normal volume |
| Weekend (2 days) | 35-40 | ~1.5x daily, not 2x (dedup reduces count) |
| Holiday (3+ days) | 40-50 | Diminishing returns after 45 |

If below target: scan skipped articles across all days for rescue candidates (importance ≥ 4, no `merge_into`, has 中文摘要).

## Rescue Skipped Articles

To expand newsletter volume:

```bash
# Find rescue candidates across date folders
grep -l 'status: skipped' YYYY-MM-DD/skipped/*.md | while read f; do
  grep -q 'merge_into: ""' "$f" && grep -q '## 中文摘要' "$f" && echo "$f"
done
```

Criteria for rescue:
- `importance` ≥ 4
- `merge_into` is empty (not a duplicate)
- Has non-empty `## 中文摘要` (already translated)
- Not superseded by a newer article

To rescue: change `status: skipped` → `status: approved`, run `organize.py`, re-compile.
