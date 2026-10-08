"""
src/research_toolkit/zotero/client.py
Zotero Web API client strictly scoped to user personal library (ADR-0002).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from research_toolkit.discovery.dedup import Deduplicator
from research_toolkit.zotero.models import ZoteroCollection

logger = logging.getLogger(__name__)


class ZoteroClient:
    """
    HTTP client for the Zotero Web API v3.
    Strictly restricted to the user personal library (`/users/<user_id>/`).
    """

    API_ROOT = "https://api.zotero.org"

    def __init__(
        self,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        library_type: Optional[str] = None,
    ):
        self.library_type = (library_type or os.getenv("ZOTERO_LIBRARY_TYPE") or "user").lower()
        if self.library_type != "user":
            raise ValueError(
                f"Invalid library_type: '{self.library_type}'. Only user personal library "
                "('user') is supported. Shared group libraries are strictly prohibited."
            )

        self.api_key = api_key or os.getenv("ZOTERO_API_KEY", "")
        self.user_id = str(user_id or os.getenv("ZOTERO_USER_ID", "")).strip()
        self.base_path = f"/users/{self.user_id}"
        self.base_url = f"{self.API_ROOT}{self.base_path}"

    def url(self, path: str) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{clean_path}"

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Zotero-API-Version": "3",
            "Content-Type": "application/json",
            "User-Agent": "ResearchToolkit/0.1.0",
        }
        if self.api_key:
            headers["Zotero-API-Key"] = self.api_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        raw: bool = False,
    ) -> Any:
        if not self.user_id:
            raise ValueError(
                "Missing Zotero User ID. Please set ZOTERO_USER_ID in your .env or environment. "
                "Run `research-toolkit doctor` to inspect system configuration."
            )
        if not self.api_key:
            raise ValueError(
                "Missing Zotero API Key. Please set ZOTERO_API_KEY in your .env or environment."
            )

        full_url = self.url(path)
        if params:
            full_url = f"{full_url}?{urllib.parse.urlencode(params)}"

        headers = self._headers()
        if extra_headers:
            headers.update(extra_headers)

        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(full_url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if raw:
                    return resp.read()
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except Exception as e:
            logger.error("Zotero API request %s %s failed: %s", method, full_url, e)
            raise

    def download_item_file(self, item_key: str, dest_path: Path) -> Optional[Path]:
        """
        Downloads a full-text attachment file directly from Zotero Cloud Storage.
        Saves content to dest_path and returns the path on success, or None on failure.
        """
        try:
            content = self._request("GET", f"/items/{item_key}/file", raw=True)
            if content and isinstance(content, bytes):
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(content)
                return dest_path
        except Exception as e:
            logger.warning("Failed to download cloud file for attachment item %s: %s", item_key, e)
        return None

    def get_or_create_collection(
        self, name: str, parent_key: Optional[str] = None
    ) -> ZoteroCollection:
        """Finds collection by name or creates it in the personal library."""
        collections_data = self._request("GET", "/collections")
        for col in collections_data:
            c_data = col.get("data", {})
            if (
                col.get("key", "").strip() == name.strip()
                or c_data.get("name", "").strip().lower() == name.strip().lower()
            ):
                return ZoteroCollection(
                    key=col.get("key", ""),
                    name=c_data.get("name", name),
                    parent_collection=c_data.get("parentCollection") or None,
                    version=col.get("version", 0),
                    user_id=self.user_id,
                )

        # Check if name is an existing collection key directly
        if len(name.strip()) == 8 and name.strip().isalnum():
            try:
                col = self._request("GET", f"/collections/{name.strip()}")
                if isinstance(col, dict) and "key" in col:
                    c_data = col.get("data", {})
                    return ZoteroCollection(
                        key=col.get("key", ""),
                        name=c_data.get("name", name),
                        parent_collection=c_data.get("parentCollection") or None,
                        version=col.get("version", 0),
                        user_id=self.user_id,
                    )
            except Exception:
                pass

        # Create new collection
        payload = [{"name": name, "parentCollection": parent_key or False}]
        resp = self._request("POST", "/collections", payload=payload)

        # Extract created collection key
        key = ""
        if isinstance(resp, dict):
            successful = resp.get("successful") or resp.get("success") or {}
            first = list(successful.values())[0] if successful else {}
            if isinstance(first, dict):
                key = first.get("key", "")
            elif isinstance(first, str):
                key = first
        return ZoteroCollection(key=key, name=name, parent_collection=parent_key, user_id=self.user_id)

    def get_collection_items(
        self, collection_key: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieves items in the given personal collection."""
        params = {"limit": limit}
        return self._request("GET", f"/collections/{collection_key}/items", params=params)

    def create_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Creates items in the personal library."""
        resp = self._request("POST", "/items", payload=items)
        if isinstance(resp, dict):
            successful = resp.get("successful") or resp.get("success") or {}
            return list(successful.values())
        return []

    def create_attachment_link(
        self, parent_key: str, title: str, url: str, content_type: str = "application/pdf"
    ) -> Dict[str, Any]:
        """Creates an imported/linked URL attachment under a parent item."""
        payload = [
            {
                "itemType": "attachment",
                "parentItem": parent_key,
                "linkMode": "imported_url",
                "title": title,
                "url": url,
                "contentType": content_type,
            }
        ]
        res = self.create_items(payload)
        return res[0] if res else {}

    def find_existing_item(
        self, doi: Optional[str] = None, title: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Searches the personal Zotero library for an existing item matching DOI or normalized title.
        Matches by canonical DOI first; if no DOI is provided, falls back to normalized title.
        Returns the raw item dict if found, else None.
        """
        clean_doi = Deduplicator.clean_doi(doi) if doi else ""
        if clean_doi:
            items = self._request("GET", "/items", params={"q": clean_doi, "itemType": "-attachment", "limit": 10})
            if isinstance(items, list):
                for it in items:
                    it_data = it.get("data", {})
                    it_doi = Deduplicator.clean_doi(it_data.get("DOI"))
                    if it_doi and it_doi == clean_doi:
                        return it
            return None

        # Fallback to normalized title match only when candidate has no DOI
        if title:
            norm_title = Deduplicator.clean_title(title)
            if norm_title:
                items = self._request("GET", "/items", params={"q": title[:50], "itemType": "-attachment", "limit": 10})
                if isinstance(items, list):
                    for it in items:
                        it_data = it.get("data", {})
                        it_title = Deduplicator.clean_title(it_data.get("title", ""))
                        if it_title and it_title == norm_title:
                            return it

        return None

    def add_item_to_collection(
        self,
        item: Union[Dict[str, Any], str, None] = None,
        collection_key: str = "",
        version: Optional[int] = None,
        existing_collections: Optional[List[str]] = None,
        *,
        item_key: Optional[str] = None,
    ) -> bool:
        """
        Appends collection_key to an existing item's collections list without altering other fields.
        Accepts either the raw item dict or an item_key string with version.
        Uses Zotero PATCH /items/<item_key> with If-Unmodified-Since-Version header.
        """
        if isinstance(item, dict):
            key = item.get("key", "")
            if version is None:
                version = item.get("version")
            if existing_collections is None:
                existing_collections = item.get("data", {}).get("collections", [])
        else:
            key = item or item_key or ""

        if not key or version is None:
            logger.warning("Cannot patch item: missing item key or version")
            return False

        current_cols = list(existing_collections or [])
        if collection_key in current_cols:
            return True  # Already belongs to target collection

        current_cols.append(collection_key)
        try:
            self._request(
                "PATCH",
                f"/items/{key}",
                payload={"collections": current_cols},
                extra_headers={"If-Unmodified-Since-Version": str(version)},
            )
            if isinstance(item, dict):
                item.setdefault("data", {})["collections"] = current_cols
            return True
        except Exception as e:
            logger.warning("Failed to add item %s to collection %s: %s", key, collection_key, e)
            return False
