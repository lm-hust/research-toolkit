"""
src/research_toolkit/discovery/snowballer.py
CitationSnowballer graph expansion engine.
Implements bidirectional 1-hop snowballing across OpenAlex and Crossref.
Conforms to CONTEXT.md and ADR-0005.
"""

from __future__ import annotations

import collections
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Union

from research_toolkit.discovery.clients import CrossrefClient, OpenAlexClient
from research_toolkit.discovery.dedup import deduplicate_candidates
from research_toolkit.discovery.models import (
    CitationEdge,
    PaperCandidate,
    PaperCandidateBatch,
    SelectionResult,
    SnowballResult,
    clean_arxiv,
    clean_doi,
)

logger = logging.getLogger(__name__)

# Re-export SnowballResult and CitationEdge for backward compatibility
__all__ = [
    "CitationEdge",
    "CitationSnowballer",
    "SnowballResult",
    "adapt_seeds",
    "candidate_from_id",
    "load_seeds_from_collection",
]


def candidate_from_id(raw_id: str) -> PaperCandidate:
    """Creates a stub PaperCandidate from a raw identifier or DOI."""
    clean_id = raw_id.strip()
    c_doi = clean_doi(clean_id)
    if c_doi and c_doi.startswith("10."):
        return PaperCandidate(
            paper_id=f"doi:{c_doi}",
            doi=c_doi,
            title=f"DOI:{c_doi}",
        )
    if clean_id.lower().startswith("arxiv:") or re.match(r"^\d{4}\.\d{4,5}", clean_id):
        aid = clean_arxiv(clean_id)
        return PaperCandidate(
            paper_id=f"arxiv:{aid}",
            arxiv_id=aid,
            title=f"arXiv:{aid}",
        )
    return PaperCandidate(
        paper_id=clean_id,
        title=clean_id,
    )


def adapt_seeds(
    seeds: Any,
    zotero_manager: Optional[Any] = None,
) -> List[PaperCandidate]:
    """
    Adapts various seed inputs into a list of PaperCandidate domain objects.
    Supported inputs:
    - List[PaperCandidate]
    - SelectionResult: extracts selected_papers
    - PaperCandidateBatch: extracts papers
    - SnowballResult: extracts seeds or discovered_candidates
    - Zotero collection name / key: fetches candidates via ZoteroManager
    - List[str] / comma-separated string of DOIs or platform IDs
    - Dict representation of SelectionResult, PaperCandidateBatch, or SnowballResult
    """
    if seeds is None:
        return []

    if isinstance(seeds, SelectionResult):
        return list(seeds.selected_papers)

    if isinstance(seeds, PaperCandidateBatch):
        return list(seeds.papers)

    if isinstance(seeds, SnowballResult):
        return list(seeds.seeds or seeds.discovered_candidates)

    if isinstance(seeds, dict):
        if "selected_papers" in seeds:
            return SelectionResult.from_dict(seeds).selected_papers
        if "papers" in seeds:
            return PaperCandidateBatch.from_dict(seeds).papers
        if "seeds" in seeds:
            return SnowballResult.from_dict(seeds).seeds
        if "discovered_candidates" in seeds:
            return SnowballResult.from_dict(seeds).discovered_candidates

    if isinstance(seeds, str):
        s_str = seeds.strip()
        if s_str.startswith("{") and s_str.endswith("}"):
            try:
                data = json.loads(s_str)
                return adapt_seeds(data, zotero_manager=zotero_manager)
            except Exception:
                pass
        if s_str.startswith("collection:"):
            col_name = s_str.split(":", 1)[1].strip()
            return load_seeds_from_collection(col_name, zotero_manager=zotero_manager)
        parts = [p.strip() for p in s_str.split(",") if p.strip()]
        return [candidate_from_id(p) for p in parts]

    if isinstance(seeds, list):
        if not seeds:
            return []
        if all(isinstance(x, PaperCandidate) for x in seeds):
            return list(seeds)
        if all(isinstance(x, str) for x in seeds):
            return [candidate_from_id(x) for x in seeds]
        if all(isinstance(x, dict) for x in seeds):
            return [PaperCandidate.from_dict(x) for x in seeds]

    return []


def load_seeds_from_collection(
    collection_name_or_key: str,
    zotero_manager: Optional[Any] = None,
) -> List[PaperCandidate]:
    """Fetches candidates from an existing Zotero collection."""
    if zotero_manager is None:
        from research_toolkit.zotero.manager import ZoteroManager

        zotero_manager = ZoteroManager()
    return zotero_manager.get_collection_candidates(collection_name_or_key)


class CitationSnowballer:
    """
    Traverses 1-hop backward references (co-citation) and forward citations (bibliographic coupling).
    Discovers foundational pillars and recent literature advancements from a seed corpus.
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
        seeds: Union[
            List[PaperCandidate],
            SelectionResult,
            PaperCandidateBatch,
            List[str],
            str,
        ],
        direction: str = "both",
        max_backward: int = 20,
        max_forward: int = 20,
        min_co_citations: int = 1,
    ) -> SnowballResult:
        """
        Executes 1-hop bidirectional citation expansion on the provided seed corpus.

        Args:
            seeds: Seeds from any supported input adapter.
            direction: Expansion direction ('both' | 'forward' | 'backward').
            max_backward: Budget cap for backward references (default: 20).
            max_forward: Budget cap for forward citations (default: 20).
            min_co_citations: Minimum co-citation threshold for foundational papers (default: 1).
        """
        seed_list = adapt_seeds(seeds)
        if not seed_list:
            return SnowballResult(direction=direction, status="completed")

        status = "completed"

        # Step 1: Normalize seeds and extract seed IDs
        normalized_seeds: List[PaperCandidate] = []
        seed_ids: Set[str] = set()
        seed_dois: Set[str] = set()

        for s in seed_list:
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
            doi_list = [m.doi for m in missing_refs if m.doi]
            try:
                resolved = self.oa_client.get_works_by_dois(doi_list)
                doi_to_resolved = {r.doi.lower().strip(): r for r in resolved if r.doi}
                for s in missing_refs:
                    if s.doi and s.doi.lower().strip() in doi_to_resolved:
                        matched = doi_to_resolved[s.doi.lower().strip()]
                        s.referenced_works = matched.referenced_works
                        s_id = self._normalize_oa_id(matched.paper_id)
                        seed_ids.add(s_id)
            except Exception as e:
                logger.warning("Failed to resolve seed references in OpenAlex: %s", e)
                status = "partial_failure"

            # Crossref reference fallback for any seeds still lacking references
            for s in missing_refs:
                if not s.referenced_works and s.doi:
                    try:
                        cr_data = self.crossref_client.get_work(s.doi)
                        if cr_data and cr_data.get("references"):
                            deposited = [
                                r["doi"]
                                for r in cr_data["references"]
                                if r.get("doi")
                            ]
                            if deposited:
                                s.referenced_works = deposited
                    except Exception as e:
                        logger.debug("Crossref fallback failed for DOI %s: %s", s.doi, e)

        # Also resolve for seeds with OpenAlex IDs lacking referenced_works
        missing_oa_refs = [
            s
            for s in normalized_seeds
            if not s.referenced_works
            and s.paper_id
            and self._normalize_oa_id(s.paper_id).startswith("W")
        ]
        if missing_oa_refs:
            oa_ids = [self._normalize_oa_id(s.paper_id) for s in missing_oa_refs]
            try:
                resolved_oa = self.oa_client.get_works_by_ids(oa_ids)
                id_to_resolved = {
                    self._normalize_oa_id(r.paper_id): r for r in resolved_oa
                }
                for s in missing_oa_refs:
                    norm_id = self._normalize_oa_id(s.paper_id)
                    if norm_id in id_to_resolved:
                        s.referenced_works = id_to_resolved[norm_id].referenced_works
                        seed_ids.add(norm_id)
            except Exception as e:
                logger.warning("Failed to resolve seed references by ID in OpenAlex: %s", e)
                status = "partial_failure"

        # Step 2: Backward Snowballing (Co-citation frequency analysis)
        ref_counter: collections.Counter[str] = collections.Counter()
        ref_to_seed_ids: Dict[str, Set[str]] = collections.defaultdict(set)
        foundational_candidates: List[PaperCandidate] = []

        if direction.lower() in ("both", "backward"):
            for s in normalized_seeds:
                for ref_uri in s.referenced_works:
                    norm_ref = self._normalize_oa_id(ref_uri)
                    if norm_ref not in seed_ids:
                        ref_counter[norm_ref] += 1
                        ref_to_seed_ids[norm_ref].add(s.paper_id)

            eligible_refs = [
                (ref_id, count)
                for ref_id, count in ref_counter.most_common()
                if count >= min_co_citations
            ]
            top_ref_ids = [ref_id for ref_id, _ in eligible_refs[:max_backward]]

            if top_ref_ids:
                try:
                    raw_foundational = self.oa_client.get_works_by_ids(top_ref_ids)
                    for cand in raw_foundational:
                        cand_id = self._normalize_oa_id(cand.paper_id)
                        cand.topological_role = "foundational"
                        cand.co_citation_count = ref_counter.get(cand_id, 1)
                        if cand.relevance_score <= 0.0:
                            cand.relevance_score = 0.85
                        foundational_candidates.append(cand)
                except Exception as e:
                    logger.warning("Error fetching foundational backward citations: %s", e)
                    status = "partial_failure"

        # Step 3: Forward Snowballing (Bibliographic coupling & SOTA surveys)
        recent_advancements: List[PaperCandidate] = []
        cand_to_cited_seed_ids: Dict[str, Set[str]] = collections.defaultdict(set)

        if direction.lower() in ("both", "forward") and seed_ids:
            try:
                raw_forward = self.oa_client.get_forward_citations(
                    list(seed_ids), limit=max_forward
                )
                for cand in raw_forward:
                    cand_refs = {self._normalize_oa_id(r) for r in cand.referenced_works}
                    matching_seeds = cand_refs & seed_ids
                    coupling_count = len(matching_seeds)
                    if coupling_count == 0:
                        coupling_count = 1
                    cand.co_citation_count = coupling_count
                    cand.topological_role = "recent_advancement"
                    if cand.relevance_score <= 0.0:
                        cand.relevance_score = 0.85
                    # Legacy heuristic cutoff eliminated: single-seed forward citations retained
                    recent_advancements.append(cand)

                    cand_norm_id = self._normalize_oa_id(cand.paper_id)
                    for s in normalized_seeds:
                        norm_s_id = self._normalize_oa_id(s.paper_id)
                        if norm_s_id in matching_seeds:
                            cand_to_cited_seed_ids[cand_norm_id].add(s.paper_id)
                    if not cand_to_cited_seed_ids[cand_norm_id] and normalized_seeds:
                        cand_to_cited_seed_ids[cand_norm_id].add(normalized_seeds[0].paper_id)
            except Exception as e:
                logger.warning("Error fetching forward citations: %s", e)
                status = "partial_failure"

        # Apply forward budget cap
        recent_advancements = recent_advancements[:max_forward]

        # Step 4: Partition seeds from discovered candidates and deduplicate
        seed_dois_clean = {clean_doi(s.doi) for s in normalized_seeds if s.doi}
        seed_paper_ids_set = {s.paper_id for s in normalized_seeds if s.paper_id}

        def is_seed(cand: PaperCandidate) -> bool:
            if cand.paper_id in seed_paper_ids_set:
                return True
            if cand.doi and clean_doi(cand.doi) in seed_dois_clean:
                return True
            return False

        discovered = foundational_candidates + recent_advancements
        deduped_discovered = deduplicate_candidates(discovered)
        strictly_discovered = [c for c in deduped_discovered if not is_seed(c)]

        # Step 5: Directed CitationEdges
        citation_edges: List[CitationEdge] = []

        # Backward edges: seed references foundational candidate
        for cand in strictly_discovered:
            if cand.topological_role == "foundational":
                cand_norm_id = self._normalize_oa_id(cand.paper_id)
                citing_seeds = ref_to_seed_ids.get(cand_norm_id)
                if citing_seeds:
                    for s_id in citing_seeds:
                        citation_edges.append(
                            CitationEdge(
                                source_id=s_id,
                                target_id=cand.paper_id,
                                direction="referenced_by",
                            )
                        )
                elif normalized_seeds:
                    citation_edges.append(
                        CitationEdge(
                            source_id=normalized_seeds[0].paper_id,
                            target_id=cand.paper_id,
                            direction="referenced_by",
                        )
                    )

        # Forward edges: recent advancement cites seed
        for cand in strictly_discovered:
            if cand.topological_role == "recent_advancement":
                cand_norm_id = self._normalize_oa_id(cand.paper_id)
                cited_seeds = cand_to_cited_seed_ids.get(cand_norm_id)
                if cited_seeds:
                    for s_id in cited_seeds:
                        citation_edges.append(
                            CitationEdge(
                                source_id=s_id,
                                target_id=cand.paper_id,
                                direction="cites",
                            )
                        )
                elif normalized_seeds:
                    citation_edges.append(
                        CitationEdge(
                            source_id=normalized_seeds[0].paper_id,
                            target_id=cand.paper_id,
                            direction="cites",
                        )
                    )

        return SnowballResult(
            seed_paper_ids=[s.paper_id for s in normalized_seeds],
            seeds=normalized_seeds,
            discovered_candidates=strictly_discovered,
            citation_edges=citation_edges,
            direction=direction,
            status=status,
            co_citation_matrix=dict(ref_counter),
        )
