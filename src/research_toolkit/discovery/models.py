"""
src/research_toolkit/discovery/models.py
Domain models conforming to CONTEXT.md and Ticket #41 data contracts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def clean_doi(doi: Optional[str]) -> Optional[str]:
    """Cleans and canonicalizes DOI to stripped lowercase without URL or prefix."""
    if not doi:
        return None
    d = doi.lower().strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = re.sub(r"^doi:\s*", "", d)
    d = d.strip("/")
    return d if d else None


def clean_arxiv(aid: Optional[str]) -> Optional[str]:
    """Cleans and canonicalizes ArXiv identifier."""
    if not aid:
        return None
    a = aid.lower().strip()
    a = re.sub(r"^arxiv:\s*", "", a)
    a = re.sub(r"v\d+$", "", a)
    return a.strip()


def compute_paper_id(
    doi: Optional[str] = None,
    title: str = "",
    authors: Optional[List[str]] = None,
    year: Optional[int] = None,
) -> str:
    """
    Computes primary bibliographic identity:
    - Canonical clean lowercase DOI (doi:10.xxx/...)
    - Deterministic hash fallback: hash(normalized_title + first_author_lastname + year) when DOI is missing.
    """
    c_doi = clean_doi(doi)
    if c_doi:
        return f"doi:{c_doi}"

    # Normalized title: alphanumeric lowercase only
    norm_title = re.sub(r"[^a-z0-9]", "", (title or "").lower())

    # First author last name: alphanumeric lowercase only
    first_author_lastname = ""
    if authors:
        for a in authors:
            raw_author = a.strip()
            if not raw_author:
                continue
            if "," in raw_author:
                first_author_lastname = raw_author.split(",")[0].strip().lower()
            else:
                parts = raw_author.split()
                first_author_lastname = parts[-1].lower() if parts else ""
            break
    first_author_lastname = re.sub(r"[^a-z0-9]", "", first_author_lastname)

    year_str = str(year) if year is not None else ""
    seed = f"{norm_title}:{first_author_lastname}:{year_str}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"hash:{digest}"


@dataclass
class PaperCandidate:
    paper_id: str = ""
    title: str = ""
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
    co_citation_count: int = 0
    topological_role: str = ""  # 'seed', 'foundational', 'recent_advancement'
    topological_score: float = 0.0
    referenced_works: List[str] = field(default_factory=list)
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

    def __post_init__(self) -> None:
        if self.doi:
            self.doi = clean_doi(self.doi)
        if self.arxiv_id:
            self.arxiv_id = clean_arxiv(self.arxiv_id)
        if not self.paper_id:
            self.paper_id = self.compute_primary_id()

    def compute_primary_id(self) -> str:
        """Returns the canonical primary identity for this candidate."""
        return compute_paper_id(
            doi=self.doi,
            title=self.title,
            authors=self.authors,
            year=self.year,
        )

    @property
    def primary_id(self) -> str:
        """Alias for canonical primary identity."""
        return self.compute_primary_id()

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

    def to_dict(self) -> Dict[str, Any]:
        """Serializes candidate to standard dictionary representation."""
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "year": self.year,
            "authors": list(self.authors),
            "citation_count": self.citation_count,
            "influential_citation_count": self.influential_citation_count,
            "venue": self.venue,
            "issn_l": self.issn_l,
            "venue_impact": self.venue_impact,
            "is_review": self.is_review,
            "is_preprint": self.is_preprint,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "abstract": self.abstract,
            "pdf_url": self.pdf_url,
            "source_platform": self.source_platform,
            "relevance_score": self.relevance_score,
            "external_ids": dict(self.external_ids),
            "composite_score": self.composite_score,
            "co_citation_count": self.co_citation_count,
            "topological_role": self.topological_role,
            "topological_score": self.topological_score,
            "referenced_works": list(self.referenced_works),
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes candidate to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PaperCandidate:
        """Deserializes candidate from dictionary."""
        is_pre = data.get("is_preprint")
        c = cls(
            paper_id=data.get("paper_id", ""),
            title=data.get("title", ""),
            year=data.get("year"),
            authors=data.get("authors") or [],
            citation_count=data.get("citation_count", 0),
            influential_citation_count=data.get("influential_citation_count", 0),
            venue=data.get("venue", ""),
            issn_l=data.get("issn_l"),
            venue_impact=float(data.get("venue_impact", 0.0)),
            is_review=bool(data.get("is_review", False)),
            doi=data.get("doi"),
            arxiv_id=data.get("arxiv_id"),
            abstract=data.get("abstract", ""),
            pdf_url=data.get("pdf_url"),
            source_platform=data.get("source_platform", "unknown"),
            relevance_score=float(data.get("relevance_score", 0.0)),
            external_ids=data.get("external_ids") or {},
            composite_score=float(data.get("composite_score", 0.0)),
            co_citation_count=data.get("co_citation_count", 0),
            topological_role=data.get("topological_role", ""),
            topological_score=float(data.get("topological_score", 0.0)),
            referenced_works=data.get("referenced_works") or [],
        )
        if is_pre is not None:
            c.is_preprint = is_pre
        return c

    @classmethod
    def from_json(cls, json_str: str) -> PaperCandidate:
        """Deserializes candidate from JSON string."""
        return cls.from_dict(json.loads(json_str))


def generate_batch_id() -> str:
    """Generates a unique timestamped batch ID."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"batch_{ts}_{uuid.uuid4().hex[:8]}"


@dataclass
class PaperCandidateBatch:
    """
    Immutable candidate batch container conforming to Ticket #41 data contract.
    Persisted to .research/batches/<batch_id>.json via atomic write-then-rename.
    """

    batch_id: str = field(default_factory=generate_batch_id)
    query: str = ""
    papers: List[PaperCandidate] = field(default_factory=list)
    source_observations: Dict[str, Any] = field(default_factory=dict)
    status: str = "completed"  # "completed" | "partial_failure" | "budget_truncated"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.batch_id:
            self.batch_id = generate_batch_id()
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def topic(self) -> str:
        """Alias for query."""
        return self.query

    def __len__(self) -> int:
        return len(self.papers)

    def __iter__(self):
        return iter(self.papers)

    def __getitem__(self, idx: int) -> PaperCandidate:
        return self.papers[idx]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes batch to dictionary."""
        return {
            "batch_id": self.batch_id,
            "query": self.query,
            "topic": self.query,
            "papers": [p.to_dict() for p in self.papers],
            "source_observations": dict(self.source_observations),
            "status": self.status,
            "created_at": self.created_at,
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes batch to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PaperCandidateBatch:
        """Deserializes batch from dictionary."""
        query = data.get("query") or data.get("topic") or ""
        raw_papers = (
            data.get("papers")
            or data.get("discovered_candidates")
            or data.get("all_candidates")
            or data.get("selected_papers")
            or []
        )
        papers = [
            p if isinstance(p, PaperCandidate) else PaperCandidate.from_dict(p)
            for p in raw_papers
        ]
        return cls(
            batch_id=data.get("batch_id") or "",
            query=query,
            papers=papers,
            source_observations=data.get("source_observations") or {},
            status=data.get("status", "completed"),
            created_at=data.get("created_at") or "",
        )

    @classmethod
    def from_json(cls, json_str: str) -> PaperCandidateBatch:
        """Deserializes batch from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def save(self, directory: Optional[Path | str] = None) -> Path:
        """
        Persists the batch atomically to .research/batches/<batch_id>.json (or specified dir)
        using temporary file write followed by atomic rename.
        """
        if directory:
            target_dir = Path(directory)
        else:
            base_dir = os.getenv("RESEARCH_BATCH_DIR") or os.getenv("RESEARCH_DATA_DIR")
            target_dir = Path(base_dir) if base_dir else (Path.cwd() / ".research" / "batches")

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{self.batch_id}.json"

        # Atomic write: write to temporary file in the same directory, then rename
        tmp_name = f".{self.batch_id}.json.tmp_{uuid.uuid4().hex}"
        tmp_path = target_dir / tmp_name
        try:
            tmp_path.write_text(self.to_json(indent=2), encoding="utf-8")
            tmp_path.replace(target_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise
        return target_path

    @classmethod
    def load(cls, file_path: Path | str) -> PaperCandidateBatch:
        """Loads and parses a PaperCandidateBatch from file."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return cls.from_json(content)


@dataclass
class AssessmentRecord:
    """
    Structured qualitative and quantitative relevance assessment for a candidate paper.
    Conforms to Ticket #42 data contract.
    """

    paper_id: str
    decision: str = "pending"  # "related" | "unrelated" | "pending"
    batch_id: Optional[str] = None
    relevance_score: Optional[float] = None  # 0.0 to 1.0; 0.0 if unrelated; None if pending
    reason: str = ""
    evidence: str = ""
    assessor: str = "lit-scout"  # e.g. "lit-scout" or "user"
    created_at: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.decision == "unrelated":
            self.relevance_score = 0.0
        elif self.decision == "pending":
            self.relevance_score = None
        elif self.decision == "related" and self.relevance_score is not None:
            self.relevance_score = max(0.0, min(1.0, float(self.relevance_score)))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes AssessmentRecord to dictionary."""
        return {
            "paper_id": self.paper_id,
            "batch_id": self.batch_id,
            "decision": self.decision,
            "relevance_score": self.relevance_score,
            "reason": self.reason,
            "evidence": self.evidence,
            "assessor": self.assessor,
            "created_at": self.created_at,
            "version": self.version,
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes AssessmentRecord to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AssessmentRecord:
        """Deserializes AssessmentRecord from dictionary."""
        rel_score = data.get("relevance_score")
        return cls(
            paper_id=data.get("paper_id", ""),
            decision=data.get("decision", "pending"),
            batch_id=data.get("batch_id"),
            relevance_score=float(rel_score) if rel_score is not None else None,
            reason=data.get("reason", ""),
            evidence=data.get("evidence", ""),
            assessor=data.get("assessor", "lit-scout"),
            created_at=data.get("created_at", ""),
            version=int(data.get("version", 1)),
        )

    @classmethod
    def from_json(cls, json_str: str) -> AssessmentRecord:
        """Deserializes AssessmentRecord from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SelectionResult:
    """
    Structured outcome of the composite ranking and MMR diversity selection pipeline.
    Conforms to Ticket #42 data contract.
    """

    batch_id: Optional[str] = None
    strategy: str = "composite_mmr"
    requested_n: int = 10
    selected_papers: List[PaperCandidate] = field(default_factory=list)
    selected_paper_ids: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    reasons: Dict[str, str] = field(default_factory=dict)
    status: str = "completed"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.selected_papers and not self.selected_paper_ids:
            self.selected_paper_ids = [p.paper_id for p in self.selected_papers]

    def __len__(self) -> int:
        return len(self.selected_papers)

    def __iter__(self):
        return iter(self.selected_papers)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes SelectionResult to dictionary."""
        return {
            "batch_id": self.batch_id,
            "strategy": self.strategy,
            "requested_n": self.requested_n,
            "selected_papers": [p.to_dict() for p in self.selected_papers],
            "selected_paper_ids": list(self.selected_paper_ids),
            "scores": dict(self.scores),
            "reasons": dict(self.reasons),
            "status": self.status,
            "created_at": self.created_at,
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes SelectionResult to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SelectionResult:
        """Deserializes SelectionResult from dictionary."""
        raw_papers = data.get("selected_papers") or []
        selected_papers = [
            p if isinstance(p, PaperCandidate) else PaperCandidate.from_dict(p)
            for p in raw_papers
        ]
        selected_paper_ids = data.get("selected_paper_ids")
        if selected_paper_ids is None:
            selected_paper_ids = [p.paper_id for p in selected_papers]
        return cls(
            batch_id=data.get("batch_id"),
            strategy=data.get("strategy", "composite_mmr"),
            requested_n=int(data.get("requested_n", 10)),
            selected_papers=selected_papers,
            selected_paper_ids=list(selected_paper_ids),
            scores=dict(data.get("scores") or {}),
            reasons=dict(data.get("reasons") or {}),
            status=data.get("status", "completed"),
            created_at=data.get("created_at", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> SelectionResult:
        """Deserializes SelectionResult from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class CitationEdge:
    """
    Directed citation relationship edge between papers in a snowball expansion graph.
    direction is 'cites' or 'referenced_by'.
    """

    source_id: str
    target_id: str
    direction: str  # "cites" | "referenced_by"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes CitationEdge to standard dictionary representation."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "direction": self.direction,
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes CitationEdge to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CitationEdge:
        """Deserializes CitationEdge from dictionary."""
        return cls(
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            direction=data.get("direction", "cites"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> CitationEdge:
        """Deserializes CitationEdge from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class SnowballResult:
    """
    Structured outcome of bidirectional 1-hop citation graph expansion.
    Conforms to Ticket #43 data contract, cleanly partitioning seeds from
    newly discovered candidates.
    """

    seed_paper_ids: List[str] = field(default_factory=list)
    seeds: List[PaperCandidate] = field(default_factory=list)
    discovered_candidates: List[PaperCandidate] = field(default_factory=list)
    citation_edges: List[CitationEdge] = field(default_factory=list)
    direction: str = "both"  # "both" | "forward" | "backward"
    status: str = "completed"  # "completed" | "partial_failure" | "budget_truncated"
    created_at: str = ""
    co_citation_matrix: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.seeds and not self.seed_paper_ids:
            self.seed_paper_ids = [s.paper_id for s in self.seeds]

    @property
    def all_candidates(self) -> List[PaperCandidate]:
        """All candidates including seeds and newly discovered candidates."""
        return self.seeds + self.discovered_candidates

    @property
    def foundational(self) -> List[PaperCandidate]:
        """Backward-discovered foundational candidates."""
        return [c for c in self.discovered_candidates if c.topological_role == "foundational"]

    @property
    def recent_advancements(self) -> List[PaperCandidate]:
        """Forward-discovered recent advancement candidates."""
        return [c for c in self.discovered_candidates if c.topological_role == "recent_advancement"]

    def __len__(self) -> int:
        return len(self.discovered_candidates)

    def __iter__(self):
        return iter(self.discovered_candidates)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes SnowballResult to dictionary."""
        return {
            "seed_paper_ids": list(self.seed_paper_ids),
            "seeds": [s.to_dict() for s in self.seeds],
            "discovered_candidates": [c.to_dict() for c in self.discovered_candidates],
            "citation_edges": [e.to_dict() for e in self.citation_edges],
            "direction": self.direction,
            "status": self.status,
            "created_at": self.created_at,
            "co_citation_matrix": dict(self.co_citation_matrix),
        }

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes SnowballResult to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SnowballResult:
        """Deserializes SnowballResult from dictionary."""
        raw_seeds = data.get("seeds") or []
        seeds = [
            s if isinstance(s, PaperCandidate) else PaperCandidate.from_dict(s)
            for s in raw_seeds
        ]
        raw_cands = data.get("discovered_candidates") or []
        if not raw_cands:
            raw_f = data.get("foundational") or []
            raw_r = data.get("recent_advancements") or []
            raw_cands = raw_f + raw_r
        discovered_candidates = [
            c if isinstance(c, PaperCandidate) else PaperCandidate.from_dict(c)
            for c in raw_cands
        ]
        raw_edges = data.get("citation_edges") or []
        citation_edges = [
            e if isinstance(e, CitationEdge) else CitationEdge.from_dict(e)
            for e in raw_edges
        ]
        seed_ids = data.get("seed_paper_ids")
        if seed_ids is None:
            seed_ids = [s.paper_id for s in seeds]
        return cls(
            seed_paper_ids=list(seed_ids),
            seeds=seeds,
            discovered_candidates=discovered_candidates,
            citation_edges=citation_edges,
            direction=data.get("direction", "both"),
            status=data.get("status", "completed"),
            created_at=data.get("created_at") or "",
            co_citation_matrix=dict(data.get("co_citation_matrix") or {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> SnowballResult:
        """Deserializes SnowballResult from JSON string."""
        return cls.from_dict(json.loads(json_str))


