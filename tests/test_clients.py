"""
tests/test_clients.py
Tests for Semantic Scholar and OpenAlex retrieval clients.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from research_toolkit.discovery.clients import (
    OpenAlexClient,
    SemanticScholarClient,
    reconstruct_openalex_abstract,
)


class TestClients(unittest.TestCase):
    def test_reconstruct_openalex_abstract(self):
        """Verifies abstract reconstruction from inverted position index."""
        inverted_index = {
            "Graph": [0],
            "neural": [1],
            "networks": [2],
            "are": [3],
            "powerful": [4],
            "tools": [5]
        }
        reconstructed = reconstruct_openalex_abstract(inverted_index)
        self.assertEqual(reconstructed, "Graph neural networks are powerful tools")

    @patch("urllib.request.urlopen")
    def test_semantic_scholar_client_parse(self, mock_urlopen):
        """Verifies parsing of Semantic Scholar API response into PaperCandidate."""
        s2_response = {
            "data": [
                {
                    "paperId": "s2_abc123",
                    "title": "A Survey on Graph Representation Learning",
                    "year": 2023,
                    "citationCount": 450,
                    "influentialCitationCount": 60,
                    "publicationTypes": ["Review"],
                    "openAccessPdf": {"url": "https://example.com/survey.pdf", "status": "GOLD"},
                    "externalIds": {"DOI": "10.1016/j.survey.2023.01", "ArXiv": "2301.12345"},
                    "venue": "IEEE TPAMI",
                    "abstract": "A comprehensive survey of representations."
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(s2_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = SemanticScholarClient(api_key="test_key")
        results = client.search("Graph Representation", limit=5)

        self.assertEqual(len(results), 1)
        c = results[0]
        self.assertEqual(c.paper_id, "s2_abc123")
        self.assertEqual(c.title, "A Survey on Graph Representation Learning")
        self.assertTrue(c.is_review)
        self.assertEqual(c.doi, "10.1016/j.survey.2023.01")
        self.assertEqual(c.arxiv_id, "2301.12345")
        self.assertEqual(c.pdf_url, "https://example.com/survey.pdf")

    @patch("urllib.request.urlopen")
    def test_openalex_client_parse(self, mock_urlopen):
        """Verifies parsing of OpenAlex API response and abstract reconstruction."""
        oa_response = {
            "results": [
                {
                    "id": "https://openalex.org/W998877",
                    "doi": "https://doi.org/10.1038/s41586-021-03819-2",
                    "title": "Geometric deep learning",
                    "publication_year": 2021,
                    "cited_by_count": 1200,
                    "type": "review",
                    "abstract_inverted_index": {
                        "Geometric": [0],
                        "deep": [1],
                        "learning": [2],
                        "unifies": [3],
                        "networks": [4]
                    },
                    "primary_location": {
                        "pdf_url": "https://nature.com/article.pdf",
                        "source": {
                            "display_name": "Nature",
                            "summary_stats": {"2yr_mean_citedness": 18.5}
                        }
                    }
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(oa_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = OpenAlexClient()
        results = client.search("Geometric Deep Learning", limit=5)

        self.assertEqual(len(results), 1)
        c = results[0]
        self.assertEqual(c.title, "Geometric deep learning")
        self.assertEqual(c.doi, "10.1038/s41586-021-03819-2")
        self.assertEqual(c.abstract, "Geometric deep learning unifies networks")
        self.assertTrue(c.is_review)
        self.assertEqual(c.venue_impact, 18.5)

    @patch("urllib.request.urlopen")
    def test_semantic_scholar_filters_out_books(self, mock_urlopen):
        """Verifies Semantic Scholar client excludes Books and BookSections."""
        s2_response = {
            "data": [
                {
                    "paperId": "book_1",
                    "title": "Deep Learning: The Book",
                    "publicationTypes": ["Book"],
                },
                {
                    "paperId": "book_section_1",
                    "title": "Chapter 3: Optimization",
                    "publicationTypes": ["BookSection"],
                },
                {
                    "paperId": "conf_paper_1",
                    "title": "Attention Is All You Need",
                    "publicationTypes": ["Conference"],
                },
                {
                    "paperId": "journal_paper_1",
                    "title": "Deep Residual Learning",
                    "publicationTypes": ["JournalArticle"],
                },
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(s2_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = SemanticScholarClient()
        results = client.search("Deep Learning")

        paper_ids = [p.paper_id for p in results]
        self.assertNotIn("book_1", paper_ids)
        self.assertNotIn("book_section_1", paper_ids)
        self.assertIn("conf_paper_1", paper_ids)
        self.assertIn("journal_paper_1", paper_ids)

    @patch("urllib.request.urlopen")
    def test_openalex_filters_out_books(self, mock_urlopen):
        """Verifies OpenAlex client excludes book, book-chapter, book-review types."""
        oa_response = {
            "results": [
                {
                    "id": "oa_book_1",
                    "title": "Artificial Intelligence: A Modern Approach",
                    "type": "book",
                },
                {
                    "id": "oa_book_review_1",
                    "title": "Review of AI Book",
                    "type": "book-review",
                },
                {
                    "id": "oa_chapter_1",
                    "title": "Search Algorithms Chapter",
                    "type": "book-chapter",
                },
                {
                    "id": "oa_conf_1",
                    "title": "Transformer Models in Robotics",
                    "type": "proceedings-article",
                },
                {
                    "id": "oa_journal_1",
                    "title": "Advances in Neural Computation",
                    "type": "article",
                },
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(oa_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = OpenAlexClient()
        results = client.search("Artificial Intelligence")

        paper_ids = [p.paper_id for p in results]
        self.assertNotIn("oa_book_1", paper_ids)
        self.assertNotIn("oa_book_review_1", paper_ids)
        self.assertNotIn("oa_chapter_1", paper_ids)
        self.assertIn("oa_conf_1", paper_ids)
        self.assertIn("oa_journal_1", paper_ids)

    @patch("urllib.request.urlopen")
    def test_openalex_client_get_source_impact(self, mock_urlopen):
        """Verifies get_source_impact retrieves 2yr_mean_citedness via unified _request."""
        source_response = {
            "id": "https://openalex.org/S12345",
            "display_name": "IEEE Transactions on Smart Grid",
            "summary_stats": {
                "2yr_mean_citedness": 9.62
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(source_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        client = OpenAlexClient()
        impact = client.get_source_impact("https://openalex.org/S12345")
        self.assertAlmostEqual(impact, 9.62, places=2)

    def test_openalex_client_get_source_impact_invalid_id(self):
        """Returns 0.0 without network call when source ID is invalid."""
        client = OpenAlexClient()
        self.assertEqual(client.get_source_impact("invalid_source_id"), 0.0)


if __name__ == "__main__":
    unittest.main()

