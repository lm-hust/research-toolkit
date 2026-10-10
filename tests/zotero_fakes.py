"""
tests/zotero_fakes.py
Fake Zotero data one level below ZoteroManager: a ZoteroClient whose listing calls are served
from memory, plus a temporary storage dir holding the attachment files.

Usage:
    lib = FakeZoteroLibrary(tmp_dir)
    col = lib.add_collection("intelligence-per-kwh")
    sub = lib.add_collection("pue", parent=col)          # subcollection, for --recursive
    lib.add_paper(col, "K1", "Paper one", pdf=True)
    with patch("research_toolkit.cli.ZoteroManager", lib.manager):
        ...

Writes are recorded, not sent: `created_notes` (knob `note_errors = {parent key: exc}`) and
`item_tags = {item key: [tag dicts]}` (arrange existing tags there; knob `tag_errors`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from research_toolkit.zotero.client import ZoteroClient
from research_toolkit.zotero.manager import ZoteroManager
from research_toolkit.zotero.models import ZoteroCollection


class FakeZoteroLibrary(ZoteroClient):
    def __init__(self, storage_dir: Path) -> None:
        super().__init__(api_key="fake", user_id="1")
        self.storage_dir = storage_dir
        self.collections: Dict[str, ZoteroCollection] = {}
        self.rows: Dict[str, List[Dict[str, Any]]] = {}
        self.created_notes: List[Dict[str, Any]] = []
        self.note_errors: Dict[str, Exception] = {}
        self.item_tags: Dict[str, List[Dict[str, Any]]] = {}
        self.tag_errors: Dict[str, Exception] = {}

    def _request(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"unexpected Zotero HTTP call: {args} {kwargs}")

    # --- arrange helpers -------------------------------------------------
    def add_collection(
        self, name: str, key: Optional[str] = None, parent: Optional[str] = None
    ) -> str:
        key = key or f"COL{len(self.collections):05d}"
        self.collections[key] = ZoteroCollection(
            key=key, name=name, parent_collection=parent, user_id=self.user_id
        )
        self.rows[key] = []
        return key

    def add_paper(
        self,
        collection_key: str,
        key: str,
        title: str,
        pdf: bool = True,
        doi: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        data: Dict[str, Any] = {"itemType": "journalArticle", "title": title}
        if doi:
            data["DOI"] = doi
        if url:
            data["url"] = url
        self.rows[collection_key].append({"key": key, "data": data})
        if pdf:
            self.add_pdf(collection_key, key, f"{title[:20]}.pdf")

    def add_attachment(
        self,
        collection_key: str,
        parent_key: str,
        content_type: str,
        filename: Optional[str],
        content: bytes = b"",
        link_mode: str = "imported_file",
    ) -> str:
        """Adds a child attachment row; with a filename, its file lands in storage/<att key>/."""
        rows = self.rows[collection_key]
        att = f"A{parent_key}{sum(1 for r in rows if r['data'].get('parentItem') == parent_key)}"
        data: Dict[str, Any] = {
            "itemType": "attachment",
            "parentItem": parent_key,
            "contentType": content_type,
            "linkMode": link_mode,
        }
        if filename:
            data["filename"] = filename
            (self.storage_dir / att).mkdir(parents=True, exist_ok=True)
            (self.storage_dir / att / filename).write_bytes(content)
        rows.append({"key": att, "data": data})
        return att

    def add_pdf(self, collection_key: str, parent_key: str, filename: str = "paper.pdf") -> str:
        return self.add_attachment(
            collection_key, parent_key, "application/pdf", filename, b"%PDF-1.4 fake"
        )

    def add_epub(self, collection_key: str, parent_key: str, filename: str = "book.epub") -> str:
        return self.add_attachment(
            collection_key, parent_key, "application/epub+zip", filename, b"PK fake epub"
        )

    def add_html_snapshot(
        self, collection_key: str, parent_key: str, html: str, filename: str = "snapshot.html"
    ) -> str:
        """A Zotero web snapshot (`imported_url`, text/html) stored on disk."""
        return self.add_attachment(
            collection_key, parent_key, "text/html", filename, html.encode(), "imported_url"
        )

    def add_link(self, collection_key: str, parent_key: str) -> str:
        """A linked URL attachment: no file anywhere."""
        return self.add_attachment(collection_key, parent_key, "text/html", None, link_mode="linked_url")

    def add_child_note(self, collection_key: str, parent_key: str, note_key: str) -> None:
        self.rows[collection_key].append(
            {"key": note_key, "data": {"itemType": "note", "parentItem": parent_key, "note": "<p>x</p>"}}
        )

    # --- ZoteroClient surface used by the code under test ----------------
    def get_collection(self, key_or_name: str) -> Optional[ZoteroCollection]:
        for col in self.collections.values():
            if col.key == key_or_name or col.name.lower() == key_or_name.lower():
                return col
        return None

    def get_subcollections(self, collection_key: str) -> List[ZoteroCollection]:
        return [c for c in self.collections.values() if c.parent_collection == collection_key]

    def get_collection_items(self, collection_key: str, limit: int = 100) -> List[Dict[str, Any]]:
        return list(self.rows[collection_key])

    def download_item_file(self, item_key: str, dest_path: Path) -> Optional[Path]:
        return None

    def create_child_note(self, parent_key: str, note_html: str, tags: List[str]) -> str:
        """Records the note in `created_notes`; `note_errors[parent_key]` makes it raise."""
        if parent_key in self.note_errors:
            raise self.note_errors[parent_key]
        key = f"N{len(self.created_notes):07d}"
        self.created_notes.append({"key": key, "parentItem": parent_key, "note": note_html, "tags": list(tags)})
        return key

    def replace_tags_with_prefix(self, item_key: str, prefix: str, new_tags: List[str]) -> None:
        """Rewrites `item_tags[item_key]`; `tag_errors[item_key]` makes it raise."""
        if item_key in self.tag_errors:
            raise self.tag_errors[item_key]
        kept = [t for t in self.item_tags.get(item_key, []) if not t["tag"].startswith(prefix)]
        self.item_tags[item_key] = kept + [{"tag": t} for t in new_tags]

    def manager(self) -> ZoteroManager:
        return ZoteroManager(client=self, storage_dir=self.storage_dir)
