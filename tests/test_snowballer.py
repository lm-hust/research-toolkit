"""
tests/test_snowballer.py
Tests for CitationSnowballer graph expansion engine.
Conforms to CONTEXT.md and ADR-0005.
"""

import unittest
from unittest.mock import MagicMock

from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.snowballer import CitationSnowballer, SnowballResult


class TestCitationSnowballer(unittest.TestCase):
    def setUp(self):
        self.mock_oa = MagicMock()
        self.mock_crossref = MagicMock()
        self.snowballer = CitationSnowballer(
            oa_client=self.mock_oa,
            crossref_client=self.mock_crossref,
        )

    def test_snowball_backward_and_forward_co_citation(self):
        """Verifies backward co-citation extraction and forward citation coupling."""
        # 2 seed papers
        seed1 = PaperCandidate(
            paper_id="https://openalex.org/W_seed1",
            title="Seed Paper 1",
            year=2022,
            doi="10.1000/seed1",
            referenced_works=[
                "https://openalex.org/W_found1",
                "https://openalex.org/W_found2",
                "https://openalex.org/W_other",
            ],
        )
        seed2 = PaperCandidate(
            paper_id="https://openalex.org/W_seed2",
            title="Seed Paper 2",
            year=2023,
            doi="10.1000/seed2",
            referenced_works=[
                "https://openalex.org/W_found1",  # Co-cited by both seeds!
                "https://openalex.org/W_found2",  # Co-cited by both seeds!
            ],
        )

        # Mock OpenAlex batch resolving the referenced works
        found1 = PaperCandidate(
            paper_id="https://openalex.org/W_found1",
            title="Foundational Attention Paper",
            year=2017,
            doi="10.1000/found1",
            citation_count=50000,
        )
        found2 = PaperCandidate(
            paper_id="https://openalex.org/W_found2",
            title="Foundational Transformer Paper",
            year=2018,
            doi="10.1000/found2",
            citation_count=30000,
        )
        self.mock_oa.get_works_by_ids.return_value = [found1, found2]

        # Mock forward citing works
        forward_survey = PaperCandidate(
            paper_id="https://openalex.org/W_fwd1",
            title="2025 SOTA Survey on Transformers",
            year=2025,
            doi="10.1000/fwd1",
            is_review=True,
            referenced_works=[
                "https://openalex.org/W_seed1",
                "https://openalex.org/W_seed2",
            ],
        )
        self.mock_oa.get_forward_citations.return_value = [forward_survey]

        result = self.snowballer.snowball(
            seeds=[seed1, seed2],
            min_co_citations=2,
            max_backward=10,
            max_forward=10,
        )

        self.assertIsInstance(result, SnowballResult)
        self.assertEqual(len(result.seeds), 2)
        self.assertEqual(len(result.foundational), 2)
        self.assertEqual(len(result.recent_advancements), 1)

        # Check foundational attributes
        f1 = next(c for c in result.foundational if c.doi == "10.1000/found1")
        self.assertEqual(f1.topological_role, "foundational")
        self.assertEqual(f1.co_citation_count, 2)

        # Check recent advancement attributes
        fwd = result.recent_advancements[0]
        self.assertEqual(fwd.topological_role, "recent_advancement")
        self.assertEqual(fwd.co_citation_count, 2)  # Cites both seeds

        # Deduplicated all_candidates
        self.assertEqual(len(result.all_candidates), 5)  # 2 seeds + 2 found + 1 fwd

    def test_snowball_empty_seeds(self):
        """Empty seed list returns empty result safely."""
        result = self.snowballer.snowball([])
        self.assertEqual(len(result.all_candidates), 0)
