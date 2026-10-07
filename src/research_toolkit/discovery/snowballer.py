"""
src/research_toolkit/discovery/snowballer.py
CitationSnowballer graph expansion engine.
Implements bidirectional 1-hop snowballing across OpenAlex and Crossref.
Conforms to CONTEXT.md and ADR-0005.
"""

from __future__ import annotations

import collections
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from research_toolkit.discovery.clients import CrossrefClient, OpenAlexClient
from research_toolkit.discovery.dedup import deduplicate_candidates
from research_toolkit.discovery.models import PaperCandidate

logger = logging.getLogger(__name__)


@dataclass
class SnowballResult:
    """Encapsulates partitioned and deduplicated graph snowballing results."""

    seeds: List[PaperCandidate] = field(default_factory=list)
    foundational: List[PaperCandidate] = field(default_factory=list)
    recent_advancements: List[PaperCandidate] = field(default_factory=list)
    all_candidates: List[PaperCandidate] = field(default_factory=list)
    co_citation_matrix: Dict[str, int] = field(default_factory=dict)


class CitationSnowballer:
    """
    Traverses 1-hop backward references (co-citation) and forward citations (bibliographic coupling).
    Discovers foundational pillars and recent literature advancements/surveys from a seed corpus.
    """

    def __init__(
        self,
        oa_client: Optional[OpenAlexClient] = None,
        crossref_client: Optional[CrossrefClient] = None,
    ):
        self.oa_client = oa_client or OpenAlexClient()
        self.crossref_client = crossref_client or CrossrefClient()

    def _normalize_oa_id(self, uri_or_id: str) -> str:
        """Normalizes an OpenAlex URI or ID to bare uppercase ID (e.g. W12345)."""
        return uri_or_id.split("/")[-1].strip().upper()

    def snowball(
        self,
        seeds: List[PaperCandidate],
        min_co_citations: int = 1,
        max_backward: int = 20,
        max_forward: int = 20,
    ) -> SnowballResult:
        """
        Executes bidirectional 1-hop citation expansion on the provided seed corpus.
        """
        if not seeds:
            return SnowballResult()

        # Step 1: Normalize seeds and extract seed IDs
        normalized_seeds: List[PaperCandidate] = []
        seed_ids: Set[str] = set()
        seed_dois: Set[str] = set()

        for s in seeds:
            s.topological_role = s.topological_role or "seed"
            normalized_seeds.append(s)
            if s.doi:
                seed_dois.add(s.doi.lower().strip())
            if s.paper_id and ("openalex" in s.paper_id.lower() or s.paper_id.upper().startswith("W")):
                seed_ids.add(self._normalize_oa_id(s.paper_id))

        # If seeds came from non-OpenAlex sources (e.g. S2) and lack referenced_works,
        # batch-resolve them via OpenAlex to populate references
        missing_refs = [s for s in normalized_seeds if not s.referenced_works and s.doi]
        if missing_refs:
            doi_filters = [f"doi:{m.doi}" for m in missing_refs if m.doi]
            # Try looking up OpenAlex records for these DOIs
            try:
                resolved = self.oa_client.get_works_by_ids(doi_filters)
                doi_to_resolved = {r.doi.lower().strip(): r for r in resolved if r.doi}
                for s in missing_refs:
                    if s.doi and s.doi.lower().strip() in doi_to_resolved:
                        matched = doi_to_resolved[s.doi.lower().strip()]
                        s.referenced_works = matched.referenced_works
                        s_id = self._normalize_oa_id(matched.paper_id)
                        seed_ids.add(s_id)
            except Exception as e:
                logger.warning("Failed to resolve seed references in OpenAlex: %s", e)

        # Step 2: Backward Snowballing (Co-citation frequency analysis)
        ref_counter: collections.Counter[str] = collections.Counter()
        for s in normalized_seeds:
            for ref_uri in s.referenced_works:
                norm_ref = self._normalize_oa_id(ref_uri)
                if norm_ref not in seed_ids:
                    ref_counter[norm_ref] += 1

        # Select candidate foundational references meeting min_co_citations threshold
        eligible_refs = [
            (ref_id, count)
            for ref_id, count in ref_counter.most_common()
            if count >= min_co_citations
        ]
        top_ref_ids = [ref_id for ref_id, _ in eligible_refs[:max_backward]]

        foundational_candidates: List[PaperCandidate] = []
        if top_ref_ids:
            try:
                raw_foundational = self.oa_client.get_works_by_ids(top_ref_ids)
                for cand in raw_foundational:
                    cand_id = self._normalize_oa_id(cand.paper_id)
                    cand.topological_role = "foundational"
                    cand.co_citation_count = ref_counter.get(cand_id, 1)
                    foundational_candidates.append(cand)
            except Exception as e:
                logger.warning("Error fetching foundational backward citations: %s", e)

        # Step 3: Forward Snowballing (Bibliographic coupling & SOTA surveys)
        recent_advancements: List[PaperCandidate] = []
        if seed_ids:
            try:
                raw_forward = self.oa_client.get_forward_citations(
                    list(seed_ids), limit=max_forward
                )
                for cand in raw_forward:
                    # Check how many seeds this paper cites
                    cand_refs = {self._normalize_oa_id(r) for r in cand.referenced_works}
                    coupling_count = len(cand_refs & seed_ids)
                    cand.topological_role = "recent_advancement"
                    cand.co_citation_count = max(1, coupling_count)
                    recent_advancements.append(cand)
            except Exception as e:
                logger.warning("Error fetching forward citations: %s", e)

        # Step 4: Deduplicate and aggregate across all streams
        aggregated = normalized_seeds + foundational_candidates + recent_advancements
        deduped = deduplicate_candidates(aggregated)

        # Map back to final groups preserving deduplication
        final_seeds = [c for c in deduped if c.topological_role == "seed"]
        final_foundational = [c for c in deduped if c.topological_role == "foundational"]
        final_advancements = [c for c in deduped if c.topological_role == "recent_advancement"]

        return SnowballResult(
            seeds=final_seeds,
            foundational=final_foundational,
            recent_advancements=final_advancements,
            all_candidates=deduped,
            co_citation_matrix=dict(ref_counter),
        )
