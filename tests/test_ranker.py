"""
tests/test_ranker.py
Tests for composite scoring and two-tier stratified selection.
"""

import io
import sys
import unittest

from research_toolkit.discovery.models import (
    AssessmentRecord,
    PaperCandidate,
)
from research_toolkit.discovery.ranker import Ranker


class TestRanker(unittest.TestCase):
    def setUp(self):
        self.ranker = Ranker(current_year=2026)

    def test_composite_score_calculation(self):
        """Verifies mathematical scoring with citation velocity, venue impact, and review boost."""
        paper = PaperCandidate(
            paper_id="p1",
            title="Survey on Modern Deep Learning",
            year=2024,
            citation_count=200,
            influential_citation_count=30,
            venue="Nature Reviews",
            venue_impact=18.0,  # High venue
            is_review=True,
            relevance_score=0.9
        )
        score = self.ranker.score(paper)
        self.assertGreater(score, 0.7)
        self.assertEqual(paper.composite_score, score)

    def test_review_paper_decay(self):
        """Older reviews should have lower review boost than fresh reviews."""
        fresh_review = PaperCandidate(
            paper_id="fresh",
            title="Recent Survey (2025)",
            year=2025,
            citation_count=100,
            is_review=True,
            relevance_score=0.8
        )
        old_review = PaperCandidate(
            paper_id="old",
            title="Old Survey (2015)",
            year=2015,
            citation_count=100,
            is_review=True,
            relevance_score=0.8
        )
        score_fresh = self.ranker.score(fresh_review)
        score_old = self.ranker.score(old_review)
        self.assertGreater(score_fresh, score_old)

    def test_review_paper_boost(self):
        """Review papers receive a composite score boost over equivalent research papers."""
        research = PaperCandidate(
            paper_id="res",
            title="Regular Research Paper",
            year=2024,
            citation_count=100,
            is_review=False,
            relevance_score=0.85
        )
        review = PaperCandidate(
            paper_id="rev",
            title="Review Paper",
            year=2024,
            citation_count=100,
            is_review=True,
            relevance_score=0.85
        )
        selected = self.ranker.rank_and_select([research, review], top_k=2)
        self.assertEqual(selected[0].paper_id, "rev")
        self.assertGreater(review.composite_score, research.composite_score)


    def test_sort_by_citations(self):
        """When sort_by='citations', results should strictly sort by citation_count descending."""
        candidates = [
            PaperCandidate(paper_id="low", title="Low Cite", year=2024, citation_count=5),
            PaperCandidate(paper_id="high", title="High Cite", year=2020, citation_count=500),
            PaperCandidate(paper_id="mid", title="Mid Cite", year=2022, citation_count=50),
        ]
        selected = self.ranker.rank_and_select(candidates, top_k=3, sort_by="citations")
        self.assertEqual([p.paper_id for p in selected], ["high", "mid", "low"])

    def test_sort_by_recent(self):
        """When sort_by='recent', results should sort primarily by publication year descending."""
        candidates = [
            PaperCandidate(paper_id="old", title="Old Paper", year=2020, citation_count=1000),
            PaperCandidate(paper_id="fresh", title="Fresh Paper", year=2025, citation_count=5),
            PaperCandidate(paper_id="mid", title="Mid Paper", year=2023, citation_count=50),
        ]
        selected = self.ranker.rank_and_select(candidates, top_k=3, sort_by="recent")
        self.assertEqual([p.paper_id for p in selected], ["fresh", "mid", "old"])

    def test_min_cites_filtering(self):
        """Filters out candidate papers with citation count below min_cites threshold."""
        candidates = [
            PaperCandidate(paper_id="p1", title="Paper 1", citation_count=100),
            PaperCandidate(paper_id="p2", title="Paper 2", citation_count=2),
            PaperCandidate(paper_id="p3", title="Paper 3", citation_count=20),
        ]
        selected = self.ranker.rank_and_select(candidates, top_k=5, min_cites=10)
        self.assertEqual([p.paper_id for p in selected], ["p1", "p3"])

    def test_peer_reviewed_filtering(self):
        """Filters out preprints when peer_reviewed_only is True."""
        candidates = [
            PaperCandidate(paper_id="arxiv", title="arXiv Paper", venue="arXiv", citation_count=50),
            PaperCandidate(paper_id="journal", title="IEEE Paper", venue="IEEE Trans", citation_count=20),
        ]
        selected = self.ranker.rank_and_select(candidates, top_k=5, peer_reviewed_only=True)
        self.assertEqual([p.paper_id for p in selected], ["journal"])

    def test_year_range_filtering(self):
        """Filters papers outside the specified (min_year, max_year) interval."""
        candidates = [
            PaperCandidate(paper_id="too_old", title="2018 Paper", year=2018, citation_count=100),
            PaperCandidate(paper_id="valid", title="2022 Paper", year=2022, citation_count=100),
            PaperCandidate(paper_id="too_new", title="2026 Paper", year=2026, citation_count=100),
        ]
        selected = self.ranker.rank_and_select(candidates, top_k=5, year_range=(2020, 2024))
        self.assertEqual([p.paper_id for p in selected], ["valid"])

    def test_composite_global_ranking_without_forced_review_lock(self):
        """Reviews get composite score bonus, but do not override globally higher scoring research papers."""
        breakthrough = PaperCandidate(
            paper_id="breakthrough",
            title="Massive Breakthrough",
            year=2024,
            citation_count=500,
            relevance_score=0.98,
            is_review=False
        )
        obscure_review = PaperCandidate(
            paper_id="review",
            title="Obscure Survey",
            year=2026,
            citation_count=0,
            relevance_score=0.5,
            is_review=True
        )
        selected = self.ranker.rank_and_select([obscure_review, breakthrough], top_k=2, sort_by="composite")
        self.assertEqual(selected[0].paper_id, "breakthrough")

    def test_topological_score_boost(self):
        """Papers with high co_citation_count receive a topological boost."""
        paper_isolated = PaperCandidate(
            paper_id="isolated",
            title="Isolated Candidate",
            year=2024,
            citation_count=50,
            relevance_score=0.8,
            co_citation_count=0,
        )
        paper_cocited = PaperCandidate(
            paper_id="cocited",
            title="Co-cited Candidate",
            year=2024,
            citation_count=50,
            relevance_score=0.8,
            co_citation_count=4,
            topological_role="foundational",
        )

        score_iso = self.ranker.score(paper_isolated)
        score_co = self.ranker.score(paper_cocited)

        self.assertGreater(score_co, score_iso)
        self.assertGreater(paper_cocited.topological_score, 0.0)

    def test_topological_sorting_mode(self):
        """Mode sort_by='topological' orders candidates primarily by co_citation_count."""
        p1 = PaperCandidate(paper_id="p1", title="Low Co-cite", co_citation_count=1, citation_count=1000)
        p2 = PaperCandidate(paper_id="p2", title="High Co-cite", co_citation_count=5, citation_count=50)

        selected = self.ranker.rank_and_select([p1, p2], top_k=2, sort_by="topological")
        self.assertEqual(selected[0].paper_id, "p2")
        self.assertEqual(selected[1].paper_id, "p1")

    def test_composite_ranking_formula_breakdown(self):
        """Verifies Ticket #42 formula: Score = 0.50*S_rel + 0.25*S_cite + 0.15*S_venue + 0.10*S_recency."""
        paper = PaperCandidate(
            paper_id="p_test",
            title="Test Paper",
            year=2024,
            citation_count=100,
            venue="Unknown Venue",
            venue_impact=0.0,
            relevance_score=0.8,
        )
        # S_rel = 0.8
        # S_cite = log(1+100) / log(1+max(100, 100)) = 1.0
        # S_venue = fallback 0.5 (unknown)
        # S_recency = 1.0 - 0.1 * (2026 - 2024) = 0.8
        # Expected: 0.50*0.8 + 0.25*1.0 + 0.15*0.5 + 0.10*0.8 = 0.40 + 0.25 + 0.075 + 0.08 = 0.8050
        breakdown = self.ranker.score_breakdown(paper, batch_max_cites=100)
        self.assertAlmostEqual(breakdown["s_rel"], 0.8, places=4)
        self.assertAlmostEqual(breakdown["s_cite"], 1.0, places=4)
        self.assertAlmostEqual(breakdown["s_venue"], 0.5, places=4)
        self.assertAlmostEqual(breakdown["s_recency"], 0.8, places=4)
        self.assertAlmostEqual(breakdown["composite"], 0.8050, places=4)

    def test_eligibility_gating_unrelated_and_pending(self):
        """Candidates with decision='unrelated' or score=0 or pending are excluded from selection."""
        p_unrelated = PaperCandidate(
            paper_id="p_unrel",
            title="Unrelated Breakthrough",
            year=2025,
            citation_count=5000,
            relevance_score=0.9,
            venue="Nature",
        )
        p_pending = PaperCandidate(
            paper_id="p_pend",
            title="Pending Candidate",
            year=2024,
            citation_count=500,
            relevance_score=0.8,
        )
        p_zero = PaperCandidate(
            paper_id="p_zero",
            title="Zero Relevance Candidate",
            year=2025,
            citation_count=300,
            relevance_score=0.0,
        )
        p_eligible = PaperCandidate(
            paper_id="p_elig",
            title="Eligible Graph Learning",
            year=2024,
            citation_count=50,
            relevance_score=0.85,
        )

        assessments = [
            AssessmentRecord(
                paper_id="p_unrel",
                decision="unrelated",
                relevance_score=0.0,
                reason="Different domain entirely",
            ),
            AssessmentRecord(
                paper_id="p_pend",
                decision="pending",
                relevance_score=None,
                reason="Under review",
            ),
            AssessmentRecord(
                paper_id="p_elig",
                decision="related",
                relevance_score=0.85,
                reason="Highly relevant",
            ),
        ]

        result = self.ranker.select(
            candidates=[p_unrelated, p_pending, p_zero, p_eligible],
            requested_n=5,
            assessments=assessments,
        )
        # Only p_eligible should be selected
        self.assertEqual(len(result.selected_papers), 1)
        self.assertEqual(result.selected_papers[0].paper_id, "p_elig")
        self.assertNotIn("p_unrel", result.selected_paper_ids)
        self.assertNotIn("p_pend", result.selected_paper_ids)
        self.assertNotIn("p_zero", result.selected_paper_ids)

    def test_mmr_diversity_team_soft_penalty(self):
        """Candidates sharing primary first author with already-selected papers receive 0.7 discount."""
        p_vaswani_1 = PaperCandidate(
            paper_id="v1",
            title="Attention Is All You Need",
            authors=["Vaswani, Ashish", "Shazeer, Noam"],
            year=2024,
            citation_count=100,
            relevance_score=0.95,
        )
        p_vaswani_2 = PaperCandidate(
            paper_id="v2",
            title="Transformers at Scale",
            authors=["Ashish Vaswani", "Parmar, Niki"],
            year=2024,
            citation_count=90,
            relevance_score=0.90,
        )
        p_lecun = PaperCandidate(
            paper_id="lecun",
            title="Self-Supervised Learning",
            authors=["LeCun, Yann"],
            year=2024,
            citation_count=60,
            relevance_score=0.85,
        )

        # With greedy MMR:
        # Round 1: v1 is chosen. Primary author 'vaswani' is recorded.
        # Round 2: v2 has author 'vaswani', so its score is discounted by 0.7.
        # lecun has author 'lecun', score is untouched.
        # lecun should beat discounted v2!
        result = self.ranker.select(
            candidates=[p_vaswani_1, p_vaswani_2, p_lecun],
            requested_n=3,
        )
        self.assertEqual(len(result.selected_papers), 3)
        self.assertEqual(result.selected_papers[0].paper_id, "v1")
        self.assertEqual(result.selected_papers[1].paper_id, "lecun")
        self.assertEqual(result.selected_papers[2].paper_id, "v2")

        # Verify reasons note the diversity penalty on v2
        self.assertIn("MMR diversity discount", result.reasons["v2"])

    def test_fallback_when_eligible_fewer_than_requested_n(self):
        """When fewer than n candidates are eligible, strictly return only eligible and warn to stderr."""
        p_elig_1 = PaperCandidate(
            paper_id="p1",
            title="Paper 1",
            relevance_score=0.8,
            year=2024,
        )
        p_elig_2 = PaperCandidate(
            paper_id="p2",
            title="Paper 2",
            relevance_score=0.7,
            year=2024,
        )
        p_unrel = PaperCandidate(
            paper_id="p_bad",
            title="Paper Bad",
            relevance_score=0.0,
            year=2024,
        )

        captured_stderr = io.StringIO()
        old_stderr = sys.stderr
        try:
            sys.stderr = captured_stderr
            result = self.ranker.select(
                candidates=[p_elig_1, p_elig_2, p_unrel],
                requested_n=5,
                topic="Graph Learning",
            )
        finally:
            sys.stderr = old_stderr

        # Strictly return only 2 eligible candidates (not 5, no padding)
        self.assertEqual(len(result.selected_papers), 2)
        self.assertEqual(result.selected_paper_ids, ["p1", "p2"])
        self.assertEqual(result.status, "insufficient_candidates")

        # Warning emitted to stderr
        stderr_output = captured_stderr.getvalue()
        self.assertIn("Warning: only 2 eligible candidates found for topic", stderr_output)
        self.assertIn("(requested n=5)", stderr_output)


if __name__ == "__main__":
    unittest.main()
