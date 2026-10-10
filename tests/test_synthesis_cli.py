"""
tests/test_synthesis_cli.py
Unit tests for CLI commands: sync-notebook.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from research_toolkit.cli import STATE_FILE, cli
from research_toolkit.synthesis.models import (
    NotebookInfo,
    NotebookSource,
)
from research_toolkit.zotero.models import CheckpointReport, ZoteroItem


class TestSynthesisCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"active_collection": "research/gnn"}), encoding="utf-8")

    @patch("research_toolkit.cli.get_default_gateway")
    @patch("research_toolkit.cli.ZoteroManager")
    def test_sync_notebook_blocked_by_checkpoint_without_allow_partial(
        self, mock_zotero_cls, mock_gateway_getter
    ):
        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_gateway = MagicMock()
        mock_gateway_getter.return_value = mock_gateway

        # Checkpoint has 1 missing paper
        mock_report = CheckpointReport(
            collection_key="COL_GNN",
            collection_name="research/gnn",
            total_items=2,
            ready_items=[ZoteroItem(key="K1", title="Paper 1", has_pdf=True, pdf_path="/p1.pdf")],
            missing_items=[ZoteroItem(key="K2", title="Paper 2", has_pdf=False)],
        )
        mock_zotero.scan_collection_checkpoint.return_value = mock_report

        result = self.runner.invoke(cli, ["sync-notebook"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("FulltextCheckpoint", result.output)
        self.assertIn("--allow-partial", result.output)
        mock_gateway.create_notebook.assert_not_called()

    @patch("research_toolkit.cli.get_default_gateway")
    @patch("research_toolkit.cli.ZoteroManager")
    def test_sync_notebook_succeeds_with_allow_partial(
        self, mock_zotero_cls, mock_gateway_getter
    ):
        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_gateway = MagicMock()
        mock_gateway_getter.return_value = mock_gateway

        mock_report = CheckpointReport(
            collection_key="COL_GNN",
            collection_name="research/gnn",
            total_items=2,
            ready_items=[ZoteroItem(key="K1", title="Paper 1", has_pdf=True, pdf_path="/tmp/p1.pdf")],
            missing_items=[ZoteroItem(key="K2", title="Paper 2", has_pdf=False)],
        )
        mock_zotero.scan_collection_checkpoint.return_value = mock_report
        mock_gateway.create_notebook.return_value = NotebookInfo(id="nb_test_123", title="research/gnn")
        mock_gateway.upload_source.return_value = NotebookSource(id="src_1", title="p1.pdf")

        result = self.runner.invoke(cli, ["sync-notebook", "--allow-partial"])

        self.assertEqual(result.exit_code, 0)
        mock_gateway.create_notebook.assert_called_once_with("research/gnn")
        mock_gateway.upload_source.assert_called_once()
        self.assertIn("nb_test_123", result.output)


if __name__ == "__main__":
    unittest.main()
