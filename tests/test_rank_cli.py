"""
tests/test_rank_cli.py
Tests for the rank CLI atom command.
Conforms to Ticket #42:
- Consumes PaperCandidateBatch from stdin JSON stream OR --batch <path_or_id>.
- Optional --assessments <jsonl_file_or_path> for structured AssessmentRecord ingestion.
- Optional --topic <text> (defaults to batch topic).
- Optional -n / --top-n <int> (default 10).
- Pure machine-readable SelectionResult JSON streamed to stdout.
- Rich table, diagnostic score breakdowns, and insufficient candidates warnings to stderr.
- Chaining compatibility: search ... | rank ...
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from research_toolkit.cli import cli
from research_toolkit.discovery.models import (
    AssessmentRecord,
    PaperCandidate,
    PaperCandidateBatch,
    SelectionResult,
)


class TestRankCli(unittest.TestCase):
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
            venue_impact=20.0,
            doi="10.1000/attention",
        )
        self.p2 = PaperCandidate(
            paper_id="doi:10.1000/transformers_scale",
            title="Transformers at Scale",
            authors=["Vaswani, Ashish", "Parmar, Niki"],
            year=2024,
            citation_count=180,
            relevance_score=0.90,
            venue="ICML",
            venue_impact=18.0,
            doi="10.1000/transformers_scale",
        )
        self.p3 = PaperCandidate(
            paper_id="doi:10.1000/self_supervised",
            title="Self-Supervised Learning Survey",
            authors=["LeCun, Yann", "Misra, Ishan"],
            year=2024,
            citation_count=150,
            relevance_score=0.88,
            venue="IEEE TPAMI",
            venue_impact=20.0,
            doi="10.1000/self_supervised",
        )
        self.p_unrelated = PaperCandidate(
            paper_id="doi:10.1000/unrelated",
            title="Unrelated Botany Study",
            authors=["Linnaeus, Carl"],
            year=2024,
            citation_count=500,
            relevance_score=0.0,
            doi="10.1000/unrelated",
        )
        self.batch = PaperCandidateBatch(
            batch_id="batch_test_rank_001",
            query="Deep Learning Architecture",
            papers=[self.p1, self.p2, self.p3, self.p_unrelated],
            status="completed",
        )

    def test_rank_cli_stdin_json_stream_to_stdout(self):
        """Consumes candidate batch from stdin and outputs pure SelectionResult JSON to stdout."""
        batch_json = self.batch.to_json(indent=2)
        result = self.runner.invoke(
            cli,
            ["rank", "-n", "2"],
            input=batch_json,
        )
        self.assertEqual(result.exit_code, 0, msg=f"CLI failed: {result.output}")

        # stdout must be pure SelectionResult JSON
        stdout_text = result.stdout.strip()
        self.assertTrue(stdout_text.startswith("{"))
        self.assertTrue(stdout_text.endswith("}"))

        res = SelectionResult.from_json(stdout_text)
        self.assertEqual(res.batch_id, "batch_test_rank_001")
        self.assertEqual(len(res.selected_papers), 2)
        self.assertEqual(res.requested_n, 2)

    def test_rank_cli_batch_file_argument(self):
        """Loads candidate batch from --batch file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_batch.json"
            file_path.write_text(self.batch.to_json(indent=2), encoding="utf-8")

            result = self.runner.invoke(
                cli,
                ["rank", "--batch", str(file_path), "-n", "2"],
            )
            self.assertEqual(result.exit_code, 0)

            stdout_text = result.stdout.strip()
            res = SelectionResult.from_json(stdout_text)
            self.assertEqual(res.batch_id, "batch_test_rank_001")
            self.assertEqual(len(res.selected_papers), 2)

    def test_rank_cli_batch_id_lookup(self):
        """Loads candidate batch by batch ID from .research/batches/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            batches_dir = Path(tmpdir) / ".research" / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)
            batch_file = batches_dir / f"{self.batch.batch_id}.json"
            batch_file.write_text(self.batch.to_json(indent=2), encoding="utf-8")

            with patch.dict(os.environ, {"RESEARCH_BATCH_DIR": str(batches_dir)}):
                result = self.runner.invoke(
                    cli,
                    ["rank", "--batch", self.batch.batch_id, "-n", "3"],
                )
                self.assertEqual(result.exit_code, 0)
                res = SelectionResult.from_json(result.stdout.strip())
                self.assertEqual(res.batch_id, self.batch.batch_id)

    def test_rank_cli_with_assessments_jsonl_hard_exclusion(self):
        """Loads AssessmentRecords from JSONL and hard-excludes unrelated candidates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            batch_file = Path(tmpdir) / "batch.json"
            batch_file.write_text(self.batch.to_json(indent=2), encoding="utf-8")

            # Create assessments JSONL
            assessments = [
                AssessmentRecord(
                    paper_id="doi:10.1000/attention",
                    decision="related",
                    relevance_score=0.95,
                    reason="Foundational attention paper",
                ),
                AssessmentRecord(
                    paper_id="doi:10.1000/unrelated",
                    decision="unrelated",
                    relevance_score=0.0,
                    reason="Irrelevant plant biology",
                ),
            ]
            assessments_file = Path(tmpdir) / "assessments.jsonl"
            lines = [a.to_json() for a in assessments]
            assessments_file.write_text("\n".join(lines), encoding="utf-8")

            result = self.runner.invoke(
                cli,
                [
                    "rank",
                    "--batch",
                    str(batch_file),
                    "--assessments",
                    str(assessments_file),
                    "-n",
                    "3",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            res = SelectionResult.from_json(result.stdout.strip())

            # Unrelated paper must be strictly excluded
            self.assertNotIn("doi:10.1000/unrelated", res.selected_paper_ids)
            # Related paper reason should be present
            self.assertIn("doi:10.1000/attention", res.selected_paper_ids)
            self.assertIn("Foundational attention paper", res.reasons["doi:10.1000/attention"])

    def test_rank_cli_mmr_diversity_ordering(self):
        """Greedy MMR promotes different first author team when duplicate first author is present."""
        batch_json = self.batch.to_json()
        result = self.runner.invoke(
            cli,
            ["rank", "-n", "3"],
            input=batch_json,
        )
        self.assertEqual(result.exit_code, 0)
        res = SelectionResult.from_json(result.stdout.strip())

        # Vaswani 1 is picked first
        self.assertEqual(res.selected_papers[0].paper_id, "doi:10.1000/attention")
        # LeCun is picked second due to MMR penalty on Vaswani 2
        self.assertEqual(res.selected_papers[1].paper_id, "doi:10.1000/self_supervised")
        # Vaswani 2 is picked third (discounted)
        self.assertEqual(res.selected_papers[2].paper_id, "doi:10.1000/transformers_scale")

    def test_rank_cli_insufficient_eligible_candidates_warning_stderr(self):
        """When fewer than requested n eligible candidates exist, returns only eligible and warns to stderr."""
        with tempfile.TemporaryDirectory() as tmpdir:
            small_batch = PaperCandidateBatch(
                batch_id="batch_small",
                query="Quantum Neural Networks",
                papers=[self.p1, self.p_unrelated],  # Only p1 is eligible (p_unrelated marked unrelated)
            )
            assessments = [
                AssessmentRecord(
                    paper_id="doi:10.1000/attention",
                    decision="related",
                    relevance_score=0.9,
                ),
                AssessmentRecord(
                    paper_id="doi:10.1000/unrelated",
                    decision="unrelated",
                    relevance_score=0.0,
                ),
            ]
            assessments_file = Path(tmpdir) / "assessments.jsonl"
            assessments_file.write_text("\n".join(a.to_json() for a in assessments), encoding="utf-8")

            result = self.runner.invoke(
                cli,
                ["rank", "-n", "5", "--assessments", str(assessments_file)],
                input=small_batch.to_json(),
            )
            self.assertEqual(result.exit_code, 0)
            res = SelectionResult.from_json(result.stdout.strip())

            # Strictly 1 eligible candidate returned (not 5)
            self.assertEqual(len(res.selected_papers), 1)
            self.assertEqual(res.status, "insufficient_candidates")

    @patch("research_toolkit.cli.DiscoveryService")
    def test_rank_cli_pipeline_chaining_search_pipe_to_rank(self, mock_service_cls):
        """Chains search and rank commands via stdout/stdin pipe."""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search.return_value = self.batch
        mock_service.format_table.return_value = "RANK | TITLE\n1 | Attention"

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Run search command
            search_res = self.runner.invoke(
                cli,
                ["search", "Deep Learning Architecture", "--data-dir", tmpdir],
            )
            self.assertEqual(search_res.exit_code, 0)
            search_stdout = search_res.stdout.strip()
            self.assertTrue(search_stdout.startswith("{"))

            # 2. Pipe search output into rank command
            rank_res = self.runner.invoke(
                cli,
                ["rank", "-n", "2"],
                input=search_stdout,
            )
            self.assertEqual(rank_res.exit_code, 0)
            rank_stdout = rank_res.stdout.strip()
            self.assertTrue(rank_stdout.startswith("{"))
            self.assertTrue(rank_stdout.endswith("}"))

            sel_res = SelectionResult.from_json(rank_stdout)
            self.assertEqual(sel_res.batch_id, "batch_test_rank_001")
            self.assertEqual(len(sel_res.selected_papers), 2)


if __name__ == "__main__":
    unittest.main()
