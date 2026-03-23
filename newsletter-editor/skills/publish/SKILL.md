---
name: publish
description: |
  美轮美换发布。将approved文章发布到Ghost和社交媒体（Twitter/X、Bluesky、Threads）。每天可执行多次。
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
python3 skills/newsletter-editor/publish.py --platform twitter # twitter only
python3 skills/newsletter-editor/publish.py --dry-run          # preview
python3 skills/newsletter-editor/publish.py --date 2026-03-22  # specific date
```

Credentials auto-loaded from `skills/newsletter-editor/.env`.

### Publishing logic

- **All approved articles** → Ghost (as individual posts)
- **`share: true` articles only** → social media (Twitter, Bluesky, Threads)
- `ghost_access: paid` → Ghost members-only; `free` → public
- Already-published platforms are skipped (tracked in `published: []` frontmatter)

### Social thread format

Optimized for 2025-2026 X algorithm. See [references/algorithm-guide.md](../../references/algorithm-guide.md).

| Post | Content | Why |
|------|---------|-----|
| 1 (Hook) | Pure text, 120-200 chars, strongest fact | No link penalty, short = punchy |
| 2..N (Body) | Self-replies | 150x algorithm boost |
| N-1 (Source) | Link to original | Avoids -50~90% link penalty on first post |
| N (CTA) | Subscribe link | Newsletter growth |

## Step 2: Staggered posting (optional)

For best algorithm performance, publish 2-4 articles per day with gaps:

```
/loop 60m /newsletter-editor:publish
```

Each cycle publishes 1 article (`--limit 1` behavior in loop mode).

## Updating published articles

If an article gets new developments after publishing:

- `publish.py` supports replying to existing Twitter/Bluesky/Threads threads
- Ghost posts can be appended to via slug
- Thread refs (`twitter_last_id`, `bluesky_root_uri`, etc.) are stored in frontmatter
