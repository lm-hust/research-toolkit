"""
src/research_toolkit/discovery/venue_registry.py
Offline registry mapping top-tier journals and premier CS conferences to standardized impact factors.
Conforms to CONTEXT.md.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent / "data" / "venues.json"


class VenueRegistry:
    """Offline lookup repository for top-tier journals and premier conferences."""

    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or DATA_PATH
        self.venues: List[Dict[str, Any]] = self._load_data()

    def _load_data(self) -> List[Dict[str, Any]]:
        if not self.data_path.exists():
            logger.warning("Venue registry data not found at %s", self.data_path)
            return []
        try:
            return json.loads(self.data_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to load venues.json: %s", e)
            return []

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

    def get_impact(self, venue_name: str) -> float:
        """
        Resolves a venue string to its standardized impact factor metric.
        Returns 0.0 if no top-tier venue match is found.
        """
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
