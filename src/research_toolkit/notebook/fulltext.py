"""
src/research_toolkit/notebook/fulltext.py
How a Zotero item's resolved full text becomes a Notebook Source.

`ZoteroManager.list_fulltext_items` picks the file (first PDF, else EPUB, else HTML snapshot).
This module decides the upload kind (adding "url" when the caller allows it) and performs the
matching notebooklm-py call, always titling the source `title`.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from markdownify import markdownify  # type: ignore[import-untyped]
from notebooklm import Source

from research_toolkit.notebook.client import NotebookClient
from research_toolkit.zotero.models import ZoteroItem


def upload_kind(item: ZoteroItem, allow_url: bool = False) -> Optional[str]:
    """"pdf" | "epub" | "html" | "url", or None when the item has no usable full text."""
    if item.fulltext_kind and item.fulltext_path:
        return item.fulltext_kind
    if allow_url and item.doi_url:
        return "url"
    return None


async def add_fulltext_source(
    client: NotebookClient, notebook_id: str, item: ZoteroItem, kind: str, title: str
) -> Source:
    """Adds the item's full text (as `upload_kind` chose) as one source titled `title`."""
    if kind == "url":
        assert item.doi_url
        return await client.sources.add_url(notebook_id, item.doi_url, title=title)
    assert item.fulltext_path
    if kind == "html":
        # notebooklm-py refuses HTML uploads; send the snapshot as markdown instead.
        with tempfile.TemporaryDirectory(prefix="rt-snapshot-") as tmp:
            md_path = Path(tmp) / f"{item.key}.md"
            md_path.write_text(html_to_markdown(Path(item.fulltext_path)), encoding="utf-8")
            return await client.sources.add_file(notebook_id, md_path, title=title)
    return await client.sources.add_file(notebook_id, item.fulltext_path, title=title)


def html_to_markdown(html_path: Path) -> str:
    html = html_path.read_bytes().decode("utf-8", errors="replace")
    return str(markdownify(html, heading_style="ATX")).strip() + "\n"
