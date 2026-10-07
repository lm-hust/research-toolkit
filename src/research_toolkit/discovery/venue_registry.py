"""
src/research_toolkit/discovery/venue_registry.py
Hybrid registry mapping top-tier journals, CS conferences, and cached OpenAlex 2-year citedness metrics.
Conforms to CONTEXT.md and ADR-0004.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from research_toolkit.discovery.clients import OpenAlexClient

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent / "data" / "venues.json"
CACHE_PATH = Path.home() / ".cache" / "research-toolkit" / "venues_cache.json"


class VenueRegistry:
    """Hybrid lookup repository and caching layer for top-tier venues and OpenAlex impact factors."""

    def __init__(
        self,
        data_path: Optional[Path] = None,
        cache_path: Optional[Path] = None,
        openalex_client: Optional[OpenAlexClient] = None,
    ):
        self.data_path = data_path or DATA_PATH
        self.cache_path = cache_path or CACHE_PATH
        self.venues: List[Dict[str, Any]] = self._load_data()
        self._cache: Dict[str, Any] = self._load_cache()
        self.openalex_client = openalex_client or OpenAlexClient()

    def _load_data(self) -> List[Dict[str, Any]]:
        if not self.data_path.exists():
            logger.warning("Venue registry data not found at %s", self.data_path)
            return []
        try:
            return json.loads(self.data_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to load venues.json: %s", e)
            return []

    def _load_cache(self) -> Dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug("Failed to load venues cache: %s", e)
            return {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("Failed to write venues cache: %s", e)

    def _fetch_openalex_source_impact(self, source_id: str) -> float:
        clean_id = source_id.split("/")[-1].strip()
        if not clean_id.startswith("S"):
            return 0.0

        try:
            impact = self.openalex_client.get_source_impact(clean_id)
            if impact > 0.0:
                self._cache[source_id] = {
                    "impact": impact,
                    "timestamp": time.time(),
                }
                self._save_cache()
            return impact
        except Exception as e:
            logger.debug("Could not fetch OpenAlex source impact for %s: %s", clean_id, e)
            return 0.0

    @staticmethod
    def normalize_name(text: str) -> str:
        """Removes conference years, volume numbers, and punctuation."""
        if not text:
            return ""
        s = text.lower()
        # Remove 4-digit years (e.g. 2024) or 2-digit apostrophe years (e.g. '24)
        s = re.sub(r"\b(19|20)\d{2}\b", " ", s)
        s = re.sub(r"\'\d{2}\b", " ", s)
        # Remove common conference volume tags like "vol. 36", "no. 2"
        s = re.sub(r"\bvol(ume)?\.?\s*\d+\b", " ", s)
        s = re.sub(r"\bproceedings\s+of\s+(the)?\b", " ", s)
        # Clean non-alphanumeric except spaces
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    def _lookup_offline(self, venue_name: str) -> float:
        if not venue_name or not venue_name.strip():
            return 0.0

        norm_query = self.normalize_name(venue_name)
        if not norm_query:
            return 0.0

        best_impact = 0.0

        for entry in self.venues:
            impact = float(entry.get("impact_factor", 0.0))
            aliases = entry.get("aliases", [])

            for alias in aliases:
                norm_alias = self.normalize_name(alias)
                if not norm_alias:
                    continue

                # 1. Exact match after normalization
                if norm_query == norm_alias:
                    if impact > best_impact:
                        best_impact = impact
                    break

                # 2. Word boundary match for acronyms (e.g. "cvpr", "tpami", "iclr")
                if len(norm_alias) <= 8:
                    pattern = rf"\b{re.escape(norm_alias)}\b"
                    if re.search(pattern, norm_query):
                        if impact > best_impact:
                            best_impact = impact
                        break

                # 3. Substring match for longer titles
                if len(norm_alias) > 8 and (norm_alias in norm_query or norm_query in norm_alias):
                    if impact > best_impact:
                        best_impact = impact
                    break

        return best_impact

    def get_impact(self, venue_name: str, source_id: Optional[str] = None) -> float:
        """
        Resolves a venue string or OpenAlex source ID to its standardized impact factor metric.
        Checks offline registry first, then local cache / dynamic fetch.
        """
        impact = self._lookup_offline(venue_name)
        if impact > 0.0:
            return impact

        if source_id:
            cached = self._cache.get(source_id)
            if cached and isinstance(cached, dict):
                # 30 days TTL = 2592000s
                ts = float(cached.get("timestamp", 0))
                if time.time() - ts < 2592000:
                    return float(cached.get("impact", 0.0))
            return self._fetch_openalex_source_impact(source_id)

        return 0.0
