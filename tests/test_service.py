"""
tests/test_service.py
Tests for DiscoveryService coordinating clients, deduplication, and ranking.
"""

import unittest
from unittest.mock import MagicMock

from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.service import DiscoveryService


class TestDiscoveryService(unittest.TestCase):
    def test_search_and_rank_end_to_end(self):
        """Service queries both sources, deduplicates, and ranks with review quota."""
        mock_s2 = MagicMock()
        mock_s2.search.return_value = [
            PaperCandidate(
                paper_id="s1",
                title="GNN Survey (2024)",
                year=2024,
                citation_count=100,
                is_review=True,
                doi="10.1000/gnn_survey",
                source_platform="semantic_scholar"
            ),
            PaperCandidate(
                paper_id="s2",
                title="GCN Breakthrough",
                year=2017,
                citation_count=8000,
                is_review=False,
                doi="10.1000/gcn",
                source_platform="semantic_scholar"
            )
        ]

        mock_oa = MagicMock()
        mock_oa.search.return_value = [
            # Duplicate of s1
            PaperCandidate(
                paper_id="oa1",
                title="GNN survey (2024)",
                year=2024,
                citation_count=110,
                is_review=True,
                doi="10.1000/gnn_survey",
                source_platform="openalex",
                abstract="Full abstract text..."
            ),
            PaperCandidate(
                paper_id="oa2",
                title="Graph Attention Networks",
                year=2018,
                citation_count=6000,
                is_review=False,
                doi="10.1000/gat",
                source_platform="openalex"
            )
        ]

        service = DiscoveryService(s2_client=mock_s2, oa_client=mock_oa)
        results = service.search_and_rank("Graph Neural Networks", top_k=3)

        # Total 3 unique papers after deduplicating the survey
        self.assertEqual(len(results), 3)

        # Survey must be rank 1 due to stratified selection
        self.assertTrue(results[0].is_review)
        self.assertEqual(results[0].doi, "10.1000/gnn_survey")
        self.assertEqual(results[0].abstract, "Full abstract text...")

    def test_search_and_rank_auto_relax_retry(self):
        """When strict boolean query returns 0 candidates, auto-relaxes query and retries."""
        mock_s2 = MagicMock()
        mock_oa = MagicMock()

        # First attempt with strict query returns empty
        def s2_side_effect(q, limit):
            if '"power systems"' in q:
                return []
            # Relaxed attempt returns results
            return [
                PaperCandidate(
                    paper_id="p1",
                    title="Power Systems AI",
                    year=2024,
                    citation_count=50,
                    source_platform="semantic_scholar"
                )
            ]

        mock_s2.search.side_effect = s2_side_effect
        mock_oa.search.return_value = []

        service = DiscoveryService(s2_client=mock_s2, oa_client=mock_oa)
        query = '("power systems") AND ("energy intelligence")'
        results = service.search_and_rank(query, top_k=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Power Systems AI")
        # Verify s2 was called twice (initial + relaxed)
        self.assertEqual(mock_s2.search.call_count, 2)
        relaxed_call_arg = mock_s2.search.call_args_list[1][0][0]
        self.assertNotIn('"', relaxed_call_arg)
        self.assertNotIn("AND", relaxed_call_arg)


if __name__ == "__main__":
    unittest.main()
