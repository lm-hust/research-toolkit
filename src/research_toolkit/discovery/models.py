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
