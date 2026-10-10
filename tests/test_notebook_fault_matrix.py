"""Bounded external-fault combinations, observed only through CLI reports and fake service state."""

import itertools
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from notebook_fakes import OPEN_CLIENT, FakeNotebookClient
from zotero_fakes import FakeZoteroLibrary

from research_toolkit.cli import cli


@pytest.mark.parametrize("order", list(itertools.permutations(("K1", "K2", "K3"))))
@pytest.mark.parametrize("deletion_fails", [False, True])
@pytest.mark.parametrize("listing_delay", [0, 2])
@pytest.mark.parametrize("lost_response", [False, True])
@pytest.mark.parametrize("lost_delete_response", [False, True])
def test_capacity_partial_success_and_resume_under_combined_faults(
    tmp_path: Path, order: tuple[str, ...], deletion_fails: bool, listing_delay: int,
    lost_response: bool, lost_delete_response: bool
) -> None:
    library = FakeZoteroLibrary(tmp_path / "storage")
    collection = library.add_collection("fault-matrix", key="MATRIX01")
    for key in order:
        library.add_paper(collection, key, f"Paper {key}")
    fake = FakeNotebookClient()
    nb_id = fake.add_notebook("fault-matrix", ["[K1] Old", "[K1] Duplicate"] +
                              [f"[OLD{i}] Existing" for i in range(297)])
    original_ids = {source.id for source in fake.state[nb_id].sources if "[OLD" in (source.title or "")}
    fake.upload_visibility_delay = listing_delay
    fake.deletion_visibility_delay = listing_delay
    if deletion_fails:
        fake.delete_errors["[K1]"] = RuntimeError("delete refused")
    if lost_response:
        fake.committed_uploads["[K2]"] = 1
    if lost_delete_response:
        fake.committed_deletes["[K1]"] = 1

    def run() -> dict[str, Any]:
        with patch(OPEN_CLIENT, fake.open), patch("research_toolkit.cli.ZoteroManager", library.manager):
            result = CliRunner().invoke(cli, ["sync-notebook", "--collection", "fault-matrix", "--replace", "K1"])
        assert result.exit_code == 0, result.output
        return json.loads(result.stdout)

    first = run()
    assert fake.peak_source_counts[nb_id] <= 300
    assert original_ids <= {source.id for source in fake.state[nb_id].sources}
    assert set(entry["key"] for entry in first["added"]) <= {"K1", "K2", "K3"}
    assert first["failed"] or len(first["added"]) == 3
    fake.delete_errors.clear()
    fake.committed_deletes.clear()
    fake.upload_visibility_delay = fake.deletion_visibility_delay = 0
    fake.hidden_sources.clear()
    fake.stale_sources.clear()
    resumed = run()
    assert resumed["failed"] == []
    assert fake.peak_source_counts[nb_id] <= 300
    for key in ("K1", "K2", "K3"):
        assert sum((title or "").startswith(f"[{key}]") for title in fake.source_titles(nb_id)) == 1


def test_restart_preserves_unconfirmed_write_protection_while_listing_is_still_stale(tmp_path: Path) -> None:
    library = FakeZoteroLibrary(tmp_path / "storage")
    collection = library.add_collection("restart", key="RESTART1")
    for key in ("K1", "K2", "K3"):
        library.add_paper(collection, key, f"Paper {key}")
    fake = FakeNotebookClient()
    nb_id = fake.add_notebook("restart", ["[K1] Old", "[K1] Duplicate"] +
                              [f"[OLD{i}] Existing" for i in range(297)])
    fake.delete_errors["[K1]"] = RuntimeError("delete refused")
    fake.committed_uploads["[K2]"] = 1
    fake.upload_visibility_delay = 10

    def run(*extra: str) -> dict[str, Any]:
        with patch(OPEN_CLIENT, fake.open), patch("research_toolkit.cli.ZoteroManager", library.manager):
            result = CliRunner().invoke(cli, ["sync-notebook", "--collection", "restart", "--replace", "K1", *extra])
        assert result.exit_code == 0, result.output
        return json.loads(result.stdout)

    first = run()
    assert first["failed"]
    assert fake.peak_source_counts[nb_id] == 300
    assert list((library.storage_dir / ".research-toolkit" / "notebook-sync").glob("*.json"))
    restarted = run()
    assert "Unconfirmed writes" in restarted["aborted_reason"]
    assert restarted["added"] == []
    blocked_preview = run("--dry-run")
    assert blocked_preview["aborted_reason"]
    assert blocked_preview["added"] == []
    assert fake.peak_source_counts[nb_id] == 300
    fake.upload_visibility_delay = 0
    fake.hidden_sources.clear()
    fake.delete_errors.clear()
    preview = run("--dry-run")
    assert preview["aborted_reason"] is None
    assert list((library.storage_dir / ".research-toolkit" / "notebook-sync").glob("*.json"))
    completed = run()
    assert completed["failed"] == []
    assert fake.peak_source_counts[nb_id] == 300
    assert not list((library.storage_dir / ".research-toolkit" / "notebook-sync").glob("*.json"))
    assert sum((title or "").startswith("[K2]") for title in fake.source_titles(nb_id)) == 1


def test_restart_does_not_confirm_a_new_write_from_a_stale_deleted_source(tmp_path: Path) -> None:
    library = FakeZoteroLibrary(tmp_path / "storage")
    collection = library.add_collection("stale-restart", key="STALE001")
    library.add_paper(collection, "K1", "Paper K1")
    fake = FakeNotebookClient()
    fake.add_notebook("stale-restart", ["[K1] Paper K1"])
    fake.upload_visibility_delay = fake.deletion_visibility_delay = 10
    fake.committed_uploads["[K1]"] = 1

    def run() -> dict[str, Any]:
        with patch(OPEN_CLIENT, fake.open), patch("research_toolkit.cli.ZoteroManager", library.manager):
            result = CliRunner().invoke(cli, ["sync-notebook", "--collection", "stale-restart", "--replace", "K1"])
        assert result.exit_code == 0, result.output
        return json.loads(result.stdout)

    assert run()["failed"]
    second = run()
    assert "Unconfirmed writes" in second["aborted_reason"]
    assert second["added"] == []
