"""
src/research_toolkit/zotero/models.py
Domain models for Zotero Personal Library items, collections, and checkpoint verification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ZoteroCollection:
    key: str
    name: str
    parent_collection: Optional[str] = None
    version: int = 0
    user_id: Optional[str] = None

    @property
    def web_url(self) -> str:
        if self.user_id and self.key:
            return f"https://www.zotero.org/users/{self.user_id}/collections/{self.key}"
        return ""


@dataclass
class ZoteroItem:
    key: str
    title: str
    doi: Optional[str] = None
    url: Optional[str] = None
    item_type: str = "journalArticle"
    has_pdf: bool = False
    pdf_path: Optional[str] = None
    attachment_key: Optional[str] = None
    extra_attachments: int = 0
    tags: List[str] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    collections: List[str] = field(default_factory=list)

    @property
    def doi_url(self) -> Optional[str]:
        if self.doi:
            clean_d = re.sub(r"^https?://(dx\.)?doi\.org/", "", self.doi.strip())
            return f"https://doi.org/{clean_d}"
        return self.url


@dataclass
class CheckpointReport:
    collection_key: str
    collection_name: str
    total_items: int
    ready_items: List[ZoteroItem] = field(default_factory=list)
    missing_items: List[ZoteroItem] = field(default_factory=list)
    reconciled_duplicates: int = 0


@dataclass
class SyncResult:
    collection_key: str = ""
    collection_name: str = ""
    collection_url: str = ""
    created_count: int = 0
    reused_count: int = 0
    created_items: List[Dict[str, Any]] = field(default_factory=list)
    reused_items: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return self.created_count + self.reused_count

    def __len__(self) -> int:
        return self.total_count

    def __iter__(self):
        return iter(self.created_items + self.reused_items)
