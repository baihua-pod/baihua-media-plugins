#!/usr/bin/env python3
"""Add ## Related backlink to all article files linking back to their date's newsletter."""

import re
from pathlib import Path

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent
CONTENT_BASE = VAULT_ROOT / "📚 Areas/Work/Baihua Media/The American Roulette/每日新闻通讯"
STATUS_FOLDERS = {"draft", "approved", "skipped", "inbox"}

updated = 0
skipped = 0

for date_dir in sorted(CONTENT_BASE.iterdir()):
    if not date_dir.is_dir():
        continue
    date_str = date_dir.name  # e.g. 2026-03-22
    
    # Parse date for display
    try:
        month = int(date_str.split("-")[1])
        day = int(date_str.split("-")[2])
        date_label = f"{month}月{day}日"
    except (IndexError, ValueError):
        continue
    
    # Wikilink back to the date's newsletter
    backlink = f"[[每日新闻通讯/{date_str}/newsletter|{date_label}]]"
    related_section = f"\n\n## Related\n\n- {backlink}\n"
    
    for status_folder in STATUS_FOLDERS:
        folder = date_dir / status_folder
        if not folder.exists():
            continue
        for f in sorted(folder.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            
            # Skip if already has Related section
            if "## Related" in content:
                skipped += 1
                continue
            
            # Append Related section
            # Strip trailing whitespace/newlines, then add section
            content = content.rstrip() + related_section
            f.write_text(content, encoding="utf-8")
            updated += 1

print(f"✅ Updated {updated} files with backlinks")
print(f"⏭️  Skipped {skipped} files (already had ## Related)")
