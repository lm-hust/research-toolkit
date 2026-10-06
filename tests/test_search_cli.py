"""
tests/test_search_cli.py
Tests for the search CLI command, automatic Zotero sync, compact output, and --detail/--json flags.
"""

import json
import unittest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from research_toolkit.cli import cli
from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.zotero.models import ZoteroCollection


class TestSearchCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.mock_candidate = PaperCandidate(
            paper_id="mock_1",
            title="A Comprehensive Survey of GNNs",
            year=2024,
            citation_count=150,
            is_review=True,
            doi="10.1000/mock_survey",
            source_platform="openalex",
            composite_score=0.88,
        )
        self.mock_col = ZoteroCollection(
            key="COL_GNN_123",
            name="research/gnn-survey",
            user_id="12345",
        )

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_defaults_syncs_to_zotero_compact_output(self, mock_service_cls, mock_zotero_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search_and_rank.return_value = [self.mock_candidate]
        mock_service.format_table.return_value = "RANK | TYPE | TITLE\n1 | [REV] | A Comprehensive Survey of GNNs"

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, [{"key": "ITEM_1"}])

        result = self.runner.invoke(cli, ["search", "Graph Neural Networks"])

        self.assertEqual(result.exit_code, 0)
        mock_zotero.sync_to_collection.assert_called_once()
        # Compact mode: returns ID and URL
        self.assertIn("ID: COL_GNN_123", result.output)
        self.assertIn("URL: https://www.zotero.org/users/12345/collections/COL_GNN_123", result.output)
        # Compact mode: does NOT output paper candidate table
        self.assertNotIn("RANK | TYPE | TITLE", result.output)

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_with_detail_outputs_table(self, mock_service_cls, mock_zotero_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search_and_rank.return_value = [self.mock_candidate]
        mock_service.format_table.return_value = "RANK | TYPE | TITLE\n1 | [REV] | A Comprehensive Survey of GNNs"

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, [{"key": "ITEM_1"}])

        result = self.runner.invoke(cli, ["search", "Graph Neural Networks", "--detail"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("ID: COL_GNN_123", result.output)
        self.assertIn("URL: https://www.zotero.org/users/12345/collections/COL_GNN_123", result.output)
        # Detail mode: outputs paper candidate table
        self.assertIn("RANK | TYPE | TITLE", result.output)

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_with_json_outputs_json(self, mock_service_cls, mock_zotero_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search_and_rank.return_value = [self.mock_candidate]

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, [{"key": "ITEM_1"}])

        result = self.runner.invoke(cli, ["search", "Graph Neural Networks", "--json"])

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.output.strip())
        self.assertEqual(data["collection_id"], "COL_GNN_123")
        self.assertEqual(data["collection_url"], "https://www.zotero.org/users/12345/collections/COL_GNN_123")
        self.assertEqual(data["count"], 1)

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_with_detail_and_json_outputs_valid_json(self, mock_service_cls, mock_zotero_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search_and_rank.return_value = [self.mock_candidate]

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, [{"key": "ITEM_1"}])

        result = self.runner.invoke(cli, ["search", "Graph Neural Networks", "--detail", "--json"])

        self.assertEqual(result.exit_code, 0)
        # Must be cleanly parseable as JSON without ASCII table pollution
        data = json.loads(result.output.strip())
        self.assertEqual(data["collection_id"], "COL_GNN_123")
        self.assertIn("candidates", data)
        self.assertEqual(len(data["candidates"]), 1)
        self.assertEqual(data["candidates"][0]["title"], "A Comprehensive Survey of GNNs")

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_custom_topic_and_slugification(self, mock_service_cls, mock_zotero_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search_and_rank.return_value = [self.mock_candidate]

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, [{"key": "ITEM_1"}])

        # 1. With explicit topic
        self.runner.invoke(cli, ["search", "('AI' OR 'ML') AND robotics", "-t", "robot-learning"])
        call_args_explicit = mock_zotero.sync_to_collection.call_args[0]
        self.assertEqual(call_args_explicit[0], "research/robot-learning")

        mock_zotero.sync_to_collection.reset_mock()

        # 2. Without topic -> auto slugification of boolean query
        self.runner.invoke(cli, ["search", "('AI' OR 'ML') AND robotics"])
        call_args_auto = mock_zotero.sync_to_collection.call_args[0]
        # Should not contain quotes or parentheses
        self.assertNotIn("(", call_args_auto[0])
        self.assertNotIn(")", call_args_auto[0])
        self.assertNotIn("'", call_args_auto[0])
        self.assertTrue(call_args_auto[0].startswith("research/"))


if __name__ == "__main__":
    unittest.main()
