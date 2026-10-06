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
from typing import Any, Dict, List, Optional

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
        self, method: str, path: str, payload: Optional[Any] = None, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        full_url = self.url(path)
        if params:
            full_url = f"{full_url}?{urllib.parse.urlencode(params)}"

        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(full_url, data=data, headers=self._headers(), method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except Exception as e:
            logger.error("Zotero API request %s %s failed: %s", method, full_url, e)
            raise

    def get_or_create_collection(
        self, name: str, parent_key: Optional[str] = None
    ) -> ZoteroCollection:
        """Finds collection by name or creates it in the personal library."""
        collections_data = self._request("GET", "/collections")
        for col in collections_data:
            c_data = col.get("data", {})
            if c_data.get("name", "").strip().lower() == name.strip().lower():
                return ZoteroCollection(
                    key=col.get("key", ""),
                    name=c_data.get("name", name),
                    parent_collection=c_data.get("parentCollection") or None,
                    version=col.get("version", 0),
                )

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
        return ZoteroCollection(key=key, name=name, parent_collection=parent_key)

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
