# plugins/my_rename_rule.py
# FileVault Plugin Example — custom rename rule
# Drop this file in your plugins/ folder and set plugin_dir in config.

from pathlib import Path
from typing import Optional

# Which extensions this plugin handles. Use ["*"] for all.
EXTENSIONS = [".pdf", ".epub"]

def rename(fp: Path, meta: dict) -> Optional[str]:
    """
    Return new filename (with extension) or None to skip.
    meta keys: title, author, date, camera, gps
    """
    title  = meta.get("title","").strip()
    author = meta.get("author","").strip()
    # Example: prefix with [READ] tag
    if title and author:
        return f"[READ] {author} — {title}{fp.suffix}"
    return None
