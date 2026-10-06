"""
src/research_toolkit/discovery/ranker.py
Composite scoring and two-tier stratified selection engine.
Conforms to CONTEXT.md and ADR-0001.
"""

from __future__ import annotations

import math
from typing import List, Optional

from research_toolkit.discovery.models import PaperCandidate


class Ranker:
    """
    Computes composite ranking scores and performs stratified two-tier selection
    ensuring review papers lead the selection quota.
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
    ):
        self.current_year = current_year
        self.w_rel = w_rel
        self.w_cite = w_cite
        self.w_venue = w_venue
        self.c_cap = c_cap
        self.i_cap = i_cap
        self.if_cap = if_cap
        self.beta_review = beta_review

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

        # 2. Venue quality (OpenAlex 2-yr citedness proxy for JCR IF)
        if p.venue_impact > 0:
            s_venue = min(1.0, math.log1p(p.venue_impact) / math.log1p(self.if_cap))
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
        self, candidates: List[PaperCandidate], top_k: int = 8
    ) -> List[PaperCandidate]:
        """
        Two-tier stratified selection:
        Guarantees top 25-30% slots for leading ReviewPapers,
        followed by top composite breakthrough research papers.
        """
        for c in candidates:
            self.score(c)

        reviews = [c for c in candidates if c.is_review]
        research = [c for c in candidates if not c.is_review]

        reviews.sort(key=lambda x: x.composite_score, reverse=True)
        research.sort(key=lambda x: x.composite_score, reverse=True)

        k_review = max(1, min(len(reviews), math.ceil(top_k * 0.25))) if reviews else 0
        k_research = top_k - k_review

        selected_reviews = reviews[:k_review]
        selected_research = research[:k_research]

        # Leading reviews placed first
        final_selection = selected_reviews + selected_research

        # Fill remaining slots if either category was underpopulated
        if len(final_selection) < top_k:
            remaining = [c for c in candidates if c not in final_selection]
            remaining.sort(key=lambda x: x.composite_score, reverse=True)
            final_selection.extend(remaining[: (top_k - len(final_selection))])

        return final_selection[:top_k]
