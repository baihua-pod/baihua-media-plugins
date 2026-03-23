#!/usr/bin/env python3
"""
美轮美换 Newsletter — RSS Feed Fetcher

Fetches articles from configured RSS feeds, scrapes full content via Jina Reader,
and saves as markdown files in the Obsidian vault for Claude to translate.

Usage:
    python3 skills/newsletter-editor/fetch_rss.py [--date YYYY-MM-DD]
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, date, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup


# --- Paths ---

SCRIPT_DIR = Path(__file__).parent
VAULT_ROOT = SCRIPT_DIR.parent.parent  # Navigate up from skills/baihua-newsletter/
CONFIG_PATH = SCRIPT_DIR / "config.json"
CONTENT_BASE = None  # Set after loading config


def load_config():
    """Load RSS source configuration."""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def get_content_dir(config: dict, target_date: date) -> Path:
    """Get the content directory for a specific date."""
    base = VAULT_ROOT / config["content_dir"]
    return base / target_date.strftime("%Y-%m-%d")


# --- URL Extraction ---

def extract_aggregator_urls(html_description: str) -> list[str]:
    """
    Extract article URLs from aggregator RSS descriptions (memeorandum/mediagazer pattern).
    These aggregators embed links to actual articles in their HTML description field.
    """
    soup = BeautifulSoup(html_description, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Skip internal aggregator links and anchors
        parsed = urlparse(href)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            domain = parsed.netloc.lower().replace("www.", "")
            # Skip links back to the aggregator itself
            if domain not in ("memeorandum.com", "mediagazer.com", "techmeme.com", "politicalwire.com"):
                urls.append(href)
    # Return unique URLs preserving order
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def get_source_from_url(url: str) -> str:
    """Extract a human-readable source name from a URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    # Map common domains to names
    domain_names = {
        "nytimes.com": "NYT",
        "washingtonpost.com": "Washington Post",
        "politico.com": "Politico",
        "thehill.com": "The Hill",
        "cnn.com": "CNN",
        "foxnews.com": "Fox News",
        "reuters.com": "Reuters",
        "apnews.com": "AP News",
        "npr.org": "NPR",
        "bbc.co.uk": "BBC",
        "bbc.com": "BBC",
        "axios.com": "Axios",
        "bloomberg.com": "Bloomberg",
        "wsj.com": "WSJ",
        "ft.com": "Financial Times",
        "theatlantic.com": "The Atlantic",
        "newyorker.com": "The New Yorker",
        "economist.com": "The Economist",
        "mediaite.com": "Mediaite",
        "rollcall.com": "Roll Call",
        "realclearpolitics.com": "Real Clear Politics",
        "politicalwire.com": "Political Wire",
        "nbcnews.com": "NBC News",
        "abcnews.go.com": "ABC News",
        "cbsnews.com": "CBS News",
        "theguardian.com": "The Guardian",
        "vox.com": "Vox",
        "slate.com": "Slate",
    }
    for d, name in domain_names.items():
        if d in domain:
            return name
    # Fallback: capitalize domain parts
    parts = domain.replace(".com", "").replace(".org", "").replace(".co.uk", "").split(".")
    return " ".join(p.capitalize() for p in parts)


# --- Content Scraping ---

def scrape_with_jina(url: str, timeout: int = 30) -> str | None:
    """Scrape article content using Jina Reader API."""
    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "text/markdown",
        "X-Return-Format": "markdown",
    }
    api_key = os.environ.get("JINA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.get(jina_url, headers=headers, timeout=timeout, follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 200:
            return clean_jina_content(resp.text)
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        print(f"  ⚠ Jina scrape failed for {url}: {e}")
    return None


def clean_jina_content(text: str) -> str:
    """Clean Jina Reader markdown output by removing navigation, ads, footers, etc."""
    lines = text.split("\n")

    # --- Pass 1: Extract metadata and find article body start ---
    title_line = None
    body_start = 0
    published_time = ""

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Published Time:"):
            published_time = stripped
            continue
        # Find the first H1 title
        if title_line is None and stripped.startswith("# "):
            title_line = i
            continue
        # After title, find the first substantial paragraph that looks like article text
        if title_line is not None and len(stripped) > 80 \
                and not stripped.startswith(("#", "*", "[", "!", "|", "---", ">")) \
                and not _is_boilerplate(stripped):
            body_start = i
            break

    if not title_line:
        body_start = 0

    # --- Pass 2: Find footer boundary ---
    body_end = len(lines)
    min_body_lines = body_start + 5
    for i in range(min_body_lines, len(lines)):
        stripped = lines[i].strip()
        if _is_footer_boundary(stripped):
            body_end = i
            break

    # --- Pass 3: Extract article body, skip junk lines ---
    cleaned = []
    if published_time:
        cleaned.append(published_time)
        cleaned.append("")
    if title_line is not None:
        cleaned.append(lines[title_line])
        cleaned.append("")

    for i in range(body_start, body_end):
        stripped = lines[i].strip()
        if _is_junk_line(stripped):
            continue
        cleaned.append(lines[i])

    text = "\n".join(cleaned)

    # --- Pass 4: Regex-based cleanup ---

    # Remove images
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)

    # Remove empty/short markdown links and mailto links
    text = re.sub(r"\[]\([^)]+\)", "", text)
    text = re.sub(r"\[[^\]]*\]\(mailto:[^)]+\)", "", text)

    # Remove nav link lists (* [Text](url)) and bare link-only bullet items
    text = re.sub(r"^\s*\*\s+\[[^\]]+\]\([^)]+\)\s*$", "", text, flags=re.MULTILINE)
    # Bare bullet items with just whitespace or nothing
    text = re.sub(r"^\s*\*\s*$", "", text, flags=re.MULTILINE)

    # Remove standalone short markdown links (nav/tags)
    text = re.sub(r"^\s*\[[^\]]{1,30}\]\(https?://[^)]+\)\s*$", "", text, flags=re.MULTILINE)

    # Remove copyright lines
    text = re.sub(r"^\s*(Copyright|©).*\d{4}.*$", "", text, flags=re.MULTILINE)

    # Remove tracking pixels / long bare URLs
    text = re.sub(r"^\s*https?://\S{100,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*,\S{50,}\s*$", "", text, flags=re.MULTILINE)

    # Remove template/tracking variables
    text = re.sub(r"^\s*\{\{.*\}\}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*#\w+\s*$", "", text, flags=re.MULTILINE)

    # Collapse 3+ blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _is_boilerplate(line: str) -> bool:
    """Check if a long line is boilerplate rather than article content."""
    boilerplate_signals = [
        "cookies", "tracking technologies", "personal data", "opt in or out",
        "targeted advertising", "privacy policy", "consent",
        "preferred source", "HANDOUT via REUTERS", "THIS IMAGE HAS BEEN SUPPLIED",
    ]
    lower = line.lower()
    return sum(1 for s in boilerplate_signals if s in lower) >= 2


def _is_footer_boundary(line: str) -> bool:
    """Detect lines that indicate the start of footer/related/recommended sections."""
    triggers = [
        # Related / recommended content
        "Related Articles", "Related Stories", "Related", "Recommended",
        "You Might Also Like", "Read Next", "Also Read", "Most Read",
        "What to read next", "What to Read Next", "Up Next",
        "More from the BBC", "More from BBC", "More from CNN", "More from Fox",
        "More In Politics", "More In News", "Trending Now",
        "Stories Chosen For You", "Keep on reading",
        # Site sections
        "BBC in other languages", "The BBC is in multiple languages",
        "Site Information", "Site Navigation",
        "Terms of Use", "Privacy Policy", "Cookie Policy",
        "Follow BBC on", "Follow us on",
        # Newsletter signups
        "Sign Up", "Newsletter Sign Up", "POLITICO Forecast",
        "Please check your inbox", "You are already subscribed",
        "Something went wrong", "All fields must be completed",
        "Get the latest",
        # Sponsored / ads
        "SPONSORED CONTENT", "Sponsored Content",
        # Comment sections
        "READ COMMENTS", "Join the discussion",
        # Paywall / subscription
        "Smarter, faster", "Your Privacy Choices",
        # Support/corrections
        "For customer support", "For corrections contact",
    ]
    if any(line == t or line.startswith(t) for t in triggers):
        return True
    # Also match heading forms: "## Related", "### Stories Chosen For You"
    clean = re.sub(r"^#{1,5}\s*", "", line)
    if any(clean == t or clean.startswith(t) for t in triggers):
        return True
    return False


def _is_junk_line(line: str) -> bool:
    """Check if a line is junk content within the article body."""

    # --- Exact matches (standalone words/phrases) ---
    junk_words = {
        "Advertisement", "ADVERTISEMENT", "Ad", "Share", "Save",
        "Copy link", "Print", "Subscribe", "Sign In", "Toggle menu",
        "Watch Live", "Login", "Search", "All topics",
        # BBC nav
        "News", "Sport", "Business", "Technology", "Health", "Culture",
        "Arts", "Travel", "Earth", "Audio", "Video", "Live", "Documentaries",
        # Form fields
        "Email", "Employer", "Job Title", "First Name", "Last Name",
        "Country", "Zip Code", "Company", "Sign Up", "Submit",
        "Loading", "Filed Under:",
        # Image credits
        "Getty Images", "AP", "Reuters", "AFP", "AP Photo",
    }
    if line in junk_words:
        return True

    # --- Pattern matches ---

    # Video duration timestamps (1:38, 12:05)
    if re.match(r"^\d{1,2}:\d{2}$", line):
        return True

    # Relative timestamps: "9 hours ago", "37 minutes ago"
    if re.match(r"^\d+\s+(mins?|hours?|days?|hrs?|minutes?|seconds?)\s+ago", line):
        return True
    # Timestamps with category: "9 hours ago - Politics"
    if re.match(r"^\d+\s+\w+\s+ago\s*[-–—]", line):
        return True

    # Empty/bare markdown links
    if re.match(r"^\[]\([^)]*\)$", line):
        return True

    # Skip to content
    if re.match(r"^(\[)?Skip to", line):
        return True

    # Press Escape
    if line.startswith("Press Escape"):
        return True

    # Privacy / cookie / consent
    if any(p in line for p in ("Do Not Sell", "Personal Information", "Opt Out of Targeted",
                                "Cookie Settings", "Cookie Policy", "Privacy Manager",
                                "Manage Preferences")):
        return True

    # JavaScript links
    if re.match(r"^\[.*\]\(javascript:", line):
        return True

    # Horizontal rules
    if line in ("* * *", "---", "___"):
        return True

    # reCAPTCHA
    if "reCAPTCHA" in line or "recaptcha" in line:
        return True

    # Copyright
    if re.match(r"^(©|Copyright)\s", line):
        return True

    # Recommendation links: [## Title](url) or [### Title](url)
    if re.match(r"^\[##?\s+.+\]\([^)]+\)$", line):
        return True
    # Recommendation links with prefix: "[ ### Title](url)"
    if re.match(r"^\[\s*###?\s+.+\]\([^)]+\)$", line):
        return True

    # Short tag/topic links: [Iran](url) — single or multiple concatenated
    if re.match(r"^\[[^\]]{1,25}\]\(https?://[^)]+\)$", line):
        return True
    # Multiple tag links on one line: [Tag1](url)[Tag2](url)
    if re.match(r"^(\[[^\]]{1,30}\]\([^)]+\))+$", line):
        return True

    # Social share buttons: "email (opens in new window)"
    if "(opens in new window)" in line:
        return True

    # "Add X as your preferred source"
    if "as your preferred source" in line:
        return True

    # "ALSO READ:" promotional links
    if line.startswith("**ALSO READ:**") or line.startswith("ALSO READ:"):
        return True

    # Subscription confirmations
    if line.startswith("You will now") or line.startswith("You are already"):
        return True

    # Template / tracking code
    if re.match(r"^\s*\{\{.*\}\}\s*$", line):
        return True
    if re.match(r"^#[a-z_]+", line) and len(line) < 40:
        return True

    # Checkbox UI elements (cookie toggles)
    if re.match(r"^- \[[x ]\] (On|Off)$", line):
        return True

    # Photo credit lines: "Photo: Name/Agency" or "Image: Name"
    if re.match(r"^(Photo|Image|Credit|Illustration)\s*:", line):
        return True

    # Lines that are just punctuation or whitespace
    if re.match(r"^[\s*_\-=]+$", line) and len(line) < 10:
        return True

    return False


def clean_rss_content(entry: dict) -> str:
    """Extract the best available content from an RSS entry."""
    # Try content fields in priority order
    for field in ["content", "content:encoded", "description", "summary"]:
        if field == "content" and hasattr(entry, "content"):
            # feedparser stores content as a list
            if entry.content:
                raw = entry.content[0].get("value", "")
                if raw:
                    return strip_html(raw)
        value = entry.get(field, "")
        if value:
            return strip_html(value)
    return ""


def strip_html(html: str) -> str:
    """Strip HTML tags and clean up text."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    text = unescape(text)
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- File Operations ---

def slugify(text: str, max_length: int = 60) -> str:
    """Create a filesystem-safe slug from text."""
    # Remove non-ASCII characters for the slug
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:max_length]


def url_hash(url: str) -> str:
    """Short hash of URL for deduplication."""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def get_existing_urls(content_dir: Path) -> set[str]:
    """Scan existing markdown files for their source_url to deduplicate."""
    urls = set()
    if not content_dir.exists():
        return urls
    for f in content_dir.glob("**/*.md"):
        if f.name.startswith("_") or f.name == "newsletter.md":
            continue
        try:
            text = f.read_text(encoding="utf-8")
            match = re.search(r'^source_url:\s*["\']?(.+?)["\']?\s*$', text, re.MULTILINE)
            if match:
                urls.add(match.group(1).strip())
        except Exception:
            pass
    return urls


def check_content_quality(content: str) -> str | None:
    """Check if scraped content is sufficient. Returns skip reason or None if OK."""
    if len(content) < 500:
        return f"too short ({len(content)} chars)"
    if content.rstrip().endswith("…"):
        return "truncated"
    if "Target URL returned error" in content or "403: Forbidden" in content:
        return "HTTP error"
    if "requiring CAPTCHA" in content:
        return "CAPTCHA"
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    long_lines = [l for l in lines if len(l) > 80
                  and not l.startswith(("#", "[", "!", "*"))]
    if len(long_lines) < 3:
        return f"thin ({len(long_lines)} paragraphs)"
    return None


def save_article(content_dir: Path, title: str, source: str, url: str,
                 content: str, pub_date: str) -> tuple[Path, bool]:
    """Save an article as a markdown file. Returns (path, is_good).
    Auto-sets status to 'skipped' if content quality is insufficient.
    Saves directly into inbox/ or skipped/ subdirectory."""
    # Quality check
    skip_reason = check_content_quality(content)
    status = "skipped" if skip_reason else "inbox"

    # Save directly to the correct status subdirectory
    target_dir = content_dir / status
    target_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(title) or url_hash(url)
    filename = f"{slug}.md"
    filepath = target_dir / filename

    # Avoid filename collisions
    counter = 1
    while filepath.exists():
        filepath = target_dir / f"{slug}-{counter}.md"
        counter += 1

    # Escape quotes in title for YAML
    safe_title = title.replace('"', '\\"')

    md = f'''---
title: "{safe_title}"
ai_title: ""
source: "{source}"
source_url: "{url}"
date: {pub_date}
status: {status}
importance: 0
category: ""
share: false
share_score: 0
ghost_access: "paid"
published: []
---

## 中文摘要



## 社交文案



## Original Content

{content}
'''
    filepath.write_text(md, encoding="utf-8")
    return filepath, skip_reason is None


# --- Main Pipeline ---

def fetch_feed(source: dict, existing_urls: set, content_dir: Path,
               target_date: date, scrape_timeout: int) -> tuple[int, int]:
    """Fetch and process a single RSS feed. Returns (good_count, skipped_count)."""
    name = source["name"]
    url = source["url"]
    is_aggregator = source.get("type") == "aggregator"

    print(f"\n📡 Fetching: {name} ({url})")

    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"  ✗ Failed to parse feed: {e}")
        return 0, 0

    if not feed.entries:
        print(f"  ⚠ No entries found")
        return 0, 0

    print(f"  Found {len(feed.entries)} entries")
    good_count = 0
    skip_count = 0
    max_articles = source.get("max_articles", 20)

    for entry in feed.entries[:max_articles]:
        entry_title = entry.get("title", "Untitled")

        if is_aggregator:
            # Extract actual article URLs from aggregator description
            description = entry.get("description", "") or entry.get("summary", "")
            article_urls = extract_aggregator_urls(description)
            if article_urls:
                # Process the first (primary) article URL
                article_url = article_urls[0]
                article_source = get_source_from_url(article_url)
            else:
                # Fallback: use entry link directly (Claude will trace source during translation)
                article_url = entry.get("link", "")
                article_source = name
                if not article_url:
                    continue
        else:
            article_url = entry.get("link", "")
            article_source = name
            if not article_url:
                continue

        # Deduplicate
        if article_url in existing_urls:
            continue

        # Parse publication date
        pub_date_str = target_date.isoformat()
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                pub_date_str = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass

        # Scrape full content
        print(f"  → Scraping: {entry_title[:60]}...")
        content = scrape_with_jina(article_url, timeout=scrape_timeout)

        if not content:
            # Fall back to RSS description
            content = clean_rss_content(entry)
            if content:
                print(f"    ↳ Using RSS description (Jina failed)")
            else:
                print(f"    ✗ No content available, skipping")
                continue

        # Save article
        filepath, is_good = save_article(
            content_dir=content_dir,
            title=entry_title,
            source=article_source,
            url=article_url,
            content=content,
            pub_date=pub_date_str,
        )
        existing_urls.add(article_url)
        if is_good:
            good_count += 1
            print(f"    ✓ Saved: {filepath.name}")
        else:
            skip_count += 1
            print(f"    ⊘ Skipped (insufficient content): {filepath.name}")

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    return good_count, skip_count


def detect_target_date(config: dict) -> date:
    """Auto-detect the target date for fetching.

    If today's newsletter.md already exists (compiled/published),
    target tomorrow instead.
    """
    today = date.today()
    today_dir = get_content_dir(config, today)
    if (today_dir / "newsletter.md").exists():
        tomorrow = today + timedelta(days=1)
        print(f"  ℹ {today.isoformat()} already has newsletter.md → targeting {tomorrow.isoformat()}")
        return tomorrow
    return today


def main():
    parser = argparse.ArgumentParser(description="Fetch RSS feeds for 美轮美换 Newsletter")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date (YYYY-MM-DD), defaults to auto-detect")
    args = parser.parse_args()

    config = load_config()

    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        target_date = detect_target_date(config)
    content_dir = get_content_dir(config, target_date)
    content_dir.mkdir(parents=True, exist_ok=True)
    scrape_timeout = config.get("scrape_timeout", 30)

    print(f"📰 美轮美换 Newsletter Fetcher")
    print(f"   Date: {target_date.isoformat()}")
    print(f"   Output: {content_dir}")

    existing_urls = get_existing_urls(content_dir)
    if existing_urls:
        print(f"   Existing articles: {len(existing_urls)} (will skip)")

    enabled_sources = [s for s in config["sources"] if s.get("enabled", True)]
    print(f"   Sources: {len(enabled_sources)} enabled\n")

    total_good = 0
    total_skipped = 0
    for source in enabled_sources:
        good, skipped = fetch_feed(source, existing_urls, content_dir, target_date, scrape_timeout)
        total_good += good
        total_skipped += skipped

    print(f"\n{'='*50}")
    print(f"✅ Done! Fetched {total_good} new articles ({total_skipped} skipped) for {target_date.isoformat()}")
    print(f"   Directory: {content_dir}")


if __name__ == "__main__":
    main()
