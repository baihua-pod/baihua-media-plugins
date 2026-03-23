#!/usr/bin/env python3
"""Generate a review.md overview page for article triage.

Usage:
    python3 skills/newsletter-editor/review.py              # today
    python3 skills/newsletter-editor/review.py --date 2026-03-21

Generates review.md in the day's directory with all draft/approved articles
grouped by category and sorted by importance. Open in Obsidian for fast
triage without opening each article individually.
"""

import argparse
import os
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent
CONTENT_BASE = VAULT_ROOT / "📚 Areas/Work/Baihua Media/The American Roulette/每日新闻通讯"
REVIEW_STATUSES = {"draft"}
SKIP_FILES = {"review.md", "newsletter.md"}

# Category display order (matches compile phase)
CATEGORY_ORDER = [
    "行政与特朗普", "国会与立法", "司法与法律", "财经与特朗普关税",
    "国际", "民主党", "媒体与文化", "地方", "其它",
]


def extract_summary(body: str) -> str:
    m = re.search(r"## 中文摘要\s*\n\s*\n(.*?)(?=\n\s*\n##|\Z)", body, re.DOTALL)
    return m.group(1).strip() if m else ""


def generate_review(target_date: date) -> None:
    day_dir = CONTENT_BASE / target_date.isoformat()
    if not day_dir.exists():
        print(f"❌ Directory not found: {day_dir}")
        return

    articles = []

    # Scan root + status subfolders
    search_dirs = [day_dir] + [day_dir / s for s in REVIEW_STATUSES]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for f in search_dir.iterdir():
            if f.suffix != ".md" or f.name in SKIP_FILES or f.is_dir():
                continue
            content = f.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
            if not m:
                continue
            try:
                fm = yaml.safe_load(m.group(1))
            except Exception:
                continue
            status = fm.get("status", "")
            if status not in REVIEW_STATUSES:
                continue

            # Determine link path (relative to day_dir)
            if f.parent == day_dir:
                link_path = f.stem
            else:
                link_path = f"{f.parent.name}/{f.stem}"

            articles.append({
                "link_path": link_path,
                "status": status,
                "ai_title": fm.get("ai_title", f.stem),
                "importance": fm.get("importance", 5),
                "category": fm.get("category", "其它"),
                "share": fm.get("share", False),
                "source": fm.get("source", ""),
                "summary": extract_summary(m.group(2)),
            })

    if not articles:
        print("No draft/approved articles found.")
        return

    # Group by category
    by_cat = defaultdict(list)
    for a in articles:
        by_cat[a["category"]].append(a)

    # Sort categories: follow CATEGORY_ORDER, then alphabetical for unknowns
    def cat_sort_key(cat):
        try:
            return CATEGORY_ORDER.index(cat)
        except ValueError:
            return len(CATEGORY_ORDER)

    cat_order = sorted(by_cat.keys(), key=cat_sort_key)

    # Build markdown
    lines = [
        f"# {target_date.isoformat()} 文章审核总览",
        "",
        f"共 **{len(articles)}** 篇待审核文章，按类别和重要性排列。",
        "",
        "审核方式：通读摘要，将 status 改为 `approved`（发布）或 `skipped`（跳过），",
        "然后运行 `python3 skills/newsletter-editor/organize.py` 自动归类文件夹。",
        "",
    ]

    for cat in cat_order:
        cat_articles = sorted(by_cat[cat], key=lambda a: -a["importance"])
        lines.append(f"## {cat}（{len(cat_articles)}篇）")
        lines.append("")
        for a in cat_articles:
            share_tag = " 📤" if a["share"] else ""
            lines.append(f"### ⭐{a['importance']} | {a['ai_title']}{share_tag}")
            lines.append(f"> 来源：{a['source']} · [[{a['link_path']}|原文]]")
            lines.append("")
            lines.append(a["summary"])
            lines.append("")
        lines.append("---")
        lines.append("")

    out_path = day_dir / "review.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Generated {out_path.name}: {len(articles)} articles, {len(cat_order)} categories")


def main():
    parser = argparse.ArgumentParser(description="Generate review overview page")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date (YYYY-MM-DD). Defaults to today.")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    generate_review(target_date)


if __name__ == "__main__":
    main()
