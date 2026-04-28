#!/usr/bin/env python3
"""
美轮美换 Newsletter — Social Media Publisher

Publishes approved articles to Twitter/X, Bluesky, and Threads.

Usage:
    python3 skills/newsletter-editor/publish.py [--date YYYY-MM-DD] [--platform twitter|bluesky|threads|ghost|all] [--dry-run] [--limit N]
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx

# --- Load .env from skill directory ---

SCRIPT_DIR = Path(__file__).parent

def _load_dotenv(env_path: Path):
    """Load .env file into os.environ (without overwriting existing vars)."""
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value

_load_dotenv(SCRIPT_DIR / ".env")

# --- Paths ---
VAULT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = SCRIPT_DIR / "config.json"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def get_content_dir(config: dict, target_date: date) -> Path:
    base = VAULT_ROOT / config["content_dir"]
    return base / target_date.strftime("%Y-%m-%d")


# --- Article Reading ---

def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from markdown text."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Handle booleans
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            # Handle lists (simple)
            elif value.startswith("["):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            fm[key] = value
    return fm


def extract_section(text: str, heading: str) -> str:
    """Extract content under a specific heading.

    Only consumes the heading line itself before capturing — empty sections
    must not absorb subsequent headings.
    """
    pattern = rf"^## {re.escape(heading)}[ \t]*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def get_publishable_articles(content_dir: Path) -> list[dict]:
    """Read all approved articles with share=true. Checks approved/ subfolder first, then root."""
    articles = []
    if not content_dir.exists():
        return articles
    # Check approved/ subfolder first, fall back to root
    search_dirs = []
    approved_dir = content_dir / "approved"
    if approved_dir.exists():
        search_dirs.append(approved_dir)
    search_dirs.append(content_dir)

    seen = set()
    for search_dir in search_dirs:
        for f in sorted(search_dir.glob("*.md")):
            if f.name in seen or f.name == "newsletter.md" or f.name in ("review.md",) or f.name.startswith("_"):
                continue
            seen.add(f.name)
            text = f.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            if fm.get("status") == "approved":
                published = fm.get("published", [])
                articles.append({
                    "path": f,
                    "title": fm.get("ai_title", fm.get("title", "")),
                    "source": fm.get("source", ""),
                    "source_url": fm.get("source_url", ""),
                    "importance": fm.get("importance", 0),
                    "share": fm.get("share") is True,
                    "ghost_access": fm.get("ghost_access", "free"),
                    "ghost_slug": fm.get("ghost_slug", ""),
                    "social_content": extract_section(text, "社交文案"),
                    "summary": extract_section(text, "中文摘要"),
                    "published": published if isinstance(published, list) else [],
                    "skip_name_check": fm.get("skip_name_check") is True,
                    "skip_validation": fm.get("skip_validation") is True,
                })
    return articles


def update_published(filepath: Path, platforms: list[str], article: dict = None):
    """Update the published field and thread refs in frontmatter."""
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    existing = fm.get("published", [])
    if isinstance(existing, list):
        updated = list(set(existing + platforms))
    else:
        updated = platforms
    # Replace the published line
    text = re.sub(
        r"^published:.*$",
        f"published: {json.dumps(updated)}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    # Save thread refs for future replies/updates
    if article:
        ref_keys = ["twitter_last_id", "twitter_first_id",
                     "bluesky_root_uri", "bluesky_root_cid",
                     "bluesky_last_uri", "bluesky_last_cid",
                     "threads_last_id"]
        for key in ref_keys:
            val = article.get(key)
            if val:
                if re.search(rf"^{key}:.*$", text, re.MULTILINE):
                    text = re.sub(rf"^{key}:.*$", f'{key}: "{val}"', text, count=1, flags=re.MULTILINE)
                else:
                    text = text.replace("published:", f'{key}: "{val}"\npublished:', 1)
    filepath.write_text(text, encoding="utf-8")


# --- Update / Merge helpers ---

def update_ghost_post(slug: str, append_html: str, dry_run: bool = False) -> bool:
    """Append content to an existing Ghost post by slug."""
    ghost_url = os.environ.get("GHOST_URL")
    admin_key = os.environ.get("GHOST_ADMIN_API_KEY")
    if not ghost_url or not admin_key:
        print("  ✗ Ghost credentials not set")
        return False

    try:
        import jwt as pyjwt
    except ImportError:
        print("  ✗ PyJWT not installed")
        return False

    parts = admin_key.split(":")
    if len(parts) != 2:
        return False
    key_id, key_secret = parts

    import time as _time
    now = int(_time.time())
    payload = {"iat": now, "exp": now + 300, "aud": "/admin/"}
    token = pyjwt.encode(payload, bytes.fromhex(key_secret),
                         algorithm="HS256", headers={"kid": key_id})
    headers = {"Authorization": f"Ghost {token}", "Content-Type": "application/json"}
    base = ghost_url.rstrip("/")

    # Find existing post (must request formats=html to get rendered content)
    resp = httpx.get(f"{base}/ghost/api/admin/posts/slug/{slug}/?formats=html", headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"  ✗ Ghost: post '{slug}' not found")
        return False

    post = resp.json().get("posts", [{}])[0]
    post_id = post["id"]
    updated_at = post["updated_at"]
    existing_html = post.get("html", "")
    if not existing_html:
        print(f"  ✗ Ghost: existing post has no HTML content")
        return False

    new_html = existing_html + "\n" + append_html

    if dry_run:
        print(f"  [DRY RUN] Ghost update: '{slug}' +{len(append_html)} chars")
        return True

    put_resp = httpx.put(
        f"{base}/ghost/api/admin/posts/{post_id}/?source=html",
        headers=headers,
        json={"posts": [{"html": new_html, "updated_at": updated_at}]},
        timeout=30,
    )
    if put_resp.status_code >= 400:
        err = put_resp.json().get("errors", [{}])[0].get("message", f"HTTP {put_resp.status_code}")
        print(f"  ✗ Ghost update error: {err}")
        return False

    print(f"  ✓ Ghost updated: {post.get('url', slug)}")
    return True


def reply_to_twitter_thread(original_article: dict, update_text: str, dry_run: bool = False) -> bool:
    """Reply to an existing Twitter thread with an update."""
    api_key = os.environ.get("TWITTER_API_KEY") or os.environ.get("TWITTER_CONSUMER_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET") or os.environ.get("TWITTER_CONSUMER_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET") or os.environ.get("TWITTER_ACCESS_SECRET")
    if not all([api_key, api_secret, access_token, access_secret]):
        print("  ✗ Twitter credentials not set")
        return False

    # Find the last tweet ID from published data
    last_tweet_id = original_article.get("twitter_last_id")
    if not last_tweet_id:
        print("  ✗ No Twitter thread ID to reply to")
        return False

    if dry_run:
        print(f"  [DRY RUN] Twitter reply to {last_tweet_id}: {update_text[:80]}...")
        return True

    try:
        import tweepy
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_secret)
        api = tweepy.API(auth)
        tweet = api.update_status(update_text, in_reply_to_status_id=last_tweet_id)
        print(f"  ✓ Twitter reply: {tweet.id}")
        return True
    except Exception as e:
        print(f"  ✗ Twitter reply error: {e}")
        return False


def reply_to_bluesky_thread(original_article: dict, update_text: str, dry_run: bool = False) -> bool:
    """Reply to an existing Bluesky thread with an update."""
    handle = os.environ.get("BLUESKY_HANDLE")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not app_password:
        print("  ✗ Bluesky credentials not set")
        return False

    last_uri = original_article.get("bluesky_last_uri")
    last_cid = original_article.get("bluesky_last_cid")
    root_uri = original_article.get("bluesky_root_uri")
    root_cid = original_article.get("bluesky_root_cid")
    if not all([last_uri, last_cid, root_uri, root_cid]):
        print("  ✗ No Bluesky thread refs to reply to")
        return False

    if dry_run:
        print(f"  [DRY RUN] Bluesky reply: {update_text[:80]}...")
        return True

    try:
        base = "https://bsky.social/xrpc"
        session = httpx.post(f"{base}/com.atproto.server.createSession",
                             json={"identifier": handle, "password": app_password}, timeout=30).json()
        did = session["did"]
        access_jwt = session["accessJwt"]
        headers = {"Authorization": f"Bearer {access_jwt}"}

        import datetime
        record = {
            "$type": "app.bsky.feed.post",
            "text": update_text,
            "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "reply": {
                "root": {"uri": root_uri, "cid": root_cid},
                "parent": {"uri": last_uri, "cid": last_cid},
            },
        }
        resp = httpx.post(f"{base}/com.atproto.repo.createRecord",
                          headers=headers, json={"repo": did, "collection": "app.bsky.feed.post", "record": record},
                          timeout=30).json()
        print(f"  ✓ Bluesky reply posted")
        return True
    except Exception as e:
        print(f"  ✗ Bluesky reply error: {e}")
        return False


def reply_to_threads_thread(original_article: dict, update_text: str, dry_run: bool = False) -> bool:
    """Reply to an existing Threads thread with an update."""
    access_token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not access_token:
        print("  ✗ Threads access token not set")
        return False

    last_id = original_article.get("threads_last_id")
    if not last_id:
        print("  ✗ No Threads post ID to reply to")
        return False

    if dry_run:
        print(f"  [DRY RUN] Threads reply: {update_text[:80]}...")
        return True

    try:
        base_url = "https://graph.threads.net/v1.0"
        create = httpx.post(f"{base_url}/me/threads",
                            params={"media_type": "TEXT", "text": update_text,
                                    "reply_to_id": last_id, "access_token": access_token},
                            timeout=60).json()
        if "error" in create:
            print(f"  ✗ Threads reply error: {create['error']}")
            return False
        time.sleep(5)
        pub = httpx.post(f"{base_url}/me/threads_publish",
                         params={"creation_id": create["id"], "access_token": access_token},
                         timeout=60).json()
        if "error" in pub:
            print(f"  ✗ Threads reply error: {pub['error']}")
            return False
        print(f"  ✓ Threads reply posted")
        return True
    except Exception as e:
        print(f"  ✗ Threads reply error: {e}")
        return False


# --- Thread Formatting (shared across platforms) ---
#
# Algorithm insights (2025-2026 X/Twitter research):
#   - Self-reply threads: 150x boost (biggest signal)
#   - External links: -50~90% reach penalty → links ONLY in reply posts
#   - Reply from others: 27x → conversational tone invites engagement
#   - First 15 min critical → hook must be strong
#   - Short posts (<200 chars) outperform long ones
#   - No emoji prefixes, no brackets → look bot-like, reduce reach
#   - Pure text first post → no media competing with text in feed

SUBSCRIBE_CTA = "订阅美轮美换，每日美国政治新闻中文速递\nhttps://theamericanroulette.com/"


def _strip_markdown(text: str) -> str:
    """Strip Markdown formatting that won't render on Threads/Bluesky.

    These platforms treat the text as plain text, so `**bold**` shows up as
    literal asterisks on mobile. Normalize to plain text before splitting.

    Handled:
      - **bold** / __bold__ → bold
      - *italic* / _italic_ → italic (single-char, avoiding collisions with `*` used as list markers)
      - [link text](url)    → "link text url" (keep URL so thread reader can follow)
      - Leading `# ` headings → drop the hash
      - Backtick `code` → code
    """
    if not text:
        return text
    # Links: [text](url) — keep both pieces separated by a space
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", text)
    # Bold: **x** or __x__ (handle before italic so we don't partial-match)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_\n]+)__", r"\1", text)
    # Italic: *x* or _x_ — only when clearly a pair, not list markers
    text = re.sub(r"(?<!\*)\*([^*\s][^*\n]*[^*\s]|\S)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_\s][^_\n]*[^_\s]|\S)_(?!_)", r"\1", text)
    # Inline code
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    # Leading heading hashes on a line
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)
    return text


def format_thread(article: dict, max_post_len: int) -> list[str]:
    """Format article as an algorithm-optimized social thread.

    Structure (optimized for 2025-2026 X algorithm):
      Post 1: Hook — first 1-2 sentences of social content (pure text, no link,
              no emoji prefix, no brackets). Short and punchy (<200 chars ideal).
      Post 2+: Rest of content as self-replies (150x algorithm boost).
      Post N-1: Source attribution + link (in reply, avoids link penalty).
      Post N: Subscribe CTA (drives newsletter growth).
    """
    content = article["social_content"] or article["summary"]
    if not content:
        return []
    content = _strip_markdown(content)

    posts: list[str] = []

    # --- Post 1: Hook — lead with strongest fact, no decoration ---
    # Extract first 1-2 sentences as hook (aim for <200 chars)
    hook, remaining = _extract_hook(content, max_post_len)
    posts.append(hook)

    # --- Middle posts: remaining content as self-replies ---
    while remaining:
        if len(remaining) <= max_post_len:
            posts.append(remaining)
            remaining = ""
        else:
            chunk, remaining = _split_at_boundary(remaining, max_post_len)
            posts.append(chunk)

    # --- Source link post (separate reply — avoids -50~90% link penalty) ---
    source_name = article.get("source", "原文")
    source_url = article.get("source_url", "")
    if source_url:
        posts.append(f"来源: {source_name}\n{source_url}")

    # --- Subscribe CTA ---
    posts.append(SUBSCRIBE_CTA)

    return posts


def _extract_hook(content: str, max_len: int) -> tuple[str, str]:
    """Extract a punchy hook from content. Aims for 1-2 sentences, <200 chars.

    If the full content fits in max_len, returns it all as the hook.
    Otherwise, finds a natural sentence break, preferring shorter hooks
    that pack maximum punch.
    """
    if len(content) <= max_len:
        return content, ""

    # Target hook length: shorter is punchier (ideal 120-200 chars)
    target = min(200, max_len)

    # Find the best sentence break within target range
    chunk = content[:target]
    for punct in ("。", "！", "？", "；"):
        idx = chunk.rfind(punct)
        if idx > 60:  # At least 60 chars for a meaningful hook
            return content[: idx + 1], content[idx + 1 :].strip()

    # If no sentence break found in target, extend to max_len
    if target < max_len:
        chunk = content[:max_len]
        for punct in ("。", "！", "？", "；"):
            idx = chunk.rfind(punct)
            if idx > 60:
                return content[: idx + 1], content[idx + 1 :].strip()

    # Fall back to comma
    idx = chunk.rfind("，")
    if idx > max_len * 0.4:
        return content[: idx + 1], content[idx + 1 :].strip()

    return content[:max_len], content[max_len:].strip()


def _split_at_boundary(text: str, max_len: int) -> tuple[str, str]:
    """Split text at a Chinese sentence boundary (。！？；), falling back to comma."""
    if len(text) <= max_len:
        return text, ""

    chunk = text[:max_len]

    # Try sentence-ending punctuation first
    for punct in ("。", "！", "？", "；"):
        idx = chunk.rfind(punct)
        if idx > max_len * 0.5:
            return text[: idx + 1], text[idx + 1 :].strip()

    # Fall back to comma
    idx = chunk.rfind("，")
    if idx > max_len * 0.4:
        return text[: idx + 1], text[idx + 1 :].strip()

    # Hard split as last resort
    return chunk, text[max_len:].strip()


# --- Bluesky facets ---

def create_bluesky_facets(text: str) -> list[dict]:
    """Create Bluesky rich-text facets for URLs."""
    facets = []
    for match in re.finditer(r"https?://\S+", text):
        url = match.group()
        byte_start = len(text[: match.start()].encode("utf-8"))
        byte_end = len(text[: match.end()].encode("utf-8"))
        facets.append(
            {
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
            }
        )
    return facets


# --- Twitter/X ---

def publish_twitter(article: dict, dry_run: bool = False) -> bool:
    """Publish thread to Twitter/X."""
    try:
        import tweepy
    except ImportError:
        print("  ✗ tweepy not installed. Run: pip install tweepy")
        return False

    api_key = os.environ.get("TWITTER_API_KEY") or os.environ.get("TWITTER_CONSUMER_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET") or os.environ.get("TWITTER_CONSUMER_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET") or os.environ.get("TWITTER_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("  ✗ Twitter credentials not set")
        return False

    tweets = format_thread(article, max_post_len=270)
    if not tweets:
        print("  ✗ No content to post")
        return False

    if dry_run:
        print(f"  [DRY RUN] Twitter: {len(tweets)} tweet(s)")
        for i, t in enumerate(tweets):
            print(f"    ({i + 1}) {t[:100]}...")
        return True

    try:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        prev_id = None
        first_id = None
        for tweet_text in tweets:
            resp = client.create_tweet(text=tweet_text, in_reply_to_tweet_id=prev_id)
            prev_id = resp.data["id"]
            if first_id is None:
                first_id = prev_id
            time.sleep(2)
        # Store thread refs for future replies
        article["twitter_last_id"] = str(prev_id)
        article["twitter_first_id"] = str(first_id)
        print(f"  ✓ Twitter: posted {len(tweets)} tweet(s)")
        return True
    except Exception as e:
        print(f"  ✗ Twitter error: {e}")
        return False


# --- Bluesky ---

def publish_bluesky(article: dict, dry_run: bool = False) -> bool:
    """Publish thread to Bluesky."""
    handle = os.environ.get("BLUESKY_HANDLE")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD")

    if not handle or not app_password:
        print("  ✗ Bluesky credentials not set")
        return False

    posts = format_thread(article, max_post_len=280)
    if not posts:
        print("  ✗ No content to post")
        return False

    if dry_run:
        print(f"  [DRY RUN] Bluesky: {len(posts)} post(s)")
        for i, p in enumerate(posts):
            print(f"    ({i + 1}) {p[:100]}...")
        return True

    try:
        session = httpx.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": app_password},
        ).json()

        if "error" in session:
            print(f"  ✗ Bluesky auth failed: {session['error']}")
            return False

        did = session["did"]
        headers = {"Authorization": f"Bearer {session['accessJwt']}"}

        from datetime import datetime, timezone

        root_uri = root_cid = None
        prev_uri = prev_cid = None

        for i, post_text in enumerate(posts):
            record = {
                "$type": "app.bsky.feed.post",
                "text": post_text,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "langs": ["zh"],
            }

            facets = create_bluesky_facets(post_text)
            if facets:
                record["facets"] = facets

            if prev_uri and prev_cid:
                record["reply"] = {
                    "root": {"uri": root_uri, "cid": root_cid},
                    "parent": {"uri": prev_uri, "cid": prev_cid},
                }

            resp = httpx.post(
                "https://bsky.social/xrpc/com.atproto.repo.createRecord",
                headers=headers,
                json={
                    "repo": did,
                    "collection": "app.bsky.feed.post",
                    "record": record,
                },
            ).json()

            if "error" in resp:
                print(f"  ✗ Bluesky post error: {resp['error']}")
                return False

            prev_uri = resp.get("uri")
            prev_cid = resp.get("cid")
            if i == 0:
                root_uri, root_cid = prev_uri, prev_cid
            time.sleep(1)

        # Store thread refs for future replies
        article["bluesky_root_uri"] = root_uri
        article["bluesky_root_cid"] = root_cid
        article["bluesky_last_uri"] = prev_uri
        article["bluesky_last_cid"] = prev_cid
        print(f"  ✓ Bluesky: posted {len(posts)} post(s)")
        return True
    except Exception as e:
        print(f"  ✗ Bluesky error: {e}")
        return False


# --- Threads ---

def publish_threads(article: dict, dry_run: bool = False) -> bool:
    """Publish thread to Threads."""
    access_token = os.environ.get("THREADS_ACCESS_TOKEN")

    if not access_token:
        print("  ✗ Threads access token not set")
        return False

    posts = format_thread(article, max_post_len=480)
    if not posts:
        print("  ✗ No content to post")
        return False

    if dry_run:
        print(f"  [DRY RUN] Threads: {len(posts)} post(s)")
        for i, p in enumerate(posts):
            print(f"    ({i + 1}) {p[:100]}...")
        return True

    try:
        base_url = "https://graph.threads.net/v1.0"
        prev_id = None

        for post_text in posts:
            params = {
                "media_type": "TEXT",
                "text": post_text,
                "access_token": access_token,
            }
            if prev_id:
                params["reply_to_id"] = prev_id

            create_resp = httpx.post(f"{base_url}/me/threads", params=params, timeout=60).json()

            if "error" in create_resp:
                print(f"  ✗ Threads create error: {create_resp['error']}")
                return False

            container_id = create_resp["id"]
            time.sleep(5)

            pub_resp = httpx.post(
                f"{base_url}/me/threads_publish",
                params={"creation_id": container_id, "access_token": access_token},
                timeout=60,
            ).json()

            if "error" in pub_resp:
                print(f"  ✗ Threads publish error: {pub_resp['error']}")
                return False

            prev_id = pub_resp.get("id")
            time.sleep(2)

        article["threads_last_id"] = str(prev_id)
        print(f"  ✓ Threads: posted {len(posts)} post(s)")
        return True
    except Exception as e:
        print(f"  ✗ Threads error: {e}")
        return False


# --- Ghost ---

def publish_ghost(article: dict, dry_run: bool = False) -> bool:
    """Publish to Ghost CMS via Admin API."""
    ghost_url = os.environ.get("GHOST_URL")
    admin_key = os.environ.get("GHOST_ADMIN_API_KEY")

    if not ghost_url or not admin_key:
        print("  ✗ Ghost credentials not set (GHOST_URL, GHOST_ADMIN_API_KEY)")
        return False

    try:
        import jwt as pyjwt
    except ImportError:
        print("  ✗ PyJWT not installed. Run: pip install PyJWT")
        return False

    content = article["summary"] or article["social_content"]
    if not content:
        print("  ✗ No content to post")
        return False

    # Parse admin key (format: {id}:{secret})
    parts = admin_key.split(":")
    if len(parts) != 2:
        print("  ✗ Invalid GHOST_ADMIN_API_KEY format (expected id:secret)")
        return False
    key_id, key_secret = parts

    # Generate JWT
    import time as _time
    now = int(_time.time())
    payload = {"iat": now, "exp": now + 300, "aud": "/admin/"}
    token = pyjwt.encode(payload, bytes.fromhex(key_secret),
                         algorithm="HS256",
                         headers={"kid": key_id})

    # Format HTML content
    source_name = article.get("source", "")
    source_url = article.get("source_url", "")
    html_parts = [f"<p>{content}</p>"]
    if source_url:
        html_parts.append(
            f'<p><a href="{source_url}">📄 {source_name or "原文链接"}</a></p>'
        )
    html = "\n".join(html_parts)

    # Slug resolution: ghost_slug frontmatter override > URL basename > filename stem > timestamp
    from urllib.parse import urlparse as _urlparse
    _url_path = _urlparse(article.get("source_url", "")).path.rstrip("/")
    slug = (
        article.get("ghost_slug")
        or (_url_path.split("/")[-1][:60] if _url_path else "")
        or article["path"].stem[:60]
        or f"news-{int(_time.time())}"
    )

    post_data = {
        "posts": [{
            "title": article["title"],
            "html": html,
            "tags": [{"name": "美国新闻速递"}],
            "status": "published",
            "custom_excerpt": f"{source_name}|{source_url}" if source_url else "",
            "visibility": "public" if article.get("ghost_access", "free") == "free" else "paid",
            "slug": slug,
        }]
    }

    if dry_run:
        print(f"  [DRY RUN] Ghost: \"{article['title']}\" → {ghost_url}")
        print(f"    slug: {slug}")
        return True

    try:
        resp = httpx.post(
            f"{ghost_url.rstrip('/')}/ghost/api/admin/posts/?source=html",
            headers={
                "Authorization": f"Ghost {token}",
                "Content-Type": "application/json",
            },
            json=post_data,
            timeout=30,
        )
        data = resp.json()

        if resp.status_code >= 400:
            err = data.get("errors", [{}])[0].get("message", f"HTTP {resp.status_code}")
            print(f"  ✗ Ghost error: {err}")
            return False

        post = data.get("posts", [{}])[0]
        print(f"  ✓ Ghost: {post.get('url', 'published')}")
        return True
    except Exception as e:
        print(f"  ✗ Ghost error: {e}")
        return False


# --- Main ---

# --- Pre-publish validation gate ---
# Enforces skill rules that previously lived only as documentation in
# review/SKILL.md and translation-guide.md. See memory:
#   feedback_newsletter_ai_title_length, feedback_newsletter_summary_length,
#   feedback_newsletter_no_markdown_social, feedback_newsletter_title_no_media

_CJK_RE = re.compile(r"[一-鿿]")

# Disallowed media-name prefixes in ai_title (e.g. "NYT：xxx").
# Skill rule (memory feedback_newsletter_title_no_media): media attribution
# already shown in trailing （[Source](url)）—reader doesn't need it twice.
_TITLE_MEDIA_PREFIXES = [
    "NYT", "Politico", "WaPo", "Washington Post", "WSJ", "Wall Street Journal",
    "CNN", "NBC", "NBC News", "CBS", "CBS News", "ABC", "ABC News",
    "Bloomberg", "Reuters", "AP", "美联社", "路透社", "彭博社",
    "Daily Beast", "emptywheel", "Just Security", "The Atlantic", "Atlantic",
    "Mother Jones", "ProPublica", "The Intercept", "Intercept",
    "Axios", "Semafor", "Punchbowl", "The Bulwark", "Bulwark", "Fox News",
    "Economist", "The Economist", "Guardian", "The Guardian", "Lawfare", "New Republic",
    "纽约时报", "华盛顿邮报", "华尔街日报", "福克斯新闻", "经济学人", "卫报",
]
# Whitelist: signed-byline columns / ratings / polls keep their prefix.
# (Skill exception: 「克鲁格曼：…」「Politico Playbook：…」「Cook 评级：…」)
_TITLE_PREFIX_WHITELIST = (
    "Politico Playbook", "Politico Influence",
    "克鲁格曼", "桑格", "加内什", "Beutler",
    "Cook 评级", "Marist 民调",
)

# Summary length tiers by importance — translation-guide.md "Summary Length"
_LENGTH_TIERS = [(1, 3, 80, 120), (4, 6, 100, 160), (7, 8, 140, 200), (9, 10, 180, 240)]

# Latin proper-noun candidates that are NOT person names (media, orgs, places kept in English).
# Per-article override: add `skip_name_check: true` to frontmatter.
_NAME_FORMAT_WHITELIST = {
    # Media (English-keep tier)
    "Lawfare", "Axios", "Semafor", "Politico", "Punchbowl", "Bulwark",
    "Newrepublic", "Mediaite", "Substack", "Newsmax", "Imprimis", "WaPo",
    "Daily", "Beast", "Mother", "Jones", "ProPublica", "Atlantic",
    "Intercept", "Guardian", "Economist", "Reuters", "Bloomberg", "Ipsos",
    # Journals / institutions
    "Pediatrics", "Hillsdale", "Caltech", "Harvard", "Yale", "Princeton",
    # Orgs / products kept English
    "Burisma", "Roundup", "Monsanto", "Bayer", "Tesla", "Disney",
    "Twitter", "Threads", "Bluesky", "YouTube", "Spotify", "Yachad",
    # US place fragments / small locations
    "Pierce", "Moultrie", "Harlan", "Tazewell", "Capitol",
    # Common English nouns capitalized at sentence start / inside org names
    "The", "And", "But", "For", "With", "From", "When", "Where", "How", "Why",
    "Department", "Justice", "Court", "Senate", "House", "Congress",
    "News", "Police", "Society", "Rule", "Law", "Act", "Truth", "Social",
    "Results", "Tree", "Pine", "Docket", "Democracy", "Cook", "Sabato",
}


# Style-check constants — translation-guide.md "Common Errors" §2/§4
# Per-article override: add `skip_validation: true` to frontmatter to bypass ALL style checks.
_JARGON_BLACKLIST = (
    # English jargon I tend to leave un-translated
    "fast-track", "reckoning", "dummymander", "OPP",
    "mixed feelings", "buckshot", "ballroom-style",
    "just not up for", "fast track",
    # Chinese internet slang / wenzhang slang we want to avoid in formal news prose
    "认知失调", "重置棋盘", "洗地", "薄壁", "破防",
)

# Media-name uppercase abbreviations that should be 《中文媒体名》 in body text.
# Detection: token NOT preceded by 《 (which means already wrapped properly).
# Whitelist: Reuters/Bloomberg/Politico etc. that we keep in English.
_MEDIA_UPPERCASE_BLACKLIST = (
    "NYT", "WSJ", "WaPo", "CNN", "MSNBC", "NBC", "ABC", "CBS", "Fox",
)


def _check_date_format(text: str) -> list[str]:
    """Flag `2/28`-style numeric dates in body — should be `2 月 28 日`.

    Skips lines containing http (URLs) or pure data lists. Conservative regex
    requires 1-2 digit / 1-2 digit, surrounded by non-date chars.
    """
    if not text:
        return []
    issues = []
    for line in text.splitlines():
        if "http" in line or "URL" in line:
            continue
        for m in re.finditer(r"(?<![\d/-])\d{1,2}/\d{1,2}(?![\d/])", line):
            issues.append(m.group())
    return issues


def _check_media_uppercase(text: str) -> list[str]:
    """Flag uppercase media tokens (NYT/WSJ/WaPo/CNN/...) not preceded by 《.

    Whitelisted are media we keep in English (Reuters, Bloomberg, Politico, etc.)
    """
    if not text:
        return []
    issues = []
    for token in _MEDIA_UPPERCASE_BLACKLIST:
        for m in re.finditer(rf"\b{re.escape(token)}\b", text):
            # Skip if already in 《...》 — preceding char is 《
            if m.start() > 0 and text[m.start() - 1] == "《":
                continue
            issues.append(token)
            break  # one occurrence per token is enough to flag
    return sorted(set(issues))


def _check_ai_title_quality(title: str) -> list[str]:
    """Three sub-rules: length ≥ 10 CJK, no jargon, no `EnglishName:` prefix.

    Whitelist `_TITLE_PREFIX_WHITELIST` exempts signed bylines / ratings /
    polls (Politico Playbook, 克鲁格曼, Cook 评级, etc.).
    """
    if not title:
        return []
    issues = []
    title_cjk = _cjk_count(title)
    if title_cjk < 10:
        issues.append(f"ai_title 中文字 {title_cjk} 字 < 10 字下限")
    # Jargon (any lowercase match, case-insensitive)
    title_lower = title.lower()
    for word in _JARGON_BLACKLIST:
        if word.lower() in title_lower:
            issues.append(f"ai_title 含黑话「{word}」")
    # English-name colon prefix (e.g., "Beutler：")
    if not any(w in title[:25] for w in _TITLE_PREFIX_WHITELIST):
        if re.match(r"^[A-Z][a-z]+\s*[:：]", title):
            issues.append(f"ai_title 以英文人名+冒号开头")
    return issues


def _check_name_format(text: str) -> list[str]:
    """Find Latin proper nouns NOT enclosed in （…） — likely missing 中文 translation.

    Rule: 人名首次出现必须是「中文（English）」。Heuristic flags mixed-case tokens
    of length ≥ 4 that are not inside a Chinese parenthetical. Pure acronyms (ICE,
    FBI) are excluded by the mixed-case filter. False positives can be silenced
    per-article via `skip_name_check: true` in frontmatter.
    """
    if not text:
        return []
    issues = []
    for m in re.finditer(r"\b[A-Z][A-Za-z]{3,}\b", text):
        token = m.group()
        if token.isupper() or token.islower():
            continue
        if token in _NAME_FORMAT_WHITELIST:
            continue
        prefix = text[: m.start()]
        if prefix.rfind("（") > prefix.rfind("）"):
            continue
        issues.append(token)
    return issues


def _cjk_count(s: str) -> int:
    """Count CJK characters only — skill measures titles/summaries in 中文字数."""
    return len(_CJK_RE.findall(s or ""))


def validate_article(article: dict) -> list[str]:
    """Return list of human-readable violations. Empty list = passes all checks.

    Per-article whole-bypass: add `skip_validation: true` to frontmatter.
    """
    if article.get("skip_validation"):
        return []
    violations = []
    title = (article.get("title") or "").strip()
    summary = article.get("summary") or ""
    social = article.get("social_content") or ""
    importance = article.get("importance", 0)
    if isinstance(importance, str):
        try:
            importance = int(importance)
        except ValueError:
            importance = 0

    # 1. ai_title hard cap: 18 CJK chars
    title_cjk = _cjk_count(title)
    if title_cjk > 18:
        violations.append(f"ai_title 超 18 中文字硬上限 ({title_cjk} 字): {title}")

    # 2. ai_title 不得以媒体名+冒号开头（白名单内豁免）
    if not any(w in title[:25] for w in _TITLE_PREFIX_WHITELIST):
        for prefix in _TITLE_MEDIA_PREFIXES:
            if re.match(rf"^{re.escape(prefix)}\s*[:：]", title):
                violations.append(f"ai_title 以媒体名开头 ({prefix}：): {title}")
                break

    # 3. 中文摘要 / 社交文案 不得含 Markdown
    for label, text in (("中文摘要", summary), ("社交文案", social)):
        if not text:
            continue
        if re.search(r"\*\*[^*\n]+\*\*", text):
            violations.append(f"{label} 含 Markdown 粗体 (**bold**)")
        if re.search(r"\[[^\]]+\]\([^)\s]+\)", text):
            violations.append(f"{label} 含 Markdown 链接 [text](url)")
        if re.search(r"(?m)^#+\s", text):
            violations.append(f"{label} 含 Markdown 标题 (#)")

    # 4. 中文摘要 字数与 importance 分级一致（+10% 软容忍）
    summary_cjk = _cjk_count(summary)
    if summary_cjk > 0:
        for lo, hi, lmin, lmax in _LENGTH_TIERS:
            if lo <= importance <= hi:
                hard_cap = int(lmax * 1.10)
                if summary_cjk > hard_cap:
                    violations.append(
                        f"中文摘要 {summary_cjk} 字超 imp={importance} 上限 {lmax} "
                        f"(+10% 容忍 {hard_cap})"
                    )
                break

    # 5. 人名格式（首次出现「中文（English）」）— 可 frontmatter 加 skip_name_check: true 豁免
    if not article.get("skip_name_check"):
        for label, text in (("中文摘要", summary), ("社交文案", social)):
            naked = _check_name_format(text)
            if naked:
                unique = sorted(set(naked))
                violations.append(
                    f"{label} 含未译人名: {', '.join(unique[:6])}"
                    f"{' ...' if len(unique) > 6 else ''}"
                    "（首次出现要「中文（English）」；如确为机构/地名/媒体名误报，"
                    "frontmatter 加 skip_name_check: true）"
                )

    # 6. 日期格式：summary/social 内 `2/28` 应为 `2 月 28 日`
    for label, text in (("中文摘要", summary), ("社交文案", social)):
        bad_dates = _check_date_format(text)
        if bad_dates:
            unique = sorted(set(bad_dates))
            violations.append(
                f"{label} 含数字日期: {', '.join(unique[:5])}"
                f"{' ...' if len(unique) > 5 else ''}"
                "（应改为「N 月 N 日」格式）"
            )

    # 7. 媒体英文缩写：summary/social 内 NYT/WSJ/WaPo 等应为《中文媒体名》
    for label, text in (("中文摘要", summary), ("社交文案", social)):
        bad_media = _check_media_uppercase(text)
        if bad_media:
            violations.append(
                f"{label} 含未中译媒体: {', '.join(bad_media)}"
                "（首次出现应为《纽约时报》《华尔街日报》等中文加书名号格式）"
            )

    # 8. ai_title style: 中文字 ≥ 10 + 无黑话 + 无「英文名：」前缀
    title_issues = _check_ai_title_quality(title)
    for issue in title_issues:
        violations.append(f"{issue}: {title}")

    return violations


def run_preflight_validation(articles: list[dict]) -> int:
    """Run validate_article on each. Print summary, return number of articles with violations."""
    failed = 0
    for a in articles:
        vios = validate_article(a)
        if vios:
            failed += 1
            print(f"✗ {a['path'].name}")
            for v in vios:
                print(f"    · {v}")
    return failed


def main():
    parser = argparse.ArgumentParser(description="Publish 美轮美换 Newsletter to social media")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--platform", type=str, default="all",
                        choices=["twitter", "bluesky", "threads", "ghost", "all"],
                        help="Platform to publish to")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without publishing")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max number of unpublished articles to process (0 = all)")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Bypass pre-flight skill-rule validation (titles, summary length, "
                             "Markdown). Use only for emergency re-publishes; fix violations first.")
    args = parser.parse_args()

    target_date = date.today()
    if args.date:
        target_date = date.fromisoformat(args.date)

    config = load_config()
    content_dir = get_content_dir(config, target_date)

    print(f"📢 美轮美换 Newsletter Publisher")
    print(f"   Date: {target_date.isoformat()}")
    print(f"   Platform: {args.platform}")
    if args.dry_run:
        print(f"   Mode: DRY RUN\n")
    else:
        print()

    articles = get_publishable_articles(content_dir)
    if not articles:
        print("No approved articles found.")
        return

    # --- Pre-flight skill-rule validation gate ---
    # Refuses to publish articles that violate documented skill rules
    # (ai_title length, summary length tier, Markdown in 中文 sections, media-name prefix).
    # Only validates articles that still have unpublished platforms — already-published
    # articles can't be edited retroactively, so don't block today's batch on yesterday's debt.
    # Bypass with --skip-validation only for emergency re-publishes.
    if not args.skip_validation:
        # Determine which articles still need any publishing
        social_plats_v = ["bluesky", "threads"]
        pending = []
        for a in articles:
            already = a.get("published", [])
            is_share_v = a.get("share", False)
            if args.platform == "all":
                needed_v = (["bluesky", "threads", "ghost"] if is_share_v else ["ghost"])
            else:
                needed_v = [args.platform]
            if any(p not in already for p in needed_v):
                pending.append(a)
        failures = run_preflight_validation(pending) if pending else 0
        if failures:
            print(f"\n✗ {failures} article(s) failed pre-flight validation. "
                  f"Fix the violations above (or pass --skip-validation to override) "
                  f"and re-run.\n")
            sys.exit(1)

    # Filter to only articles that need publishing on requested platforms
    if args.limit > 0:
        social_plats = ["bluesky", "threads"]
        unpublished = []
        for a in articles:
            is_share = a.get("share", False)
            already = a.get("published", [])
            # Determine which platforms this article actually needs
            # NOTE: twitter/X is currently disabled (account suspended) — excluded from "all"
            if args.platform == "all":
                needed = (["bluesky", "threads", "ghost"] if is_share
                          else ["ghost"])
            else:
                needed = [args.platform]
            if any(p not in already for p in needed):
                unpublished.append(a)
        articles = unpublished[:args.limit]

    print(f"Found {len(articles)} article(s) to publish:\n")

    social_platforms = ["twitter", "bluesky", "threads"]
    platforms_map = {
        "twitter": publish_twitter,
        "bluesky": publish_bluesky,
        "threads": publish_threads,
        "ghost": publish_ghost,
    }

    # NOTE: twitter/X is currently disabled (account suspended) — excluded from "all".
    # Use --platform twitter explicitly to override.
    if args.platform == "all":
        requested_platforms = ["bluesky", "threads", "ghost"]
    else:
        requested_platforms = [args.platform]

    for article in articles:
        is_share = article.get("share", False)
        access = article.get("ghost_access", "free")
        label = "viral/free" if is_share else "deep/paid"
        print(f"📄 {article['title']} ({label})")
        published_to = []

        for platform in requested_platforms:
            # Skip social platforms for non-share articles
            if platform in social_platforms and not is_share:
                print(f"  ⏭ {platform}: skipped (deep/paid article)")
                continue

            # Skip if already published to this platform
            if platform in article.get("published", []):
                print(f"  ⏭ {platform}: already published")
                continue

            publisher = platforms_map[platform]
            success = publisher(article, dry_run=args.dry_run)
            if success and not args.dry_run:
                published_to.append(platform)

            time.sleep(3)  # Delay between platforms

        # Update frontmatter
        if published_to and not args.dry_run:
            update_published(article["path"], published_to, article)

        print()

    print(f"{'='*50}")
    print(f"✅ Publishing complete for {target_date.isoformat()}")


if __name__ == "__main__":
    main()
