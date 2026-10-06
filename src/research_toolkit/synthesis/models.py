"""
src/research_toolkit/synthesis/models.py
Domain models for NotebookLM/Gemini synthesis, source management, and grounded evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NotebookInfo:
    id: str
    title: str
    sources_count: int = 0


@dataclass
class NotebookSource:
    id: str
    title: str
    source_type: str = "pdf"
    path: Optional[str] = None


@dataclass
class DistilledEvidence:
    """Verbatim quoted evidence grounded in a specific source document."""

    quote: str
    source_id: str
    source_title: str = ""
    start_offset: int = 0
    end_offset: int = 0


@dataclass
class GroundedAnswer:
    """Grounded answer accompanied by verbatim cited evidence."""

    answer: str
    citations: List[DistilledEvidence] = field(default_factory=list)
    notebook_id: str = ""
