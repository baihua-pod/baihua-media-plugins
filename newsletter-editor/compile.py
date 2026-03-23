#!/usr/bin/env python3
"""Compile approved articles into newsletter.md.

Usage:
    python3 skills/newsletter-editor/compile.py              # today
    python3 skills/newsletter-editor/compile.py --date 2026-03-22
    python3 skills/newsletter-editor/compile.py --dry-run    # preview without writing
"""

import argparse
import re
from datetime import date
from pathlib import Path

import yaml

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent
CONTENT_BASE = VAULT_ROOT / "📚 Areas/Work/Baihua Media/The American Roulette/每日新闻通讯"

# Category display order — update when adding/removing temporary categories
CATEGORY_ORDER = [
    "伊朗战争",
    "行政与特朗普",
    "国会与立法",
    "司法与法律",
    "财经与特朗普关税",
    "民生与经济",
    "国际",
    "民主党",
    "媒体与文化",
    "地方",
    "其它",
]


def parse_article(filepath: Path) -> dict | None:
    """Parse frontmatter and 中文摘要 from an article file."""
    content = filepath.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
    except Exception:
        return None

    if fm.get("status") != "approved":
        return None

    # Extract 中文摘要
    body = m.group(2)
    summary_match = re.search(r"## 中文摘要\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else ""

    if not summary or not fm.get("ai_title"):
        return None

    return {
        "ai_title": fm.get("ai_title", ""),
        "category": fm.get("category", "其它"),
        "importance": fm.get("importance", 0),
        "source": fm.get("source", ""),
        "source_url": fm.get("source_url", ""),
        "ghost_access": fm.get("ghost_access", "paid"),
        "summary": summary,
        "filename": filepath.name,
    }


def format_entry(article: dict) -> str:
    """Format a single article entry for the newsletter."""
    source = article["source"]
    source_url = article["source_url"]
    if source_url:
        source_str = f"[{source}]({source_url})"
    else:
        source_str = source
    return f"- **{article['ai_title']}**：{article['summary']}（{source_str}）"


def compile_newsletter(target_date: date, dry_run: bool = False) -> None:
    day_dir = CONTENT_BASE / target_date.isoformat()
    approved_dir = day_dir / "approved"

    if not approved_dir.exists():
        print(f"❌ No approved/ directory found: {approved_dir}")
        return

    # Parse all approved articles
    articles = []
    for f in sorted(approved_dir.iterdir()):
        if f.suffix != ".md":
            continue
        article = parse_article(f)
        if article:
            articles.append(article)

    if not articles:
        print("❌ No approved articles with content found.")
        return

    # Group by category
    grouped: dict[str, list[dict]] = {}
    for article in articles:
        cat = article["category"]
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(article)

    # Sort within each category by importance descending
    for cat in grouped:
        grouped[cat].sort(key=lambda a: a["importance"], reverse=True)

    # Count free vs paid
    total = len(articles)
    free_count = sum(1 for a in articles if a["ghost_access"] == "free")
    paid_count = total - free_count

    # Format date for header
    date_str = f"{target_date.year}年{target_date.month}月{target_date.day}日"

    # Build newsletter
    lines = [
        "---",
        f'title: "美轮美换每日新闻通讯 {target_date.isoformat()}"',
        f"date: {target_date.isoformat()}",
        "---",
        "",
        f"# 美轮美换 | {date_str}",
        "",
        f"> 今日共 {total} 篇 | 免费 {free_count} 篇 · 付费 {paid_count} 篇",
        "",
    ]

    # Ordered categories
    ordered_cats = [c for c in CATEGORY_ORDER if c in grouped]
    # Any categories not in CATEGORY_ORDER go at the end
    extra_cats = [c for c in grouped if c not in CATEGORY_ORDER]
    ordered_cats.extend(sorted(extra_cats))

    for cat in ordered_cats:
        lines.append("")
        lines.append(f"## {cat}")
        lines.append("")
        for article in grouped[cat]:
            lines.append(format_entry(article))
            lines.append("")

    output = "\n".join(lines)

    if dry_run:
        print(output)
        print(f"\n{'='*50}")
        print(f"📋 Preview: {total} articles ({free_count} free, {paid_count} paid)")
        print(f"   Categories: {len(ordered_cats)}")
        return

    # Write newsletter.md
    newsletter_path = day_dir / "newsletter.md"
    newsletter_path.write_text(output, encoding="utf-8")
    print(f"✅ Compiled newsletter.md: {total} articles ({free_count} free, {paid_count} paid)")
    print(f"   Categories: {', '.join(ordered_cats)}")
    print(f"   Output: {newsletter_path}")


def main():
    parser = argparse.ArgumentParser(description="Compile approved articles into newsletter.md")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview output without writing file.")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    compile_newsletter(target_date, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
