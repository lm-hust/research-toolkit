"""
tests/test_search_cli.py
Tests for the search CLI command as an atomic literature retrieval command.
Conforms to Ticket #41 acceptance criteria:
- Pure retrieval atom (Semantic Scholar + OpenAlex, normalization, deduplication).
- No implicit citation snowballing or Zotero writes.
- Stream separation: stdout emits pure PaperCandidateBatch JSON; stderr receives Rich table and progress.
- File-first atomic persistence to .research/batches/<batch_id>.json.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from research_toolkit.cli import cli
from research_toolkit.discovery.models import (
    PaperCandidate,
    PaperCandidateBatch,
)


class TestSearchCli(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.mock_candidate = PaperCandidate(
            paper_id="doi:10.1000/mock_survey",
            title="A Comprehensive Survey of GNNs",
            year=2024,
            authors=["Vaswani, Ashish"],
            citation_count=150,
            is_review=True,
            doi="10.1000/mock_survey",
            source_platform="openalex",
            composite_score=0.88,
            external_ids={"openalex_id": "W12345"},
        )
        self.mock_batch = PaperCandidateBatch(
            batch_id="batch_mock_001",
            query="Graph Neural Networks",
            papers=[self.mock_candidate],
            source_observations={
                "semantic_scholar": {"count": 1, "status": "success"},
                "openalex": {"count": 1, "status": "success"},
            },
            status="completed",
        )

    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_retrieval_atom_no_zotero_side_effects(self, mock_service_cls):
        """Verifies search operates as pure retrieval atom without invoking ZoteroManager."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch
        mock_service.format_table.return_value = "RANK | TYPE | TITLE\n1 | [REV] | A Comprehensive Survey of GNNs"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(
                cli,
                ["search", "Graph Neural Networks", "--data-dir", tmpdir],
            )
            self.assertEqual(result.exit_code, 0)

            # Ensure ZoteroManager was not imported or called in search
            self.assertNotIn("ZoteroManager", str(mock_service.mock_calls))

            # Machine-readable JSON emitted on stdout
            data = json.loads(result.output[result.output.find("{") :])
            self.assertEqual(data["batch_id"], "batch_mock_001")
            self.assertEqual(data["status"], "completed")

    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_stream_separation_stdout_pure_json_stderr_rich_table(self, mock_service_cls):
        """Verifies stdout has pure parseable JSON and stderr receives Rich table and progress."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch
        mock_service.format_table.return_value = "RANK | TYPE | TITLE\n1 | [REV] | A Comprehensive Survey of GNNs"

        runner = self.runner
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                ["search", "Graph Neural Networks", "--data-dir", tmpdir],
            )
            self.assertEqual(result.exit_code, 0)

            # stdout must be cleanly parseable as PaperCandidateBatch JSON with zero table text
            stdout_str = result.stdout.strip()
            self.assertTrue(stdout_str.startswith("{"))
            self.assertTrue(stdout_str.endswith("}"))
            batch_data = json.loads(stdout_str)
            self.assertEqual(batch_data["batch_id"], "batch_mock_001")
            self.assertEqual(len(batch_data["papers"]), 1)
            self.assertEqual(batch_data["papers"][0]["paper_id"], "doi:10.1000/mock_survey")
            self.assertNotIn("RANK | TYPE | TITLE", result.stdout)

            # stderr must contain human-readable progress and Rich table
            self.assertIn("Searching literature for: 'Graph Neural Networks'...", result.stderr)
            self.assertIn("RANK | TYPE | TITLE", result.stderr)
            self.assertIn("Persisted batch 'batch_mock_001'", result.stderr)

    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_with_json_flag(self, mock_service_cls):
        """Verifies --json flag forces pure PaperCandidateBatch JSON emission."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        runner = self.runner
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                ["search", "Graph Neural Networks", "--json", "--data-dir", tmpdir],
            )
            self.assertEqual(result.exit_code, 0)
            data = json.loads(result.stdout.strip())
            self.assertEqual(data["batch_id"], "batch_mock_001")
            self.assertEqual(data["query"], "Graph Neural Networks")
            self.assertEqual(data["papers"][0]["doi"], "10.1000/mock_survey")

    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_with_quiet_flag(self, mock_service_cls):
        """Verifies --quiet flag suppresses stderr output completely."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        runner = self.runner
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                ["search", "Graph Neural Networks", "--quiet", "--data-dir", tmpdir],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.stderr, "")
            # stdout still has valid JSON
            data = json.loads(result.stdout.strip())
            self.assertEqual(data["batch_id"], "batch_mock_001")

    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_atomic_persistence_to_file(self, mock_service_cls):
        """Verifies batch is saved atomically to file and matches PaperCandidateBatch schema."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(
                cli,
                [
                    "search",
                    "Graph Neural Networks",
                    "--batch-dir",
                    tmpdir,
                    "--batch-id",
                    "batch_persistent_999",
                ],
            )
            self.assertEqual(result.exit_code, 0)

            expected_file = Path(tmpdir) / "batch_mock_001.json"
            self.assertTrue(expected_file.is_file())

            # Load and verify batch
            loaded_batch = PaperCandidateBatch.load(expected_file)
            self.assertEqual(loaded_batch.batch_id, "batch_mock_001")
            self.assertEqual(len(loaded_batch.papers), 1)
            self.assertEqual(loaded_batch.papers[0].title, "A Comprehensive Survey of GNNs")

            # Check that no temporary files remain
            temp_files = [f for f in Path(tmpdir).iterdir() if f.name.startswith(".")]
            self.assertEqual(temp_files, [])

    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_forwards_filtering_options(self, mock_service_cls):
        """Verifies search flags (--limit, --min-cites, --year, --peer-reviewed) are passed to service."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(
                cli,
                [
                    "search",
                    "Deep Learning",
                    "--limit",
                    "5",
                    "--min-cites",
                    "25",
                    "--year",
                    "2021-2025",
                    "--peer-reviewed",
                    "--data-dir",
                    tmpdir,
                ],
            )
            self.assertEqual(result.exit_code, 0)
            mock_service.search.assert_called_once_with(
                query="Deep Learning",
                limit=5,
                min_cites=25,
                year_range=(2021, 2025),
                peer_reviewed_only=True,
                batch_id=None,
            )

    @patch("research_toolkit.cli.DiscoveryService")
    def test_search_handles_zero_candidates(self, mock_service_cls):
        """When 0 candidates found, emits valid empty batch JSON to stdout and message to stderr."""
        empty_batch = PaperCandidateBatch(
            batch_id="batch_empty_000",
            query="Nonexistent Topic",
            papers=[],
            status="completed",
        )
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = empty_batch

        runner = self.runner
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                cli,
                ["search", "Nonexistent Topic", "--data-dir", tmpdir],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("No matching papers found.", result.stderr)

            data = json.loads(result.stdout.strip())
            self.assertEqual(data["batch_id"], "batch_empty_000")
            self.assertEqual(data["papers"], [])

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_expand_command_retains_behavior(self, mock_service_cls, mock_zotero_cls):
        """Verifies expand command still functions without disruption."""
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
