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


if __name__ == "__main__":
    unittest.main()
