"""
tests/test_scout_cli.py
Tests for the scout composite CLI command and legacy search compatibility shim.
Conforms to Ticket #45 acceptance criteria:
1. 'research-toolkit scout' packages the complete literature discovery pipeline:
   Search -> Initial Rank -> Citation Snowball -> Re-Rank -> CurationCheckpoint -> Export.
2. CLI options: topic, --collection/-c, -n/--top-n, --direction, --dry-run, --json, --quiet/-q, --detail.
3. Legacy 'search' deprecation shim issuing DeprecationWarning when legacy options are invoked.
4. Consistent semantics of --json, --detail, and --dry-run across subcommands.
"""

import json
import tempfile
import unittest
import warnings
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from research_toolkit.cli import cli
from research_toolkit.discovery.models import (
    PaperCandidate,
    PaperCandidateBatch,
    SnowballResult,
)
from research_toolkit.zotero.models import SyncResult, ZoteroCollection


def make_candidate(doi: str, title: str, year: int = 2024, cites: int = 50) -> PaperCandidate:
    return PaperCandidate(
        paper_id=f"doi:{doi}",
        title=title,
        doi=doi,
        year=year,
        citation_count=cites,
        relevance_score=0.9,
        venue="NeurIPS",
        authors=["Vaswani, Ashish"],
    )


class TestScoutCliSuite(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.p_seed = make_candidate("10.1000/seed", "Attention Is All You Need", 2017, 50000)
        self.p_found = make_candidate("10.1000/found", "Foundational Work", 2015, 10000)
        self.p_found.topological_role = "foundational"
        self.p_recent = make_candidate("10.1000/recent", "Recent Frontier LLM", 2024, 100)
        self.p_recent.topological_role = "recent_advancement"

        self.mock_batch = PaperCandidateBatch(
            batch_id="batch_scout_test_01",
            query="Graph Neural Networks",
            papers=[self.p_seed],
            status="completed",
        )
        self.mock_col = ZoteroCollection(
            key="COL_SCOUT",
            name="research/cimo-gnn",
            user_id="12345",
        )
        self.mock_sync_result = SyncResult(
            collection_key="COL_SCOUT",
            collection_name="research/cimo-gnn",
            collection_url="https://www.zotero.org/users/12345/collections/COL_SCOUT",
            created_count=2,
            reused_count=0,
            created_items=[
                {"key": "ITEM_1", "data": {"title": self.p_seed.title, "DOI": self.p_seed.doi}},
                {"key": "ITEM_2", "data": {"title": self.p_found.title, "DOI": self.p_found.doi}},
            ],
            reused_items=[],
        )

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.CitationSnowballer")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_scout_end_to_end_flow(self, mock_service_cls, mock_snowballer_cls, mock_zotero_cls):
        """Verifies scout command runs Search -> Rank -> Snowball -> Re-rank -> Curation -> Export."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        mock_snowballer = MagicMock()
        mock_snowballer_cls.return_value = mock_snowballer
        mock_snowball_res = SnowballResult(
            seed_paper_ids=[self.p_seed.paper_id],
            seeds=[self.p_seed],
            discovered_candidates=[self.p_found, self.p_recent],
            direction="both",
            status="completed",
        )
        mock_snowballer.snowball.return_value = mock_snowball_res

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        result = self.runner.invoke(
            cli,
            [
                "scout",
                "Graph Neural Networks",
                "--collection",
                "research/cimo-gnn",
                "--top-n",
                "5",
                "--direction",
                "both",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        # Search called
        mock_service.search.assert_called_once()
        # Snowball called with seeds
        mock_snowballer.snowball.assert_called_once()
        # Zotero sync called
        mock_zotero.sync_to_collection.assert_called_once()

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.CitationSnowballer")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_scout_dry_run_does_not_mutate_zotero(self, mock_service_cls, mock_snowballer_cls, mock_zotero_cls):
        """Verifies scout with --dry-run previews candidate discovery without calling mutating Zotero methods."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        mock_snowballer = MagicMock()
        mock_snowballer_cls.return_value = mock_snowballer
        mock_snowball_res = SnowballResult(
            seed_paper_ids=[self.p_seed.paper_id],
            seeds=[self.p_seed],
            discovered_candidates=[self.p_found],
            direction="both",
            status="completed",
        )
        mock_snowballer.snowball.return_value = mock_snowball_res

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        result = self.runner.invoke(
            cli,
            [
                "scout",
                "Graph Neural Networks",
                "--collection",
                "research/cimo-gnn",
                "--dry-run",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        mock_zotero.sync_to_collection.assert_called_once()
        call_kwargs = mock_zotero.sync_to_collection.call_args.kwargs
        self.assertTrue(call_kwargs.get("dry_run"))

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.CitationSnowballer")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_scout_json_output(self, mock_service_cls, mock_snowballer_cls, mock_zotero_cls):
        """Verifies scout with --json emits pure JSON summary to stdout and suppresses interactive prompts."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        mock_snowballer = MagicMock()
        mock_snowballer_cls.return_value = mock_snowballer
        mock_snowballer.snowball.return_value = SnowballResult(
            seed_paper_ids=[self.p_seed.paper_id],
            seeds=[self.p_seed],
            discovered_candidates=[self.p_found],
            direction="both",
            status="completed",
        )

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        result = self.runner.invoke(
            cli,
            [
                "scout",
                "Graph Neural Networks",
                "--collection",
                "research/cimo-gnn",
                "--json",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        stdout_data = json.loads(result.stdout.strip())
        self.assertIn("collection_key", stdout_data)
        self.assertIn("collection_name", stdout_data)

    @patch("research_toolkit.cli.ZoteroManager")
    @patch("research_toolkit.cli.CitationSnowballer")
    @patch("research_toolkit.cli.DiscoveryService")
    def test_legacy_search_shim_with_collection_triggers_deprecation_warning(
        self, mock_service_cls, mock_snowballer_cls, mock_zotero_cls
    ):
        """Invoking search with legacy options (e.g. --collection) issues DeprecationWarning and routes to scout."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        mock_snowballer = MagicMock()
        mock_snowballer_cls.return_value = mock_snowballer
        mock_snowballer.snowball.return_value = SnowballResult(
            seed_paper_ids=[self.p_seed.paper_id],
            seeds=[self.p_seed],
            discovered_candidates=[self.p_found],
            direction="both",
            status="completed",
        )

        mock_zotero = MagicMock()
        mock_zotero_cls.return_value = mock_zotero
        mock_zotero.sync_to_collection.return_value = (self.mock_col, self.mock_sync_result)

        with warnings.catch_warnings(record=True) as recorded_warnings:
            warnings.simplefilter("always")
            result = self.runner.invoke(
                cli,
                [
                    "search",
                    "Graph Neural Networks",
                    "--collection",
                    "cimo-gnn",
                    "--dry-run",
                ],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            # DeprecationWarning issued
            deprecations = [w for w in recorded_warnings if issubclass(w.category, DeprecationWarning)]
            self.assertTrue(len(deprecations) >= 1)
            self.assertIn("scout", str(deprecations[0].message).lower())

        # Stderr also contains deprecation message
        self.assertIn("DeprecationWarning", result.stderr)

    @patch("research_toolkit.cli.DiscoveryService")
    def test_clean_search_atom_emits_no_deprecation_warning(self, mock_service_cls):
        """Invoking search as a pure retrieval atom (without collection or snowball) emits no DeprecationWarning."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.mock_batch

        with tempfile.TemporaryDirectory() as tmpdir:
            with warnings.catch_warnings(record=True) as recorded_warnings:
                warnings.simplefilter("always")
                result = self.runner.invoke(
                    cli,
                    ["search", "Graph Neural Networks", "--data-dir", tmpdir],
                )
                self.assertEqual(result.exit_code, 0)
                deprecations = [w for w in recorded_warnings if issubclass(w.category, DeprecationWarning)]
                self.assertEqual(len(deprecations), 0)


if __name__ == "__main__":
    unittest.main()
