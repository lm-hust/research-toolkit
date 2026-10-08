"""
tests/test_snowball_cli.py
Integration tests for 'research-toolkit snowball' command conforming to Ticket #43.
Verifies CLI stream separation (JSON stdout, Rich stderr), seed adapters, budget caps, and pipeline chaining.
"""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from research_toolkit.cli import cli
from research_toolkit.discovery.models import (
    PaperCandidate,
    PaperCandidateBatch,
    SelectionResult,
    SnowballResult,
)


def create_sample_seed(doi: str, title: str, ref_dois: list[str] | None = None) -> PaperCandidate:
    return PaperCandidate(
        paper_id=f"doi:{doi}",
        title=title,
        doi=doi,
        year=2023,
        citation_count=50,
        relevance_score=0.9,
        referenced_works=ref_dois or [],
    )


def test_snowball_cli_with_seeds_option():
    """Verifies snowball command with explicit --seeds argument list."""
    runner = CliRunner()
    seed_doi = "10.1000/seed1"

    found_paper = PaperCandidate(
        paper_id="https://openalex.org/W_found",
        title="Foundational Reference",
        year=2018,
        doi="10.1000/found",
        citation_count=1000,
        relevance_score=0.85,
    )
    fwd_paper = PaperCandidate(
        paper_id="https://openalex.org/W_fwd",
        title="Recent Citing Work",
        year=2024,
        doi="10.1000/fwd",
        citation_count=10,
        relevance_score=0.85,
        referenced_works=["https://openalex.org/W_seed1"],
    )

    with patch("research_toolkit.cli.CitationSnowballer") as mock_snowballer_cls:
        mock_instance = MagicMock()
        mock_snowballer_cls.return_value = mock_instance
        mock_instance.snowball.return_value = SnowballResult(
            seed_paper_ids=[f"doi:{seed_doi}"],
            seeds=[create_sample_seed(seed_doi, "Seed 1")],
            discovered_candidates=[found_paper, fwd_paper],
            direction="both",
            status="completed",
        )

        result = runner.invoke(
            cli,
            [
                "snowball",
                "--seeds",
                seed_doi,
                "--direction",
                "both",
                "--max-backward",
                "15",
                "--max-forward",
                "15",
            ],
        )

        assert result.exit_code == 0, result.output
        # Stderr contains diagnostic and table info
        assert "Ingested 1 seed papers" in result.stderr
        assert "Discovered 2 candidates" in result.stderr
        assert "Snowball Discovered Candidates" in result.stderr

        # Stdout is strictly parseable SnowballResult JSON
        data = json.loads(result.stdout)
        assert data["direction"] == "both"
        assert data["status"] == "completed"
        assert len(data["seeds"]) == 1
        assert len(data["discovered_candidates"]) == 2
        assert data["seed_paper_ids"] == [f"doi:{seed_doi}"]


def test_snowball_cli_stdin_paper_candidate_batch():
    """Verifies snowball command reading PaperCandidateBatch from stdin stream."""
    runner = CliRunner()
    batch = PaperCandidateBatch(
        batch_id="batch_test_123",
        query="test query",
        papers=[create_sample_seed("10.1000/s1", "Seed Paper from Batch")],
    )

    mock_res = SnowballResult(
        seed_paper_ids=["doi:10.1000/s1"],
        seeds=batch.papers,
        discovered_candidates=[
            PaperCandidate(
                paper_id="https://openalex.org/W_fwd",
                title="Forward Paper",
                topological_role="recent_advancement",
                co_citation_count=1,
            )
        ],
        direction="forward",
        status="completed",
    )

    with patch("research_toolkit.cli.CitationSnowballer") as mock_snowballer_cls:
        mock_instance = MagicMock()
        mock_snowballer_cls.return_value = mock_instance
        mock_instance.snowball.return_value = mock_res

        result = runner.invoke(
            cli,
            ["snowball", "--direction", "forward"],
            input=batch.to_json(),
        )

        assert result.exit_code == 0, result.output
        assert "Ingested 1 seed papers" in result.stderr

        data = json.loads(result.stdout)
        assert data["direction"] == "forward"
        assert len(data["discovered_candidates"]) == 1
        assert data["discovered_candidates"][0]["topological_role"] == "recent_advancement"


def test_snowball_cli_stdin_selection_result():
    """Verifies snowball command reading SelectionResult from stdin stream."""
    runner = CliRunner()
    sel = SelectionResult(
        batch_id="batch_sel_456",
        selected_papers=[create_sample_seed("10.1000/sel1", "Selected Top Paper")],
        selected_paper_ids=["doi:10.1000/sel1"],
    )

    mock_res = SnowballResult(
        seed_paper_ids=["doi:10.1000/sel1"],
        seeds=sel.selected_papers,
        discovered_candidates=[],
        direction="both",
        status="completed",
    )

    with patch("research_toolkit.cli.CitationSnowballer") as mock_snowballer_cls:
        mock_instance = MagicMock()
        mock_snowballer_cls.return_value = mock_instance
        mock_instance.snowball.return_value = mock_res

        result = runner.invoke(
            cli,
            ["snowball"],
            input=sel.to_json(),
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["seed_paper_ids"] == ["doi:10.1000/sel1"]


def test_snowball_cli_batch_file_option(tmp_path):
    """Verifies loading seeds from --batch file path."""
    runner = CliRunner()
    batch = PaperCandidateBatch(
        batch_id="batch_file_test",
        query="file query",
        papers=[create_sample_seed("10.1000/file1", "File Seed Paper")],
    )
    batch_file = tmp_path / "batch.json"
    batch_file.write_text(batch.to_json(), encoding="utf-8")

    mock_res = SnowballResult(
        seed_paper_ids=["doi:10.1000/file1"],
        seeds=batch.papers,
        discovered_candidates=[],
        direction="both",
        status="completed",
    )

    with patch("research_toolkit.cli.CitationSnowballer") as mock_snowballer_cls:
        mock_instance = MagicMock()
        mock_snowballer_cls.return_value = mock_instance
        mock_instance.snowball.return_value = mock_res

        result = runner.invoke(
            cli,
            ["snowball", "--batch", str(batch_file)],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["seed_paper_ids"] == ["doi:10.1000/file1"]


def test_snowball_cli_from_collection():
    """Verifies loading seeds from Zotero collection via --from-collection."""
    runner = CliRunner()
    collection_seeds = [create_sample_seed("10.1000/col1", "Collection Seed")]

    mock_res = SnowballResult(
        seed_paper_ids=["doi:10.1000/col1"],
        seeds=collection_seeds,
        discovered_candidates=[],
        direction="both",
        status="completed",
    )

    with (
        patch("research_toolkit.cli.load_seeds_from_collection") as mock_load_col,
        patch("research_toolkit.cli.CitationSnowballer") as mock_snowballer_cls,
    ):
        mock_load_col.return_value = collection_seeds
        mock_instance = MagicMock()
        mock_snowballer_cls.return_value = mock_instance
        mock_instance.snowball.return_value = mock_res

        result = runner.invoke(
            cli,
            ["snowball", "--from-collection", "my-zotero-collection"],
        )

        assert result.exit_code == 0, result.output
        mock_load_col.assert_called_once_with("my-zotero-collection")
        data = json.loads(result.stdout)
        assert data["seed_paper_ids"] == ["doi:10.1000/col1"]


def test_snowball_cli_quiet_option():
    """Verifies --quiet suppresses Rich table and diagnostic stderr output."""
    runner = CliRunner()
    seed_doi = "10.1000/seed1"

    mock_res = SnowballResult(
        seed_paper_ids=[f"doi:{seed_doi}"],
        seeds=[create_sample_seed(seed_doi, "Seed 1")],
        discovered_candidates=[],
        direction="both",
        status="completed",
    )

    with patch("research_toolkit.cli.CitationSnowballer") as mock_snowballer_cls:
        mock_instance = MagicMock()
        mock_snowballer_cls.return_value = mock_instance
        mock_instance.snowball.return_value = mock_res

        result = runner.invoke(
            cli,
            ["snowball", "--seeds", seed_doi, "--quiet"],
        )

        assert result.exit_code == 0, result.output
        # Stderr should be empty
        assert result.stderr == ""
        # Stdout is valid JSON
        data = json.loads(result.stdout)
        assert data["status"] == "completed"


def test_snowball_cli_piping_to_rank():
    """Verifies UNIX piping chaining: snowball output piped into rank."""
    runner = CliRunner()
    seed_doi = "10.1000/seed1"

    discovered_cand1 = PaperCandidate(
        paper_id="doi:10.1000/cand1",
        title="Discovered Candidate 1",
        doi="10.1000/cand1",
        year=2024,
        citation_count=20,
        relevance_score=0.95,
        topological_role="recent_advancement",
    )
    discovered_cand2 = PaperCandidate(
        paper_id="doi:10.1000/cand2",
        title="Discovered Candidate 2",
        doi="10.1000/cand2",
        year=2019,
        citation_count=500,
        relevance_score=0.85,
        topological_role="foundational",
    )

    snowball_res = SnowballResult(
        seed_paper_ids=[f"doi:{seed_doi}"],
        seeds=[create_sample_seed(seed_doi, "Seed 1")],
        discovered_candidates=[discovered_cand1, discovered_cand2],
        direction="both",
        status="completed",
    )

    # 1. Simulate snowball producing stdout JSON
    snowball_json = snowball_res.to_json(indent=2)

    # 2. Pipe snowball JSON into 'rank -n 2'
    rank_result = runner.invoke(
        cli,
        ["rank", "-n", "2", "--topic", "test-topic"],
        input=snowball_json,
    )

    assert rank_result.exit_code == 0, rank_result.output
    rank_data = json.loads(rank_result.stdout)
    assert rank_data["requested_n"] == 2
    assert len(rank_data["selected_papers"]) == 2
    assert rank_data["status"] == "completed"
    selected_ids = rank_data["selected_paper_ids"]
    assert "doi:10.1000/cand1" in selected_ids
    assert "doi:10.1000/cand2" in selected_ids


def test_snowball_cli_missing_seeds_raises_usage_error():
    """Verifies usage error when no seeds or input streams are provided."""
    runner = CliRunner()
    with patch("research_toolkit.cli.load_session", return_value={}):
        result = runner.invoke(cli, ["snowball"])
        assert result.exit_code != 0
        assert "Seed papers must be provided" in result.output
