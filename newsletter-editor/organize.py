#!/usr/bin/env python3
"""Organize articles into subfolders by frontmatter status.

Usage:
    python3 skills/newsletter-editor/organize.py              # today
    python3 skills/newsletter-editor/organize.py --date 2026-03-21

Run after changing article statuses in Obsidian to move files into
draft/, approved/, or skipped/ subfolders.
"""

import argparse
import os
import re
import shutil
from datetime import date
from pathlib import Path

import yaml

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent
CONTENT_BASE = VAULT_ROOT / "📚 Areas/Work/Baihua Media/The American Roulette/每日新闻通讯"
STATUS_FOLDERS = {"draft", "approved", "skipped", "inbox"}
SKIP_FILES = {"review.md", "newsletter.md"}


def get_status(filepath: Path) -> str | None:
    content = filepath.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
        return fm.get("status")
    except Exception:
        return None


def organize(target_date: date) -> None:
    day_dir = CONTENT_BASE / target_date.isoformat()
    if not day_dir.exists():
        print(f"❌ Directory not found: {day_dir}")
        return

    # Ensure subfolders exist
    for folder in STATUS_FOLDERS:
        (day_dir / folder).mkdir(exist_ok=True)

    moved = []

    # Scan root + all status subfolders
    search_dirs = [day_dir] + [day_dir / f for f in STATUS_FOLDERS]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for f in search_dir.iterdir():
            if f.suffix != ".md" or f.name in SKIP_FILES or f.is_dir():
                continue

            status = get_status(f)
            if status not in STATUS_FOLDERS:
                continue

            target_dir = day_dir / status
            if f.parent.resolve() == target_dir.resolve():
                continue

            shutil.move(str(f), str(target_dir / f.name))
            old_loc = f.parent.name if f.parent != day_dir else "root"
            moved.append((f.name, old_loc, status))

    if moved:
        print(f"✅ Moved {len(moved)} files:")
        for name, old, new in moved:
            print(f"  {name}: {old}/ → {new}/")
    else:
        print("✅ All files already in correct folders.")

    # Print summary
    for folder in sorted(STATUS_FOLDERS):
        folder_path = day_dir / folder
        if folder_path.exists():
            count = sum(1 for f in folder_path.iterdir() if f.suffix == ".md")
            if count:
                print(f"  {folder}/: {count} files")


def main():
    parser = argparse.ArgumentParser(description="Organize articles by status")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date (YYYY-MM-DD). Defaults to today.")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    organize(target_date)


if __name__ == "__main__":
    main()
