"""
src/research_toolkit/notebook/titles.py
Notebook Source titles carry their Zotero item key: `[<key>] <paper title>`.
"""

from __future__ import annotations

import re
from typing import Optional

_KEY_PREFIX = re.compile(r"^\[([A-Za-z0-9]+)\]")


def source_title(item_key: str, paper_title: str) -> str:
    return f"[{item_key}] {paper_title.strip()}"


def source_key(title: Optional[str]) -> Optional[str]:
    """Returns the Zotero key from a `[key]`-prefixed source title, else None."""
    match = _KEY_PREFIX.match(title or "")
    return match.group(1) if match else None
