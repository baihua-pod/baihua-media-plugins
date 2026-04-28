---
name: publish
description: |
  美轮美换发布。将approved文章发布到Ghost和社交媒体（Bluesky、Threads）。每天可执行多次。
  触发词: baihua publish, 百花 publish, 发布新闻, publish, 百花发布
---

# 发布

Plugin root: `skills/newsletter-editor/`. All commands run from vault root.

## Prerequisites

Run **after** `/review` (articles approved) and `/compile` (newsletter.md ready).

## Step 1: Publish articles

```bash
python3 skills/newsletter-editor/publish.py                    # publish all unpublished
python3 skills/newsletter-editor/publish.py --limit 1          # publish 1 article
python3 skills/newsletter-editor/publish.py --platform ghost   # ghost only
python3 skills/newsletter-editor/publish.py --platform bluesky # bluesky only
python3 skills/newsletter-editor/publish.py --dry-run          # preview
python3 skills/newsletter-editor/publish.py --date 2026-03-22  # specific date
```

Credentials auto-loaded from `skills/newsletter-editor/.env`.

### Publishing logic

- **All approved articles** → Ghost (as individual posts)
- **`share: true` articles only** → social media (Bluesky, Threads)
- `ghost_access: paid` → Ghost members-only; `free` → public
- Already-published platforms are skipped (tracked in `published: []` frontmatter)

### Platform status

| Platform | Status | Notes |
|----------|--------|-------|
| Ghost | Active | Primary newsletter platform |
| Bluesky | Active | @theamericanroulette.bsky.social |
| Threads | Active | @theamericanroulette |
| X/Twitter | **Suspended** | Account banned. `--platform all` auto-skips twitter. Will re-enable when/if restored. |

### Ghost slug customization

Ghost URL slug resolves in this order:
1. `ghost_slug` frontmatter field（显式覆盖）
2. `source_url` 的最后一段 path（默认）
3. 文章文件名 stem
4. 时间戳兜底

**Dry-run 时必须检查 `slug:` 输出**。当 URL basename 是非语义的（Punchbowl 归档 `/archive/41626-am/`、Memeorandum 数字 ID、查询参数等），在 approved 文章的 frontmatter 加 `ghost_slug` 覆盖：

```yaml
# Bad: source_url=.../archive/41626-am/ → 发出的链接 /news/41626-am/
# Fix:
ghost_slug: "record-senate-democrats-vote-against-israel"
```

Slug 风格：kebab-case、语义化英文关键词、≤60 字符。发出去之后不要改 slug——Ghost 会产生 404 旧链接。

### Social thread format

Optimized for 2025-2026 algorithm patterns. See [references/algorithm-guide.md](../../references/algorithm-guide.md).

| Post | Content | Why |
|------|---------|-----|
| 1 (Hook) | Pure text, 120-200 chars, strongest fact | No link penalty, short = punchy |
| 2..N (Body) | Self-replies | Algorithm boost for thread engagement |
| N-1 (Source) | Link to original | Avoids link penalty on first post |
| N (CTA) | Subscribe link | Newsletter growth |

**Markdown 剥离**：`build_thread_posts` 在切分前调用 `_strip_markdown()` 去掉 `**bold**`、`*italic*`、`[text](url)`、`` `code` ``、`#` 标题——Threads/Bluesky 不渲染 Markdown，会显示字面字符。Ghost post body 保持 Markdown 原样（Ghost 会转 HTML）。即使如此，review 阶段应**从源头避免**在社交文案与中文摘要里写 Markdown（见 `review/SKILL.md` §3）。

## Step 2: Staggered posting (optional)

For best algorithm performance, publish 2-4 articles per day with gaps:

```
/loop 60m /newsletter-editor:publish --limit 1
```

Each cycle publishes 1 article. The `/loop` skill sets up a cron job that fires every 60 minutes.

## Weekend Edition Publishing

Weekend editions compile multiple days into one newsletter.md but individual articles still publish separately to Ghost:

- **Ghost newsletter**: Publish newsletter.md as a single Ghost post (the email digest)
- **Ghost individual posts**: Each approved article gets its own Ghost post (for SEO/discoverability)
- **Social**: Only `share: true` articles get social threads, same as daily

## Updating Published Articles

When breaking news updates a published story (e.g., election results, new developments):

### 1. Update article file
- Edit 中文摘要, 社交文案, ai_title, importance, share/share_score as needed
- Run punctuation auto-check on edited Chinese sections

### 2. Update Ghost post
Look up existing post by slug, then PATCH:

```python
# Ghost Admin API — lookup by slug
GET /ghost/api/admin/posts/slug/{slug}/
# Update title + html
PUT /ghost/api/admin/posts/{id}/
  {"posts": [{"title": "...", "html": "...", "updated_at": "..."}]}
```

Auth: JWT with HS256, key from `.env` `GHOST_ADMIN_API_KEY` (`{id}:{secret}`).

### 3. Update newsletter.md
Find and replace the article's entry in the compiled newsletter.

### 4. Update social threads
- If `share` changed from `false` → `true`: publish new social threads via `publish.py`
- If already on social: reply to existing thread with update (thread refs in frontmatter: `bluesky_root_uri`, `threads_id`)
- `publish.py` supports replying to existing Bluesky/Threads threads

## Error Recovery

- **Ghost 429 (rate limit)**: Wait 60s, retry. Or use `--limit 1` with `/loop`.
- **Bluesky auth expired**: Re-authenticate — credentials in `.env`
- **Platform rejection**: Check character limits (Bluesky: 300 chars/post, Threads: 500 chars/post). Truncate or split social content.
- **Partial publish failure**: Safe to re-run — already-published platforms are tracked in `published: []` and skipped.
