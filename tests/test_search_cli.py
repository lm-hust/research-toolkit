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

        # Default mode: outputs candidate table, ID, and URL
        result = self.runner.invoke(cli, ["search", "Graph Neural Networks"])
        self.assertEqual(result.exit_code, 0)
        mock_zotero.sync_to_collection.assert_called_once()
        self.assertIn("ID: COL_GNN_123", result.output)
        self.assertIn("URL: https://www.zotero.org/users/12345/collections/COL_GNN_123", result.output)
        self.assertIn("RANK | TYPE | TITLE", result.output)

        # Quiet mode: does NOT output paper candidate table
        result_quiet = self.runner.invoke(cli, ["search", "Graph Neural Networks", "--quiet"])
        self.assertEqual(result_quiet.exit_code, 0)
        self.assertNotIn("RANK | TYPE | TITLE", result_quiet.output)

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

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_passes_sorting_and_filtering_flags(self, mock_service_cls, mock_zotero_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search_and_rank.return_value = [self.mock_candidate]
        mock_service.format_table.return_value = "RANK | TYPE | TITLE"

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, [{"key": "ITEM_1"}])

        result = self.runner.invoke(
            cli,
            [
                "search",
                "Deep Learning",
                "--sort",
                "citations",
                "--min-cites",
                "25",
                "--year",
                "2021-2025",
                "--peer-reviewed",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        mock_service.search_and_rank.assert_called_once_with(
            "Deep Learning",
            top_k=8,
            sort_by="citations",
            min_cites=25,
            year_range=(2021, 2025),
            peer_reviewed_only=True,
            snowball=True,
        )

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_with_no_snowball(self, mock_service_cls, mock_zotero_cls):
        """Passing --no-snowball forwards snowball=False to service."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search_and_rank.return_value = [self.mock_candidate]

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, [{"key": "ITEM_1"}])

        result = self.runner.invoke(cli, ["search", "Deep Learning", "--no-snowball", "--yes"])
        self.assertEqual(result.exit_code, 0)
        mock_service.search_and_rank.assert_called_once_with(
            "Deep Learning",
            top_k=8,
            sort_by="composite",
            min_cites=0,
            year_range=None,
            peer_reviewed_only=False,
            snowball=False,
        )

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_expand_command(self, mock_service_cls, mock_zotero_cls):
        """Verifies expand command fetches collection items, runs snowballer, and syncs."""
        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_col_obj = MagicMock()
        mock_col_obj.key = "COL_123"
        mock_seed = PaperCandidate(paper_id="seed_a", title="Seed A", doi="10.1000/a", topological_role="seed")
        mock_zotero.get_collection_candidates.return_value = [mock_seed]
        mock_zotero.sync_to_collection.return_value = (mock_col_obj, MagicMock())

        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_snowball_res = MagicMock()
        mock_core_candidate = PaperCandidate(
            paper_id="core_1",
            title="Core Paper Found Via Graph",
            topological_role="foundational",
            co_citation_count=3,
        )
        mock_snowball_res.all_candidates = [mock_core_candidate]
        mock_service.snowballer.snowball.return_value = mock_snowball_res
        mock_service.ranker.rank_and_select.return_value = [mock_core_candidate]

        result = self.runner.invoke(cli, ["expand", "my-seeds", "--yes"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Successfully expanded and synced 1 papers", result.output)
        mock_zotero.sync_to_collection.assert_called_once_with("my-seeds", [mock_core_candidate])


if __name__ == "__main__":
    unittest.main()
