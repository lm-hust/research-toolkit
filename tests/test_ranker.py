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


if __name__ == "__main__":
    unittest.main()
