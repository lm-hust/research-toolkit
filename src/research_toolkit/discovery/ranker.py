"""
src/research_toolkit/discovery/ranker.py
Composite scoring and two-tier stratified selection engine.
Conforms to CONTEXT.md and ADR-0001.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.venue_registry import VenueRegistry


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
        c_cap: float = 50.0,
        i_cap: float = 15.0,
        if_cap: float = 20.0,
        beta_review: float = 0.20,
        venue_registry: Optional[VenueRegistry] = None,
    ):
        self.current_year = current_year
        self.w_rel = w_rel
        self.w_cite = w_cite
        self.w_venue = w_venue
        self.c_cap = c_cap
        self.i_cap = i_cap
        self.if_cap = if_cap
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

        # 3. Review paper boost with age decay
        b_review = 0.0
        if p.is_review:
            decay = math.exp(-0.15 * max(0, age - 1))
            b_review = self.beta_review * decay

        composite = (
            self.w_rel * p.relevance_score
            + self.w_cite * s_cite
            + self.w_venue * s_venue
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
        Conforms to ADR-0004.
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
        else:  # default 'composite'
            filtered.sort(key=lambda x: x.composite_score, reverse=True)

        return filtered[:top_k]
