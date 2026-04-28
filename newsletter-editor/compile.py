#!/usr/bin/env python3
"""Compile approved articles into newsletter.md.

Usage:
    python3 skills/newsletter-editor/compile.py              # today
    python3 skills/newsletter-editor/compile.py --date 2026-03-22
    python3 skills/newsletter-editor/compile.py --dates 2026-04-12,2026-04-13  # weekend edition
    python3 skills/newsletter-editor/compile.py --dry-run    # preview without writing
"""

import argparse
import re
from datetime import date
from pathlib import Path

import yaml
from urllib.parse import urlparse

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent
CONTENT_BASE = VAULT_ROOT / "📚 Areas/Work/Baihua Media/The American Roulette/每日新闻通讯"

# Known aggregator domains — source_url should NOT point to these
AGGREGATOR_DOMAINS = {"memeorandum.com", "mediagazer.com", "techmeme.com", "politicalwire.com"}

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

# Normalize non-canonical frontmatter category values to one of CATEGORY_ORDER.
# Accumulated from actual article frontmatter observed in production — add new
# entries here rather than leaving them to fall through to "其它".
# Keys with the same value as the canonical target are no-ops (kept for clarity).
CATEGORY_ALIASES = {
    # → 行政与特朗普
    "政府人事": "行政与特朗普",
    "政府内部分歧": "行政与特朗普",
    "特朗普商业与腐败": "行政与特朗普",
    "特朗普人事": "行政与特朗普",
    # → 司法与法律
    "司法与执法": "司法与法律",
    "法律界": "司法与法律",
    # → 财经与特朗普关税
    "能源与经济": "财经与特朗普关税",
    "关税": "财经与特朗普关税",
    "财经": "财经与特朗普关税",
    # → 民生与经济
    "社保与医疗": "民生与经济",
    "科技政策": "民生与经济",
    "移民与公民": "民生与经济",
    "医疗": "民生与经济",
    # → 国际
    "外交与国际": "国际",
    "外交": "国际",
    # → 媒体与文化
    "媒体与新闻自由": "媒体与文化",
    "新闻自由": "媒体与文化",
    # → 地方
    "州政治": "地方",
    # → 其它
    "中期选举": "其它",
    "选举与中期": "其它",
    "选举完整性": "其它",
    "民调与舆情": "其它",
    "民调": "其它",
    "暴力犯罪": "其它",
}


def canonicalize_category(raw: str) -> str:
    """Map a frontmatter category to one of the canonical CATEGORY_ORDER values.

    Unknown non-canonical categories fall through to "其它" rather than
    appearing as their own section at the end of the newsletter. Returns the
    raw value if it's already canonical.
    """
    if not raw:
        return "其它"
    if raw in CATEGORY_ORDER:
        return raw
    if raw in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[raw]
    return "其它"


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

    raw_category = fm.get("category", "其它")
    category = canonicalize_category(raw_category)

    return {
        "ai_title": fm.get("ai_title", ""),
        "category": category,
        "raw_category": raw_category,  # kept for debug output
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

    # Validate: warn and strip link if source_url points to an aggregator
    # but source claims to be an original publication (e.g., source="Politico" + source_url=politicalwire.com)
    if source_url:
        url_domain = urlparse(source_url).netloc.lower().replace("www.", "")
        if any(agg in url_domain for agg in AGGREGATOR_DOMAINS):
            print(f"  ⚠ Aggregator URL detected for '{article['ai_title']}': source={source}, url={source_url}")
            source_url = ""  # Strip the misleading link

    if source_url:
        source_str = f"[{source}]({source_url})"
    else:
        source_str = source
    return f"- **{article['ai_title']}**：{article['summary']}（{source_str}）"


def compile_newsletter(target_date: date, dry_run: bool = False,
                       extra_dates: list[date] | None = None) -> None:
    day_dir = CONTENT_BASE / target_date.isoformat()

    # Collect approved directories from all dates
    all_dates = sorted(set((extra_dates or []) + [target_date]))
    approved_dirs = []
    for d in all_dates:
        adir = CONTENT_BASE / d.isoformat() / "approved"
        if adir.exists():
            approved_dirs.append(adir)

    if not approved_dirs:
        print(f"❌ No approved/ directories found for: {', '.join(d.isoformat() for d in all_dates)}")
        return

    is_multi_day = len(all_dates) > 1

    # Parse all approved articles, dedup by source_url
    articles = []
    seen_urls = set()
    for approved_dir in approved_dirs:
        for f in sorted(approved_dir.iterdir()):
            if f.suffix != ".md":
                continue
            article = parse_article(f)
            if article:
                url = article.get("source_url", "")
                if url and url in seen_urls:
                    print(f"  ⊘ Dedup (same source_url): {article['ai_title']}")
                    continue
                if url:
                    seen_urls.add(url)
                articles.append(article)

    if not articles:
        print("❌ No approved articles with content found.")
        return

    # Report any non-canonical category normalizations
    remapped = [a for a in articles if a.get("raw_category") and a["raw_category"] != a["category"]]
    if remapped:
        print(f"  ↺ Normalized {len(remapped)} non-canonical categories → canonical:")
        aliases_used: dict[str, str] = {}
        for a in remapped:
            aliases_used[a["raw_category"]] = a["category"]
        for src, dst in sorted(aliases_used.items()):
            count = sum(1 for a in remapped if a["raw_category"] == src)
            print(f"     {src} → {dst} ({count})")

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
    if is_multi_day:
        first_d = all_dates[0]
        last_d = all_dates[-1]
        if first_d.month == last_d.month:
            date_str = f"{first_d.month}月{first_d.day}-{last_d.day}日周末版"
        else:
            date_str = f"{first_d.month}月{first_d.day}日-{last_d.month}月{last_d.day}日"
        title_dates = f"{first_d.isoformat()} ~ {last_d.isoformat()}"
        count_label = "本期共"
    else:
        date_str = f"{target_date.year}年{target_date.month}月{target_date.day}日"
        title_dates = target_date.isoformat()
        count_label = "今日共"

    # Build newsletter
    lines = [
        "---",
        f'title: "美轮美换每日新闻通讯 {title_dates}"',
        f"date: {target_date.isoformat()}",
        "---",
        "",
        f"# 美轮美换 | {date_str}",
        "",
        f"> {count_label} {total} 篇 | 免费 {free_count} 篇 · 付费 {paid_count} 篇",
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


def parse_newsletter_entry(line: str) -> tuple | None:
    """Parse one bullet line `- **{title}**：{summary}（[A](u1) / [B](u2)）`.

    Returns (ai_title, summary, urls) or None.
    Anchors the trailing source block from the RIGHT to handle 「（...）」
    nested parens inside summary (e.g., 「修整均值」（trimmed averages，剔除...）).
    """
    if not line.startswith("- **"):
        return None
    m_title = re.match(r"^- \*\*(.+?)\*\*：", line)
    if not m_title:
        return None
    ai_title = m_title.group(1)
    rest = line[m_title.end():]
    # Trailing source block: 「（[X](url1) [/ [Y](url2)]+...）」at end of line
    m_sources = re.search(
        r"（((?:\[[^\]]+\]\([^)]+\)\s*/?\s*)+)）\s*$",
        rest,
    )
    if not m_sources:
        return None
    summary = rest[:m_sources.start()].strip()
    urls = re.findall(r"\]\((https?://[^)]+)\)", m_sources.group(1))
    return ai_title, summary, urls


def parse_newsletter_entries(newsletter_path: Path) -> dict:
    """Parse newsletter.md → {source_url: {ai_title, summary, n_sources, all_urls}}."""
    if not newsletter_path.exists():
        return {}
    entries = {}
    for line in newsletter_path.read_text(encoding="utf-8").splitlines():
        parsed = parse_newsletter_entry(line)
        if not parsed:
            continue
        ai_title, summary, urls = parsed
        if not urls:
            continue
        for url in urls:
            entries[url] = {
                "ai_title": ai_title,
                "summary": summary,
                "n_sources": len(urls),
                "all_urls": urls,
            }
    return entries


def apply_writeback(filepath: Path, new_title: str, new_summary: str, learn_date: date) -> None:
    """Rewrite ai_title + 中文摘要 section in source approved/*.md, mark learned_from_edit."""
    text = filepath.read_text(encoding="utf-8")
    m = re.match(r"^(---\n)(.*?)(\n---\n)(.*)", text, re.DOTALL)
    if not m:
        return
    fm_open, fm_body, fm_close, body = m.groups()

    # Update ai_title (preserve double-quote style; escape any " in title)
    safe_title = new_title.replace('"', '\\"')
    fm_body, n_title = re.subn(
        r'^ai_title:\s*.*$',
        f'ai_title: "{safe_title}"',
        fm_body,
        count=1,
        flags=re.MULTILINE,
    )
    # Add/update learned_from_edit marker
    if re.search(r"^learned_from_edit:\s*", fm_body, re.MULTILINE):
        fm_body = re.sub(
            r"^learned_from_edit:\s*.*$",
            f"learned_from_edit: {learn_date.isoformat()}",
            fm_body,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        fm_body = fm_body.rstrip() + f"\nlearned_from_edit: {learn_date.isoformat()}"

    # Update 中文摘要 section content (preserve heading + trailing structure)
    body = re.sub(
        r"(## 中文摘要[ \t]*\n)(.*?)(?=\n## |\Z)",
        lambda x: f"{x.group(1)}\n{new_summary}\n",
        body,
        count=1,
        flags=re.DOTALL,
    )

    filepath.write_text(fm_open + fm_body + fm_close + body, encoding="utf-8")


def learn_from_newsletter(target_date: date, apply: bool = False) -> None:
    """Diff newsletter.md against approved/*.md baseline; propagate user edits to source."""
    day_dir = CONTENT_BASE / target_date.isoformat()
    newsletter_path = day_dir / "newsletter.md"
    approved_dir = day_dir / "approved"

    if not newsletter_path.exists():
        print(f"❌ No newsletter.md at {newsletter_path}")
        return
    if not approved_dir.exists():
        print(f"❌ No approved/ at {approved_dir}")
        return

    user_entries = parse_newsletter_entries(newsletter_path)
    if not user_entries:
        print(f"❌ Could not parse any entries from {newsletter_path}")
        return
    print(f"📰 Parsed {len(user_entries)} source URLs from newsletter.md")

    written = 0
    multi_source = 0
    unchanged = 0
    no_match = 0
    not_in_newsletter = 0

    for f in sorted(approved_dir.glob("*.md")):
        article = parse_article(f)
        if not article:
            continue
        url = article["source_url"]
        if not url:
            no_match += 1
            continue
        if url not in user_entries:
            not_in_newsletter += 1
            continue
        user_v = user_entries[url]
        if user_v["n_sources"] > 1:
            multi_source += 1
            print(f"  ⊘ multi-source merge skip: {f.name} (sources: {len(user_v['all_urls'])})")
            continue
        title_changed = user_v["ai_title"] != article["ai_title"]
        summary_changed = user_v["summary"] != article["summary"]
        if not (title_changed or summary_changed):
            unchanged += 1
            continue
        # Show diff
        print(f"  ✎ {f.name}")
        if title_changed:
            print(f"      title:  {article['ai_title']!r}")
            print(f"        →    {user_v['ai_title']!r}")
        if summary_changed:
            old_s = article["summary"][:120].replace("\n", " ")
            new_s = user_v["summary"][:120].replace("\n", " ")
            old_n = len(article["summary"])
            new_n = len(user_v["summary"])
            print(f"      summary ({old_n} → {new_n} chars):")
            print(f"        old: {old_s}{'...' if old_n > 120 else ''}")
            print(f"        new: {new_s}{'...' if new_n > 120 else ''}")
        if apply:
            apply_writeback(f, user_v["ai_title"], user_v["summary"], target_date)
            written += 1

    print()
    if apply:
        print(f"✅ Wrote back {written} files (with learned_from_edit: {target_date.isoformat()})")
    else:
        candidates = len([1 for f in sorted(approved_dir.glob("*.md"))
                          if (a := parse_article(f)) and a.get("source_url") in user_entries
                          and user_entries[a["source_url"]]["n_sources"] == 1
                          and (user_entries[a["source_url"]]["ai_title"] != a["ai_title"]
                               or user_entries[a["source_url"]]["summary"] != a["summary"])])
        print(f"🔍 Dry-run: {candidates} files would be rewritten. Pass --apply to commit.")
    print(f"   Multi-source merge skipped: {multi_source}")
    print(f"   Unchanged: {unchanged}")
    print(f"   No source URL in article: {no_match}")
    print(f"   Article not in newsletter.md: {not_in_newsletter}")


def main():
    parser = argparse.ArgumentParser(description="Compile approved articles into newsletter.md")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--dates", type=str, default=None,
                        help="Comma-separated dates for multi-day edition (e.g., 2026-04-12,2026-04-13). "
                             "Newsletter.md is written to the last date's folder.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview compile output without writing file.")
    parser.add_argument("--learn", action="store_true",
                        help="Learn from user's edits to newsletter.md: propagate changes back to "
                             "source approved/*.md so future compiles preserve them. Default dry-run.")
    parser.add_argument("--apply", action="store_true",
                        help="With --learn: actually write changes (default is dry-run preview).")
    args = parser.parse_args()

    if args.learn:
        target_date = date.fromisoformat(args.date) if args.date else date.today()
        learn_from_newsletter(target_date, apply=args.apply)
        return

    if args.dates:
        all_dates = [date.fromisoformat(d.strip()) for d in args.dates.split(",")]
        target_date = all_dates[-1]
        extra_dates = all_dates[:-1]
        compile_newsletter(target_date, dry_run=args.dry_run, extra_dates=extra_dates)
    else:
        target_date = date.fromisoformat(args.date) if args.date else date.today()
        compile_newsletter(target_date, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
