"""
tests/test_checkpoint_cli.py
Unit tests for the research-toolkit checkpoint CLI command.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from research_toolkit.cli import cli, STATE_FILE
from research_toolkit.zotero.models import CheckpointReport, ZoteroItem


class TestCheckpointCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    @patch("research_toolkit.cli.ZoteroManager")
    def test_checkpoint_displays_report_with_collection_arg(self, mock_manager_cls):
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager

        mock_report = CheckpointReport(
            collection_key="COL_MOCK",
            collection_name="Graph Neural Networks",
            total_items=2,
            ready_items=[
                ZoteroItem(key="K1", title="Paper One", has_pdf=True, pdf_path="/storage/K1/p.pdf")
            ],
            missing_items=[
                ZoteroItem(key="K2", title="Paper Two", doi="10.1000/two", has_pdf=False)
            ],
            reconciled_duplicates=0,
        )
        mock_manager.scan_collection_checkpoint.return_value = mock_report
        mock_manager.format_checkpoint_report.return_value = "📋 FULLTEXT CHECKPOINT REPORT: 'Graph Neural Networks'\nReady: 1/2\nMissing: Paper Two"

        result = self.runner.invoke(cli, ["checkpoint", "--collection", "COL_MOCK", "--status"])

        self.assertEqual(result.exit_code, 0)
        mock_manager.scan_collection_checkpoint.assert_called_once_with("COL_MOCK")
        self.assertIn("FULLTEXT CHECKPOINT REPORT", result.output)
        self.assertIn("Ready: 1/2", result.output)

    @patch("research_toolkit.cli.ZoteroManager")
    def test_checkpoint_uses_saved_state_when_no_collection_flag(self, mock_manager_cls):
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager

        # Write mock state file
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"active_collection": "SAVED_COL"}), encoding="utf-8")

        mock_report = CheckpointReport(
            collection_key="SAVED_COL",
            collection_name="Saved Research",
            total_items=1,
            ready_items=[],
            missing_items=[],
        )
        mock_manager.scan_collection_checkpoint.return_value = mock_report
        mock_manager.format_checkpoint_report.return_value = "📋 FULLTEXT CHECKPOINT: Saved Research"

        result = self.runner.invoke(cli, ["checkpoint"])

        self.assertEqual(result.exit_code, 0)
        mock_manager.scan_collection_checkpoint.assert_called_once_with("SAVED_COL")
        self.assertIn("FULLTEXT CHECKPOINT", result.output)


if __name__ == "__main__":
    unittest.main()
