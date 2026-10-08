"""
tests/test_candidate_batch.py
Tests for PaperCandidateBatch, PaperCandidate primary identity, and atomic batch persistence.
Conforms to Ticket #41 data contract requirements.
"""

import tempfile
import unittest
from pathlib import Path

from research_toolkit.discovery.models import (
    PaperCandidate,
    PaperCandidateBatch,
    clean_doi,
    compute_paper_id,
)


class TestCandidateBatchContracts(unittest.TestCase):
    def test_clean_doi(self):
        """Clean DOI normalizes various formats to lowercase DOI without prefix/URL."""
        self.assertEqual(clean_doi("10.1000/182"), "10.1000/182")
        self.assertEqual(clean_doi("doi:10.1000/182"), "10.1000/182")
        self.assertEqual(clean_doi("DOI: 10.1000/182/"), "10.1000/182")
        self.assertEqual(clean_doi("https://doi.org/10.1000/182"), "10.1000/182")
        self.assertEqual(clean_doi("http://dx.doi.org/10.48550/ARXIV.1706.03762"), "10.48550/arxiv.1706.03762")
        self.assertIsNone(clean_doi(None))
        self.assertIsNone(clean_doi(""))

    def test_compute_paper_id(self):
        """compute_paper_id uses clean DOI or deterministic hash fallback."""
        self.assertEqual(compute_paper_id(doi="10.1000/182"), "doi:10.1000/182")
        h1 = compute_paper_id(title="Survey of AI", authors=["Smith, John"], year=2024)
        h2 = compute_paper_id(title="survey of ai", authors=["John Smith"], year=2024)
        self.assertTrue(h1.startswith("hash:"))
        self.assertEqual(h1, h2)

    def test_paper_primary_identity_with_doi(self):
        """Candidate with DOI uses lowercase clean DOI (doi:10.xxx/...) as primary identity."""
        p = PaperCandidate(
            title="Attention Is All You Need",
            doi="https://doi.org/10.48550/arXiv.1706.03762",
            authors=["Vaswani, Ashish", "Shazeer, Noam"],
            year=2017,
        )
        self.assertEqual(p.paper_id, "doi:10.48550/arxiv.1706.03762")
        self.assertEqual(p.primary_id, "doi:10.48550/arxiv.1706.03762")
        self.assertEqual(p.doi, "10.48550/arxiv.1706.03762")

    def test_paper_primary_identity_fallback_hash_when_doi_missing(self):
        """Candidate without DOI falls back to deterministic hash of normalized title, author, and year."""
        p1 = PaperCandidate(
            title="Graph Neural Networks for Power Systems!",
            authors=["Alice J. Smith", "Bob Jones"],
            year=2024,
        )
        p2 = PaperCandidate(
            title="graph neural networks for power systems",
            authors=["Smith, Alice J."],
            year=2024,
        )
        # Should start with hash:
        self.assertTrue(p1.paper_id.startswith("hash:"))
        self.assertEqual(p1.paper_id, p2.paper_id)

        # Different title or author yields different deterministic hash
        p3 = PaperCandidate(
            title="Another Title",
            authors=["Alice J. Smith"],
            year=2024,
        )
        self.assertNotEqual(p1.paper_id, p3.paper_id)

    def test_paper_candidate_serialization(self):
        """PaperCandidate converts to/from dict and JSON cleanly."""
        p = PaperCandidate(
            title="Test Paper",
            doi="10.1000/test",
            authors=["Author One"],
            year=2023,
            citation_count=42,
            venue="Nature",
            external_ids={"s2_id": "s2_123", "openalex_id": "W123"},
        )
        d = p.to_dict()
        self.assertEqual(d["paper_id"], "doi:10.1000/test")
        self.assertEqual(d["title"], "Test Paper")
        self.assertEqual(d["external_ids"]["s2_id"], "s2_123")
        self.assertEqual(d["external_ids"]["openalex_id"], "W123")

        p_restored = PaperCandidate.from_dict(d)
        self.assertEqual(p_restored.paper_id, p.paper_id)
        self.assertEqual(p_restored.title, p.title)
        self.assertEqual(p_restored.external_ids, p.external_ids)

        json_str = p.to_json()
        p_json_restored = PaperCandidate.from_json(json_str)
        self.assertEqual(p_json_restored.paper_id, p.paper_id)

    def test_batch_schema_and_serialization(self):
        """PaperCandidateBatch supports query/topic, source_observations, status, and serialization."""
        p = PaperCandidate(
            title="Survey Paper",
            doi="10.1000/survey",
            year=2024,
        )
        batch = PaperCandidateBatch(
            batch_id="batch_test_001",
            query="Graph Neural Networks",
            papers=[p],
            source_observations={
                "semantic_scholar": {"count": 1, "status": "success"},
                "openalex": {"count": 1, "status": "success"},
            },
            status="completed",
        )
        self.assertEqual(batch.topic, "Graph Neural Networks")
        self.assertEqual(len(batch), 1)

        d = batch.to_dict()
        self.assertEqual(d["batch_id"], "batch_test_001")
        self.assertEqual(d["query"], "Graph Neural Networks")
        self.assertEqual(d["status"], "completed")
        self.assertEqual(len(d["papers"]), 1)

        batch_from_dict = PaperCandidateBatch.from_dict(d)
        self.assertEqual(batch_from_dict.batch_id, batch.batch_id)
        self.assertEqual(batch_from_dict.query, batch.query)
        self.assertEqual(batch_from_dict.status, "completed")
        self.assertEqual(len(batch_from_dict.papers), 1)

        json_str = batch.to_json()
        batch_from_json = PaperCandidateBatch.from_json(json_str)
        self.assertEqual(batch_from_json.batch_id, batch.batch_id)
        self.assertEqual(batch_from_json.papers[0].paper_id, "doi:10.1000/survey")

    def test_batch_statuses_supported(self):
        """PaperCandidateBatch accepts status completed, partial_failure, and budget_truncated."""
        for st in ("completed", "partial_failure", "budget_truncated"):
            batch = PaperCandidateBatch(query="test", status=st)
            self.assertEqual(batch.status, st)

    def test_atomic_file_persistence(self):
        """PaperCandidateBatch.save atomically persists file to directory using temporary file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            batch = PaperCandidateBatch(
                batch_id="batch_atomic_123",
                query="Atomic Storage",
                papers=[PaperCandidate(title="Paper 1", doi="10.1000/p1")],
            )
            saved_path = batch.save(directory=tmpdir)
            self.assertTrue(saved_path.is_file())
            self.assertEqual(saved_path.name, "batch_atomic_123.json")

            # Verify no leftover temporary files in directory
            all_files = list(Path(tmpdir).iterdir())
            self.assertEqual(all_files, [saved_path])

            # Load and verify
            loaded = PaperCandidateBatch.load(saved_path)
            self.assertEqual(loaded.batch_id, "batch_atomic_123")
            self.assertEqual(loaded.papers[0].paper_id, "doi:10.1000/p1")


if __name__ == "__main__":
    unittest.main()
