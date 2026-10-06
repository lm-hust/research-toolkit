"""
tests/test_dedup.py
Tests for 3-tier paper deduplication (DOI -> ArXiv -> Fuzzy Title).
"""

import unittest
from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.dedup import Deduplicator


class TestDeduplicator(unittest.TestCase):
    def setUp(self):
        self.dedup = Deduplicator()

    def test_deduplicate_by_canonical_doi(self):
        """Papers with different DOI formatting should merge into single canonical record."""
        p1 = PaperCandidate(
            paper_id="s2_1",
            title="Attention Is All You Need",
            year=2017,
            citation_count=100000,
            doi="https://doi.org/10.48550/arXiv.1706.03762",
            source_platform="semantic_scholar"
        )
        p2 = PaperCandidate(
            paper_id="oa_1",
            title="Attention is all you need",
            year=2017,
            citation_count=105000,
            doi="10.48550/arxiv.1706.03762",
            source_platform="openalex",
            abstract="Reconstructed abstract text..."
        )

        merged = self.dedup.process([p1, p2])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].citation_count, 105000)
        self.assertEqual(merged[0].abstract, "Reconstructed abstract text...")
        self.assertEqual(merged[0].doi, "10.48550/arxiv.1706.03762")

    def test_deduplicate_by_arxiv_id_when_doi_missing(self):
        """Papers without DOIs should merge if ArXiv ID matches."""
        p1 = PaperCandidate(
            paper_id="s2_2",
            title="Language Models are Few-Shot Learners",
            year=2020,
            arxiv_id="arXiv:2005.14165v4",
            citation_count=20000
        )
        p2 = PaperCandidate(
            paper_id="oa_2",
            title="Language Models are Few-Shot Learners",
            year=2020,
            arxiv_id="2005.14165",
            citation_count=21000
        )

        merged = self.dedup.process([p1, p2])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].citation_count, 21000)
        self.assertEqual(merged[0].arxiv_id, "2005.14165")

    def test_deduplicate_by_fuzzy_title_when_ids_missing(self):
        """Papers with slight title variance within 1 publication year should merge."""
        p1 = PaperCandidate(
            paper_id="p1",
            title="Deep Residual Learning for Image Recognition.",
            year=2016,
            citation_count=150000
        )
        p2 = PaperCandidate(
            paper_id="p2",
            title="Deep residual learning for image recognition",
            year=2016,
            citation_count=160000
        )

        merged = self.dedup.process([p1, p2])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].citation_count, 160000)


if __name__ == "__main__":
    unittest.main()
