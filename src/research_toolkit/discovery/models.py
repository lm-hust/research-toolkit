"""
src/research_toolkit/discovery/models.py
Domain models conforming to CONTEXT.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PaperCandidate:
    paper_id: str
    title: str
    year: Optional[int] = None
    authors: List[str] = field(default_factory=list)
    citation_count: int = 0
    influential_citation_count: int = 0
    venue: str = ""
    issn_l: Optional[str] = None
    venue_impact: float = 0.0  # OpenAlex 2-yr citedness proxy for JCR IF
    is_review: bool = False
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    abstract: str = ""
    pdf_url: Optional[str] = None
    source_platform: str = "unknown"
    relevance_score: float = 0.0  # Normalized [0.0, 1.0]
    external_ids: Dict[str, str] = field(default_factory=dict)
    composite_score: float = 0.0
    _is_preprint: Optional[bool] = field(default=None, repr=False)

    PREPRINT_VENUES = (
        "arxiv",
        "biorxiv",
        "medrxiv",
        "ssrn",
        "chemrxiv",
        "research square",
        "preprints.org",
        "techrxiv",
        "osf preprints",
        "authorea",
    )

    @property
    def is_preprint(self) -> bool:
        """Determines if the candidate originates from a preprint repository or preprint metadata."""
        if self._is_preprint is not None:
            return self._is_preprint
        if self.arxiv_id and not self.doi:
            return True
        if self.venue:
            v = self.venue.lower()
            return any(pv in v for pv in self.PREPRINT_VENUES)
        return False

    @is_preprint.setter
    def is_preprint(self, value: bool) -> None:
        self._is_preprint = value
