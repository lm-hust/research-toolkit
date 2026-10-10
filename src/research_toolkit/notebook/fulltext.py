"""
src/research_toolkit/notebook/fulltext.py
What a Zotero item's resolved full text is sent to Gemini Notebook as.

`ZoteroManager.list_fulltext_items` picks the file (first PDF, else EPUB, else HTML snapshot).
`upload_kind` decides the upload kind ("url" only when the caller allows it) and
`upload_target` yields what the sources API is given: a file path for `add_file`
(an HTML snapshot becomes a temporary markdown file, since notebooklm-py refuses HTML uploads),
or the DOI/URL for `add_url`.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from markdownify import markdownify  # type: ignore[import-untyped]

from research_toolkit.zotero.models import ZoteroItem

URL_KIND = "url"


def upload_kind(item: ZoteroItem, allow_url: bool = False) -> Optional[str]:
    """"pdf" | "epub" | "html" | "url", or None when the item has no usable full text."""
    if item.fulltext_kind and item.fulltext_path:
        return item.fulltext_kind
    if allow_url and item.doi_url:
        return URL_KIND
    return None


@contextmanager
def upload_target(item: ZoteroItem, kind: str) -> Iterator[str]:
    """Yields the file path (or, for "url", the URL) to upload; valid inside the block only."""
    if kind == URL_KIND:
        assert item.doi_url
        yield item.doi_url
        return
    assert item.fulltext_path
    if kind != "html":
        yield item.fulltext_path
        return
    with tempfile.TemporaryDirectory(prefix="rt-snapshot-") as tmp:
        md_path = Path(tmp) / f"{item.key}.md"
        md_path.write_text(html_to_markdown(Path(item.fulltext_path)), encoding="utf-8")
        yield str(md_path)


def html_to_markdown(html_path: Path) -> str:
    html = html_path.read_bytes().decode("utf-8", errors="replace")
    return str(markdownify(html, heading_style="ATX")).strip() + "\n"
