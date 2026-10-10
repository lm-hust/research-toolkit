"""
tests/zotero_fakes.py
Fake Zotero data one level below ZoteroManager: a ZoteroClient whose listing calls are served
from memory, plus a temporary storage dir holding the attachment files.

Usage:
    lib = FakeZoteroLibrary(tmp_dir)
    col = lib.add_collection("intelligence-per-kwh")
    lib.add_paper(col, "K1", "Paper one", pdf=True)
    with patch("research_toolkit.cli.ZoteroManager", lib.manager):
        ...

Writes are recorded, not sent: `created_notes` (knob `note_errors = {parent key: exc}`).
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

    def _request(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"unexpected Zotero HTTP call: {args} {kwargs}")

    # --- arrange helpers -------------------------------------------------
    def add_collection(self, name: str, key: Optional[str] = None) -> str:
        key = key or f"COL{len(self.collections):05d}"
        self.collections[key] = ZoteroCollection(key=key, name=name, user_id=self.user_id)
        self.rows[key] = []
        return key

    def add_paper(self, collection_key: str, key: str, title: str, pdf: bool = True) -> None:
        rows = self.rows[collection_key]
        rows.append({"key": key, "data": {"itemType": "journalArticle", "title": title}})
        if pdf:
            att = f"A{key}"
            (self.storage_dir / att).mkdir(parents=True, exist_ok=True)
            (self.storage_dir / att / f"{title[:20]}.pdf").write_bytes(b"%PDF-1.4 fake")
            rows.append(
                {
                    "key": att,
                    "data": {
                        "itemType": "attachment",
                        "parentItem": key,
                        "contentType": "application/pdf",
                        "linkMode": "imported_file",
                    },
                }
            )

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

    def manager(self) -> ZoteroManager:
        return ZoteroManager(client=self, storage_dir=self.storage_dir)
