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
    """Extract content under a specific heading."""
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=\n## |\Z)"
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
                    "social_content": extract_section(text, "社交文案"),
                    "summary": extract_section(text, "中文摘要"),
                    "published": published if isinstance(published, list) else [],
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

    # Generate slug from title
    slug = article.get("source_url", "").rstrip("/").split("/")[-1][:60] or f"news-{int(_time.time())}"

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

    # Filter to only articles that need publishing on requested platforms
    if args.limit > 0:
        social_plats = ["twitter", "bluesky", "threads"]
        unpublished = []
        for a in articles:
            is_share = a.get("share", False)
            already = a.get("published", [])
            # Determine which platforms this article actually needs
            if args.platform == "all":
                needed = (["twitter", "bluesky", "threads", "ghost"] if is_share
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

    if args.platform == "all":
        requested_platforms = ["twitter", "bluesky", "threads", "ghost"]
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
