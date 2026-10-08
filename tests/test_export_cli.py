"""
tests/test_export_cli.py
Tests for the export CLI atom command.
Conforms to Ticket #44:
- Consumes SelectionResult OR PaperCandidateBatch from stdin JSON stream OR --batch <path_or_id>.
- Syncs selected papers to target Zotero collection (or active session collection).
- Enforces Zotero domain invariants: personal library scope (/users/<user_id>/),
  non-destructive attachment, canonical clean DOI match first before normalized title.
- Clean stream separation: stdout emits JSON summary; stderr emits Rich status table,
  collection URL, and confirmation messages.
- Supports --dry-run and --quiet flags.
- Pipeline chaining: search ... | rank ... | export ...
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from research_toolkit.cli import cli
from research_toolkit.discovery.models import (
    PaperCandidate,
    PaperCandidateBatch,
    SelectionResult,
)
from research_toolkit.zotero.client import ZoteroClient
from research_toolkit.zotero.manager import ZoteroManager
from research_toolkit.zotero.models import SyncResult, ZoteroCollection


class TestExportCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.p1 = PaperCandidate(
            paper_id="doi:10.1000/attention",
            title="Attention Is All You Need",
            authors=["Vaswani, Ashish", "Shazeer, Noam"],
            year=2024,
            citation_count=200,
            relevance_score=0.95,
            venue="NeurIPS",
            doi="10.1000/attention",
            pdf_url="https://arxiv.org/pdf/1706.03762.pdf",
        )
        self.p2 = PaperCandidate(
            paper_id="doi:10.1000/transformers_scale",
            title="Transformers at Scale",
            authors=["Vaswani, Ashish", "Parmar, Niki"],
            year=2024,
            citation_count=180,
            relevance_score=0.90,
            venue="ICML",
            doi="10.1000/transformers_scale",
        )
        self.p_no_doi = PaperCandidate(
            paper_id="hash:nodoi12345",
            title="Preprint Without A DOI",
            authors=["Anonymous, Researcher"],
            year=2023,
            citation_count=12,
            relevance_score=0.80,
            venue="arXiv",
            arxiv_id="2301.00001",
        )
        self.batch = PaperCandidateBatch(
            batch_id="batch_test_export_001",
            query="Deep Learning Architecture",
            papers=[self.p1, self.p2, self.p_no_doi],
            status="completed",
        )
        self.selection = SelectionResult(
            batch_id="batch_test_export_001",
            strategy="composite_mmr",
            requested_n=2,
            selected_papers=[self.p1, self.p2],
            selected_paper_ids=[self.p1.paper_id, self.p2.paper_id],
            scores={self.p1.paper_id: 0.95, self.p2.paper_id: 0.90},
            status="completed",
        )

        self.mock_col = ZoteroCollection(
            key="COL_TARGET",
            name="DL Research",
            user_id="12345",
        )
        self.mock_sync_result = SyncResult(
            collection_key="COL_TARGET",
            collection_name="DL Research",
            collection_url="https://www.zotero.org/users/12345/collections/COL_TARGET",
            created_count=2,
            reused_count=0,
            created_items=[
                {"key": "ITEM_001", "data": {"title": self.p1.title, "DOI": self.p1.doi}},
                {"key": "ITEM_002", "data": {"title": self.p2.title, "DOI": self.p2.doi}},
            ],
            reused_items=[],
        )

    @patch("research_toolkit.cli.ZoteroManager")
    def test_export_cli_stdin_selection_result(self, mock_zotero_cls):
        """Consumes SelectionResult from stdin and outputs JSON summary to stdout."""
        mock_mgr = MagicMock()
        mock_zotero_cls.return_value = mock_mgr
        mock_mgr.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        sel_json = self.selection.to_json(indent=2)
        result = self.runner.invoke(
            cli,
            ["export", "--collection", "DL Research"],
            input=sel_json,
        )
        self.assertEqual(result.exit_code, 0, msg=f"CLI failed: {result.output}")

        # stdout must be valid JSON summary
        stdout_text = result.stdout.strip()
        self.assertTrue(stdout_text.startswith("{"))
        self.assertTrue(stdout_text.endswith("}"))
        summary = json.loads(stdout_text)

        self.assertEqual(summary["collection_key"], "COL_TARGET")
        self.assertEqual(summary["collection_name"], "DL Research")
        self.assertEqual(summary["total_count"], 2)
        self.assertEqual(summary["created_count"], 2)
        self.assertEqual(summary["reused_count"], 0)
        self.assertEqual(summary["synced_item_keys"], ["ITEM_001", "ITEM_002"])
        self.assertFalse(summary["dry_run"])

        # stderr must contain Rich table and confirmation
        self.assertIn("COL_TARGET", result.stderr)
        self.assertIn("https://www.zotero.org/users/12345/collections/COL_TARGET", result.stderr)

        # Verify sync_to_collection was called with 2 selected papers
        mock_mgr.sync_to_collection.assert_called_once()
        args, kwargs = mock_mgr.sync_to_collection.call_args
        self.assertEqual(args[0], "DL Research")
        self.assertEqual(len(args[1]), 2)
        self.assertEqual(args[1][0].title, self.p1.title)

    @patch("research_toolkit.cli.ZoteroManager")
    def test_export_cli_stdin_candidate_batch(self, mock_zotero_cls):
        """Consumes PaperCandidateBatch from stdin and syncs all batch papers."""
        mock_mgr = MagicMock()
        mock_zotero_cls.return_value = mock_mgr
        batch_sync_result = SyncResult(
            collection_key="COL_TARGET",
            collection_name="DL Research",
            collection_url="https://www.zotero.org/users/12345/collections/COL_TARGET",
            created_count=3,
            reused_count=0,
            created_items=[
                {"key": "ITEM_001"},
                {"key": "ITEM_002"},
                {"key": "ITEM_003"},
            ],
            reused_items=[],
        )
        mock_mgr.sync_to_collection.return_value = (self.mock_col, batch_sync_result)

        batch_json = self.batch.to_json(indent=2)
        result = self.runner.invoke(
            cli,
            ["export", "--collection", "DL Research"],
            input=batch_json,
        )
        self.assertEqual(result.exit_code, 0, msg=f"CLI failed: {result.output}")

        summary = json.loads(result.stdout.strip())
        self.assertEqual(summary["total_count"], 3)
        self.assertEqual(summary["synced_item_keys"], ["ITEM_001", "ITEM_002", "ITEM_003"])

        mock_mgr.sync_to_collection.assert_called_once()
        args, _ = mock_mgr.sync_to_collection.call_args
        self.assertEqual(len(args[1]), 3)

    @patch("research_toolkit.cli.ZoteroManager")
    def test_export_cli_batch_file_argument(self, mock_zotero_cls):
        """Loads SelectionResult from --batch file path."""
        mock_mgr = MagicMock()
        mock_zotero_cls.return_value = mock_mgr
        mock_mgr.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "selection.json"
            file_path.write_text(self.selection.to_json(indent=2), encoding="utf-8")

            result = self.runner.invoke(
                cli,
                ["export", "--batch", str(file_path), "--collection", "DL Research"],
            )
            self.assertEqual(result.exit_code, 0)
            summary = json.loads(result.stdout.strip())
            self.assertEqual(summary["collection_key"], "COL_TARGET")

    @patch("research_toolkit.cli.ZoteroManager")
    def test_export_cli_batch_id_resolution(self, mock_zotero_cls):
        """Resolves batch ID from .research/batches/ directory."""
        mock_mgr = MagicMock()
        mock_zotero_cls.return_value = mock_mgr
        mock_mgr.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            batch_file = Path(tmpdir) / "my_custom_batch_123.json"
            batch_file.write_text(self.batch.to_json(indent=2), encoding="utf-8")

            with patch.dict(os.environ, {"RESEARCH_BATCH_DIR": tmpdir}):
                result = self.runner.invoke(
                    cli,
                    ["export", "--batch", "my_custom_batch_123", "--collection", "DL Research"],
                )
                self.assertEqual(result.exit_code, 0)
                summary = json.loads(result.stdout.strip())
                self.assertEqual(summary["collection_key"], "COL_TARGET")

    @patch("research_toolkit.cli.ZoteroManager")
    def test_export_cli_collection_fallback_to_session(self, mock_zotero_cls):
        """Defaults --collection to active collection in session.json when omitted."""
        mock_mgr = MagicMock()
        mock_zotero_cls.return_value = mock_mgr
        mock_mgr.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "session.json"
            session_file.write_text(
                json.dumps({"active_collection": "Session Active Collection"}),
                encoding="utf-8",
            )
            with patch("research_toolkit.cli.STATE_FILE", session_file):
                result = self.runner.invoke(
                    cli,
                    ["export"],
                    input=self.selection.to_json(),
                )
                self.assertEqual(result.exit_code, 0)
                mock_mgr.sync_to_collection.assert_called_once()
                args, _ = mock_mgr.sync_to_collection.call_args
                self.assertEqual(args[0], "Session Active Collection")

    def test_export_cli_missing_collection_error(self):
        """Raises error when collection is omitted and no session collection is active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "session.json"
            session_file.write_text("{}", encoding="utf-8")
            with patch("research_toolkit.cli.STATE_FILE", session_file):
                result = self.runner.invoke(
                    cli,
                    ["export"],
                    input=self.selection.to_json(),
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("collection", result.output.lower())

    def test_export_cli_missing_batch_or_stdin_error(self):
        """Raises error when neither stdin nor --batch is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_file = Path(tmpdir) / "session.json"
            session_file.write_text("{}", encoding="utf-8")
            with patch("research_toolkit.cli.STATE_FILE", session_file):
                result = self.runner.invoke(
                    cli,
                    ["export", "--collection", "DL Research"],
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("batch", result.output.lower())

    @patch("research_toolkit.cli.ZoteroManager")
    def test_export_cli_dry_run(self, mock_zotero_cls):
        """Previews sync in --dry-run without modifying Zotero."""
        mock_mgr = MagicMock()
        mock_zotero_cls.return_value = mock_mgr
        dry_sync_result = SyncResult(
            collection_key="dry-run-preview",
            collection_name="DL Research",
            collection_url="",
            created_count=2,
            reused_count=0,
            created_items=[{"key": "dry_run_1"}, {"key": "dry_run_2"}],
            reused_items=[],
        )
        dry_col = ZoteroCollection(key="dry-run-preview", name="DL Research", user_id="12345")
        mock_mgr.sync_to_collection.return_value = (dry_col, dry_sync_result)

        result = self.runner.invoke(
            cli,
            ["export", "--collection", "DL Research", "--dry-run"],
            input=self.selection.to_json(),
        )
        self.assertEqual(result.exit_code, 0)

        # stdout must indicate dry_run=True
        summary = json.loads(result.stdout.strip())
        self.assertTrue(summary["dry_run"])
        self.assertEqual(summary["collection_key"], "dry-run-preview")

        # stderr must display dry-run diagnostic message
        self.assertIn("[dry-run]", result.stderr)

        # Verify sync_to_collection called with dry_run=True
        mock_mgr.sync_to_collection.assert_called_once()
        _, kwargs = mock_mgr.sync_to_collection.call_args
        self.assertTrue(kwargs.get("dry_run"))

    @patch("research_toolkit.cli.ZoteroManager")
    def test_export_cli_quiet(self, mock_zotero_cls):
        """Suppresses stderr progress and table output when --quiet is set."""
        mock_mgr = MagicMock()
        mock_zotero_cls.return_value = mock_mgr
        mock_mgr.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        result = self.runner.invoke(
            cli,
            ["export", "--collection", "DL Research", "--quiet"],
            input=self.selection.to_json(),
        )
        self.assertEqual(result.exit_code, 0)

        # stderr must be completely empty
        self.assertEqual(result.stderr.strip(), "")

        # stdout still has pure JSON summary
        summary = json.loads(result.stdout.strip())
        self.assertEqual(summary["total_count"], 2)

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_export_cli_pipeline_chaining_search_rank_export(
        self, mock_discovery_cls, mock_zotero_cls
    ):
        """Tests complete UNIX pipe workflow: search ... | rank ... | export ..."""
        mock_discovery = MagicMock()
        mock_discovery_cls.return_value = mock_discovery
        mock_discovery.search.return_value = self.batch
        mock_discovery.format_table.return_value = "Search Table"

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Search atom
            res_search = self.runner.invoke(
                cli,
                ["search", "Deep Learning", "--data-dir", tmpdir],
            )
            self.assertEqual(res_search.exit_code, 0)
            search_stdout = res_search.stdout.strip()
            self.assertTrue(search_stdout.startswith("{"))

            # 2. Rank atom
            res_rank = self.runner.invoke(
                cli,
                ["rank", "-n", "2"],
                input=search_stdout,
            )
            self.assertEqual(res_rank.exit_code, 0)
            rank_stdout = res_rank.stdout.strip()
            self.assertTrue(rank_stdout.startswith("{"))

            # 3. Export atom
            res_export = self.runner.invoke(
                cli,
                ["export", "--collection", "DL Research"],
                input=rank_stdout,
            )
            self.assertEqual(res_export.exit_code, 0)
            export_stdout = res_export.stdout.strip()
            self.assertTrue(export_stdout.startswith("{"))

            summary = json.loads(export_stdout)
            self.assertEqual(summary["collection_key"], "COL_TARGET")
            self.assertEqual(summary["total_count"], 2)

    def test_zotero_manager_sync_to_collection_invariants(self):
        """Verifies ZoteroManager invariants: DOI match first, title fallback only when no DOI, and personal scope."""
        mock_client = MagicMock(spec=ZoteroClient)
        mock_client.library_type = "user"
        mock_client.user_id = "12345"

        existing_by_doi = {
            "key": "EXIST_DOI_KEY",
            "version": 1,
            "data": {"title": "Attention Is All You Need", "DOI": "10.1000/attention", "collections": []},
        }
        existing_by_title = {
            "key": "EXIST_TITLE_KEY",
            "version": 2,
            "data": {"title": "Preprint Without A DOI", "DOI": "", "collections": []},
        }

        def mock_find(doi=None, title=None):
            if doi and "10.1000/attention" in doi:
                return existing_by_doi
            if not doi and title and "preprint without a doi" in title.lower():
                return existing_by_title
            return None

        mock_client.find_existing_item.side_effect = mock_find
        mock_client.add_item_to_collection.return_value = True
        mock_client.create_items.return_value = [{"key": "NEW_ITEM_KEY"}]
        mock_client.get_or_create_collection.return_value = ZoteroCollection(
            key="COL_123", name="AI Col", user_id="12345"
        )

        manager = ZoteroManager(client=mock_client)
        col, sync_res = manager.sync_to_collection(
            collection_name="AI Col",
            candidates=[self.p1, self.p2, self.p_no_doi],
            auto_download_oa=False,
        )

        self.assertEqual(col.key, "COL_123")
        # p1 matched by DOI (reused)
        # p2 has DOI 10.1000/transformers_scale which was not found -> created new
        # p_no_doi has no DOI -> matched by title (reused)
        self.assertEqual(sync_res.created_count, 1)
        self.assertEqual(sync_res.reused_count, 2)
        self.assertEqual(len(sync_res.synced_item_keys), 3)

        # Non-destructive collection addition called for p1 and p_no_doi
        self.assertEqual(mock_client.add_item_to_collection.call_count, 2)
        # create_items called once for p2
        mock_client.create_items.assert_called_once()


if __name__ == "__main__":
    unittest.main()
