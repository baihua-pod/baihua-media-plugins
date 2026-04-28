# Review — Advanced Operations

## Rescue Skipped Articles

When the newsletter needs more articles (e.g., weekend edition target is 35-40):

1. **Scan candidates** across relevant date folders:
   ```bash
   grep -rl 'status: skipped' YYYY-MM-DD/skipped/*.md | xargs grep -l 'importance: [4-9]' | xargs grep -L 'merge_into: [^"]'
   ```
   Or read files manually: look for `importance >= 4`, empty `merge_into`, non-empty `## 中文摘要`.

2. **Evaluate**: Is the article independently valuable? Not superseded by a newer article?

3. **Restore**:
   ```bash
   sed -i '' 's/^status: skipped/status: approved/' path/to/article.md
   ```

4. **Organize** to move file from `skipped/` to `approved/`:
   ```bash
   python3 skills/newsletter-editor/organize.py
   ```

## Batch Operations

For bulk status changes (e.g., approving 10 articles at once after user confirmation):

```bash
# Approve all drafts in a folder
for f in YYYY-MM-DD/draft/*.md; do sed -i '' 's/^status: draft/status: approved/' "$f"; done

# Skip multiple articles
for f in file1.md file2.md file3.md; do sed -i '' 's/^status: draft/status: skipped/' "$f"; done
```

Always run `organize.py` after batch status changes.

## Weekend Edition Review

For multi-day editions, see [weekend-workflow.md](weekend-workflow.md). Additional review considerations:

- Run cross-day dedup BEFORE approving articles
- Target >= 35 articles for weekend editions (vs ~20-25 daily)
- After dedup + rescue, verify paid ratio >= 50% still holds

## Cross-Day Dedup (Weekend/Multi-Day)

Check if an older article is superseded by a newer one covering the same story's progression:

| Pattern | Action |
|---------|--------|
| Earlier: 谈判代表抵达 -> Later: 谈判破裂 | Skip earlier |
| Earlier: 提案公布 -> Later: 投票结果 | Skip earlier |
| Earlier: 军舰穿越 -> Later: 封锁宣布 | Skip earlier |
| Same event, different publication | Merge into one |
| Same topic, genuinely different angles | Keep both |

For superseded articles: set `merge_into: <newer-filename>`, fold unique info into the newer article's 中文摘要.
