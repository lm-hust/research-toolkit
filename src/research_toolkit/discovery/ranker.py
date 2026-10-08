"""
src/research_toolkit/discovery/ranker.py
Composite scoring and two-tier stratified selection engine.
Conforms to CONTEXT.md and ADR-0001.
"""

from __future__ import annotations

import math
import re
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

from research_toolkit.discovery.models import (
    AssessmentRecord,
    PaperCandidate,
    SelectionResult,
    clean_doi,
)
from research_toolkit.discovery.venue_registry import VenueRegistry


def extract_primary_author(paper: PaperCandidate) -> str:
    """Extracts normalized first author last name / team identifier."""
    if not paper.authors:
        return ""
    for raw in paper.authors:
        author = raw.strip()
        if not author:
            continue
        if "," in author:
            last = author.split(",")[0].strip().lower()
        else:
            parts = author.split()
            last = parts[-1].lower() if parts else ""
        norm_last = re.sub(r"[^a-z0-9]", "", last)
        if norm_last:
            return norm_last
    return ""


class Ranker:
    """
    Computes composite ranking scores and performs flexible multi-modal selection.
    Conforms to CONTEXT.md and ADR-0004.
    """

    def __init__(
        self,
        current_year: int = 2026,
        w_rel: float = 0.40,
        w_cite: float = 0.35,
        w_venue: float = 0.25,
        w_topo: float = 0.20,
        c_cap: float = 50.0,
        i_cap: float = 15.0,
        if_cap: float = 20.0,
        topo_cap: float = 5.0,
        beta_review: float = 0.20,
        venue_registry: Optional[VenueRegistry] = None,
    ):
        self.current_year = current_year
        self.w_rel = w_rel
        self.w_cite = w_cite
        self.w_venue = w_venue
        self.w_topo = w_topo
        self.c_cap = c_cap
        self.i_cap = i_cap
        self.if_cap = if_cap
        self.topo_cap = topo_cap
        self.beta_review = beta_review
        self.venue_registry = venue_registry if venue_registry is not None else VenueRegistry()

    def score(self, p: PaperCandidate) -> float:
        age = max(self.current_year - (p.year or self.current_year), 1)

        # 1. Citation velocity saturation
        c_vel = p.citation_count / age
        s_cite_raw = min(1.0, math.log1p(c_vel) / math.log1p(self.c_cap))

        if p.influential_citation_count > 0:
            i_vel = p.influential_citation_count / age
            s_inf = min(1.0, math.log1p(i_vel) / math.log1p(self.i_cap))
            s_cite = 0.65 * s_cite_raw + 0.35 * s_inf
        else:
            s_cite = s_cite_raw

        # 2. Venue quality (max of OpenAlex 2-yr citedness and offline/cached VenueRegistry impact)
        source_id = p.external_ids.get("openalex_source_id") if p.external_ids else None
        local_impact = (
            self.venue_registry.get_impact(p.venue, source_id=source_id)
            if self.venue_registry
            else 0.0
        )
        effective_impact = max(p.venue_impact, local_impact)
        if effective_impact > 0:
            p.venue_impact = effective_impact
            s_venue = min(1.0, math.log1p(effective_impact) / math.log1p(self.if_cap))
        else:
            s_venue = 0.15  # Baseline for unindexed preprint/unknown venue

        # 3. Topological centrality & co-citation score
        if p.co_citation_count > 0:
            s_topo = min(1.0, math.log1p(p.co_citation_count) / math.log1p(self.topo_cap))
            p.topological_score = round(s_topo, 4)
        else:
            s_topo = 0.0
            p.topological_score = 0.0

        # 4. Review paper boost with age decay
        b_review = 0.0
        if p.is_review:
            decay = math.exp(-0.15 * max(0, age - 1))
            b_review = self.beta_review * decay

        composite = (
            self.w_rel * p.relevance_score
            + self.w_cite * s_cite
            + self.w_venue * s_venue
            + self.w_topo * s_topo
            + b_review
        )
        p.composite_score = round(composite, 4)
        return p.composite_score

    def rank_and_select(
        self,
        candidates: List[PaperCandidate],
        top_k: int = 8,
        sort_by: str = "composite",
        min_cites: int = 0,
        year_range: Optional[Tuple[int, int]] = None,
        peer_reviewed_only: bool = False,
    ) -> List[PaperCandidate]:
        """
        Ranks and filters candidates by specified sorting mode and qualification thresholds.
        Conforms to ADR-0004 and ADR-0005.
        """
        filtered = list(candidates)

        # 1. Hard filters
        if min_cites > 0:
            filtered = [c for c in filtered if (c.citation_count or 0) >= min_cites]

        if year_range:
            min_y, max_y = year_range
            filtered = [c for c in filtered if c.year and min_y <= c.year <= max_y]

        if peer_reviewed_only:
            filtered = [c for c in filtered if not c.is_preprint]

        # 2. Score all remaining candidates
        for c in filtered:
            self.score(c)

        # 3. Sort according to mode
        mode = sort_by.lower()
        if mode == "citations":
            filtered.sort(
                key=lambda x: (x.citation_count or 0, x.composite_score), reverse=True
            )
        elif mode == "recent":
            filtered.sort(
                key=lambda x: (x.year or 0, x.citation_count or 0, x.composite_score), reverse=True
            )
        elif mode == "topological":
            filtered.sort(
                key=lambda x: (x.co_citation_count or 0, x.composite_score), reverse=True
            )
        else:  # default 'composite'
            filtered.sort(key=lambda x: x.composite_score, reverse=True)

        return filtered[:top_k]

    def score_breakdown(
        self,
        p: PaperCandidate,
        batch_max_cites: int = 100,
    ) -> Dict[str, float]:
        """
        Computes composite ranking formula breakdown conforming to Ticket #42:
        Score = 0.50 * S_rel + 0.25 * S_cite + 0.15 * S_venue + 0.10 * S_recency
        """
        # S_rel: relevance score in [0.0, 1.0]
        s_rel = min(1.0, max(0.0, float(p.relevance_score or 0.0)))

        # S_cite: log-normalized citation count: log(1 + cites) / log(1 + max(batch_max_cites, 100))
        cites = max(0, p.citation_count or 0)
        denom_cite = math.log1p(max(batch_max_cites, 100))
        s_cite = min(1.0, max(0.0, math.log1p(cites) / denom_cite)) if denom_cite > 0 else 0.0

        # S_venue: venue impact score in [0.0, 1.0] (via VenueRegistry, fallback 0.5 if unknown)
        source_id = p.external_ids.get("openalex_source_id") if p.external_ids else None
        local_impact = (
            self.venue_registry.get_impact(p.venue, source_id=source_id)
            if self.venue_registry
            else 0.0
        )
        effective_impact = max(p.venue_impact or 0.0, local_impact)
        if effective_impact > 1.0:
            s_venue = min(1.0, max(0.0, math.log1p(effective_impact) / math.log1p(self.if_cap)))
        elif 0.0 < effective_impact <= 1.0:
            s_venue = float(effective_impact)
        else:
            s_venue = 0.5  # fallback 0.5 if unknown

        # S_recency: max(0.0, 1.0 - 0.1 * (current_year - year))
        year = p.year or self.current_year
        s_recency = min(1.0, max(0.0, 1.0 - 0.1 * (self.current_year - year)))

        composite = 0.50 * s_rel + 0.25 * s_cite + 0.15 * s_venue + 0.10 * s_recency
        return {
            "s_rel": round(s_rel, 4),
            "s_cite": round(s_cite, 4),
            "s_venue": round(s_venue, 4),
            "s_recency": round(s_recency, 4),
            "composite": round(composite, 4),
        }

    def select(
        self,
        candidates: List[PaperCandidate],
        requested_n: int = 10,
        assessments: Optional[Union[List[AssessmentRecord], Dict[str, AssessmentRecord]]] = None,
        batch_id: Optional[str] = None,
        strategy: str = "composite_mmr",
        diversity_discount: float = 0.7,
        topic: Optional[str] = None,
    ) -> SelectionResult:
        """
        Executes eligibility gating, composite scoring, and greedy MMR diversity selection.
        Conforms to Ticket #42.
        """
        # 1. Index assessments
        assessment_map: Dict[str, AssessmentRecord] = {}
        if assessments:
            rec_iter = assessments.values() if isinstance(assessments, dict) else assessments
            for r in rec_iter:
                assessment_map[r.paper_id] = r
                c_doi = clean_doi(r.paper_id)
                if c_doi:
                    assessment_map[c_doi] = r
                    assessment_map[f"doi:{c_doi}"] = r

        def get_assessment(cand: PaperCandidate) -> Optional[AssessmentRecord]:
            if cand.paper_id in assessment_map:
                return assessment_map[cand.paper_id]
            if cand.doi:
                c_doi = clean_doi(cand.doi)
                if c_doi and c_doi in assessment_map:
                    return assessment_map[c_doi]
                if c_doi and f"doi:{c_doi}" in assessment_map:
                    return assessment_map[f"doi:{c_doi}"]
            if cand.arxiv_id:
                if cand.arxiv_id in assessment_map:
                    return assessment_map[cand.arxiv_id]
                if f"arxiv:{cand.arxiv_id}" in assessment_map:
                    return assessment_map[f"arxiv:{cand.arxiv_id}"]
            return None

        # 2. Eligibility gating
        eligible_candidates: List[PaperCandidate] = []
        for cand in candidates:
            assessment_rec = get_assessment(cand)
            if assessment_rec is not None:
                if assessment_rec.decision == "unrelated":
                    continue  # Strictly hard-excluded
                if assessment_rec.decision == "pending":
                    continue  # Excluded from automatic ranked top-n selection
                if assessment_rec.decision == "related":
                    if assessment_rec.relevance_score is None or assessment_rec.relevance_score <= 0.0:
                        continue  # Excluded if relevance score is 0
                    cand.relevance_score = assessment_rec.relevance_score
                    eligible_candidates.append(cand)
                else:
                    continue
            else:
                # No assessment record
                if cand.relevance_score <= 0.0:
                    continue  # Hard-excluded when score is 0
                eligible_candidates.append(cand)

        # 3. Composite ranking score calculation for eligible candidates
        batch_max_cites = max([c.citation_count for c in candidates] or [100])
        breakdowns: Dict[str, Dict[str, float]] = {}
        for cand in eligible_candidates:
            bd = self.score_breakdown(cand, batch_max_cites=batch_max_cites)
            cand.composite_score = bd["composite"]
            breakdowns[cand.paper_id] = bd

        # 4. Diversity / MMR Team Soft Penalty greedy selection
        pool = list(eligible_candidates)
        selected_papers: List[PaperCandidate] = []
        selected_scores: Dict[str, float] = {}
        selected_reasons: Dict[str, str] = {}
        selected_primary_authors: Set[str] = set()

        while len(selected_papers) < requested_n and pool:
            best_cand: Optional[PaperCandidate] = None
            best_effective_score = -1.0
            best_discounted = False
            best_author = ""
            best_key: Tuple[float, float, int, int, str] = (-1.0, -1.0, 0, 0, "")

            for cand in pool:
                author = extract_primary_author(cand)
                is_discounted = bool(author and author in selected_primary_authors)
                multiplier = diversity_discount if is_discounted else 1.0
                effective_score = round(cand.composite_score * multiplier, 4)

                cand_key = (
                    effective_score,
                    cand.composite_score,
                    cand.citation_count or 0,
                    cand.year or 0,
                    cand.paper_id,
                )
                if best_cand is None or cand_key > best_key:
                    best_cand = cand
                    best_effective_score = effective_score
                    best_discounted = is_discounted
                    best_author = author
                    best_key = cand_key

            if best_cand is None:
                break

            pool.remove(best_cand)
            selected_papers.append(best_cand)
            if best_author:
                selected_primary_authors.add(best_author)
            selected_scores[best_cand.paper_id] = best_effective_score

            cand_assessment = get_assessment(best_cand)
            bd = breakdowns.get(best_cand.paper_id, {})
            score_desc = f"rel={bd.get('s_rel', 0):.2f}, cite={bd.get('s_cite', 0):.2f}, ven={bd.get('s_venue', 0):.2f}, rec={bd.get('s_recency', 0):.2f}"
            base_reason = (
                cand_assessment.reason
                if (cand_assessment and cand_assessment.reason)
                else f"Composite score {best_cand.composite_score:.4f} ({score_desc})"
            )
            if best_discounted:
                selected_reasons[best_cand.paper_id] = (
                    f"{base_reason} (MMR diversity discount {diversity_discount}x applied; "
                    f"primary author '{best_author}' already represented; adjusted score: {best_effective_score:.4f})"
                )
            else:
                selected_reasons[best_cand.paper_id] = base_reason

        # 5. Fallback when eligible candidates < requested_n
        if len(selected_papers) < requested_n:
            topic_disp = f"'{topic}' " if topic else ""
            warning_msg = (
                f"Warning: only {len(selected_papers)} eligible candidates found for topic "
                f"{topic_disp}(requested n={requested_n})"
            )
            sys.stderr.write(f"{warning_msg}\n")
            sys.stderr.flush()
            status = "insufficient_candidates" if selected_papers else "empty"
        else:
            status = "completed"

        return SelectionResult(
            batch_id=batch_id,
            strategy=strategy,
            requested_n=requested_n,
            selected_papers=selected_papers,
            selected_paper_ids=[p.paper_id for p in selected_papers],
            scores=selected_scores,
            reasons=selected_reasons,
            status=status,
        )

