"""
tests/test_ranker.py
Tests for composite scoring and two-tier stratified selection.
"""

import unittest
from research_toolkit.discovery.models import PaperCandidate
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

    def test_two_tier_selection_guarantees_review_quota(self):
        """When selecting top 8 papers, at least 25% (2 slots) must be top reviews."""
        candidates = []
        # Create 10 breakthrough research papers with very high citations
        for i in range(10):
            candidates.append(
                PaperCandidate(
                    paper_id=f"res_{i}",
                    title=f"Breakthrough Research Paper {i}",
                    year=2022,
                    citation_count=5000 + i * 500,
                    is_review=False,
                    relevance_score=0.95
                )
            )

        # Create 3 review papers with moderate citations
        for i in range(3):
            candidates.append(
                PaperCandidate(
                    paper_id=f"rev_{i}",
                    title=f"Comprehensive Review Paper {i}",
                    year=2024,
                    citation_count=150 + i * 50,
                    is_review=True,
                    relevance_score=0.85
                )
            )

        selected = self.ranker.rank_and_select(candidates, top_k=8)
        self.assertEqual(len(selected), 8)

        # The leading papers must include top reviews
        review_count = sum(1 for p in selected if p.is_review)
        self.assertGreaterEqual(review_count, 2)  # at least 25% of 8 = 2
        # And review paper should be at rank #1
        self.assertTrue(selected[0].is_review)


if __name__ == "__main__":
    unittest.main()
