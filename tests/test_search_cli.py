"""
tests/test_search_cli.py
Tests for the search CLI command and --dry-run option.
"""

import unittest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from research_toolkit.cli import cli
from research_toolkit.discovery.models import PaperCandidate


class TestSearchCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_dry_run_outputs_table(self, mock_service_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        mock_candidate = PaperCandidate(
            paper_id="mock_1",
            title="A Comprehensive Survey of GNNs",
            year=2024,
            citation_count=150,
            is_review=True,
            doi="10.1000/mock_survey",
            source_platform="openalex",
            composite_score=0.88,
        )
        mock_service.search_and_rank.return_value = [mock_candidate]
        mock_service.format_table.return_value = "RANK | TYPE | TITLE\n1 | [REV] | A Comprehensive Survey of GNNs"

        result = self.runner.invoke(cli, ["search", "Graph Neural Networks", "--dry-run"])

        self.assertEqual(result.exit_code, 0)
        mock_service.search_and_rank.assert_called_once_with("Graph Neural Networks", top_k=8)
        self.assertIn("A Comprehensive Survey of GNNs", result.output)


if __name__ == "__main__":
    unittest.main()
