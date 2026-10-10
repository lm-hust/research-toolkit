"""Public script interfaces, exercised in disposable directories without network access."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True, check=False,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    )


def test_skill_trial_dry_run_creates_nothing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    skill = source / "whoami"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("test skill", encoding="utf-8")
    target = tmp_path / "trial"

    result = run_script("sync_skills.py", "--source", str(source), "--target", str(target),
                        "--mode", "trial", "--skill", "whoami", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "whoami" in result.stdout
    assert not target.exists()


def test_skill_sync_requires_explicit_selection_and_destination() -> None:
    result = run_script("sync_skills.py")
    assert result.returncode != 0
    assert "--target" in result.stderr


def test_trial_retargets_only_selected_link_and_preserves_its_old_source(tmp_path: Path) -> None:
    source, old, target = (tmp_path / name for name in ("source", "old", "target"))
    for root in (source, old):
        (root / "whoami").mkdir(parents=True)
        (root / "whoami" / "SKILL.md").write_text("same", encoding="utf-8")
    target.mkdir()
    (target / "whoami").symlink_to(old / "whoami")
    (target / "other").write_text("untouched", encoding="utf-8")
    result = run_script("sync_skills.py", "--source", str(source), "--target", str(target),
                        "--mode", "trial", "--skill", "whoami")
    assert result.returncode == 0, result.stderr
    assert (target / "whoami").resolve() == source / "whoami"
    assert (old / "whoami" / "SKILL.md").read_text() == "same"
    assert (target / "other").read_text() == "untouched"


def test_skill_conflict_preflight_prevents_all_selected_writes(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    for name in ("one", "two"):
        (source / name).mkdir(parents=True)
        (source / name / "SKILL.md").write_text("new", encoding="utf-8")
    (target / "two").mkdir(parents=True)
    (target / "two" / "SKILL.md").write_text("user edit", encoding="utf-8")
    result = run_script("sync_skills.py", "--source", str(source), "--target", str(target),
                        "--mode", "trial", "--skill", "one", "--skill", "two")
    assert result.returncode == 1
    assert "SKILL.md" in result.stderr
    assert not (target / "one").exists()
    assert (target / "two" / "SKILL.md").read_text() == "user edit"


def test_publication_is_a_snapshot_and_explicit_replacement_preserves_backup(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    (source / "whoami").mkdir(parents=True)
    (source / "whoami" / "SKILL.md").write_text("new", encoding="utf-8")
    (target / "whoami").mkdir(parents=True)
    (target / "whoami" / "SKILL.md").write_text("old", encoding="utf-8")
    args = ("--source", str(source), "--target", str(target), "--mode", "publish", "--skill", "whoami")
    assert run_script("sync_skills.py", *args).returncode == 1
    result = run_script("sync_skills.py", *args, "--replace")
    assert result.returncode == 0, result.stderr
    [backup] = list(target.glob(".whoami.backup-*"))
    assert (backup / "SKILL.md").read_text() == "old"
    assert not (target / "whoami").is_symlink()
    (source / "whoami" / "SKILL.md").write_text("later edit", encoding="utf-8")
    assert (target / "whoami" / "SKILL.md").read_text() == "new"


def test_skill_sync_rejects_path_traversal_and_nested_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "whoami").mkdir(parents=True)
    (source / "whoami" / "SKILL.md").write_text("skill", encoding="utf-8")
    outside = tmp_path / "private"
    outside.write_text("private", encoding="utf-8")
    (source / "whoami" / "secret").symlink_to(outside)
    args = ("--source", str(source), "--target", str(tmp_path / "target"), "--mode", "publish")
    assert run_script("sync_skills.py", *args, "--skill", "../private").returncode == 1
    assert run_script("sync_skills.py", *args, "--skill", "whoami").returncode == 1
    assert not (tmp_path / "target").exists()


def test_check_log_preserves_failure_status_and_output(tmp_path: Path) -> None:
    log = tmp_path / "check.log"
    result = subprocess.run(
        ["bash", str(SCRIPTS / "check-log.sh"), str(log), sys.executable, "-c",
         "import sys; print('diagnostic'); sys.exit(7)"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 7
    assert "diagnostic" in result.stdout
    assert "diagnostic" in log.read_text()


def test_acceptance_ready_requires_evidence_and_explicit_human_gate(tmp_path: Path) -> None:
    record = tmp_path / "acceptance.json"
    data: dict[str, Any] = {"head": "a" * 40, "gates": {
        "automated": {"status": "passed", "evidence": ["https://github.com/o/r/actions/runs/1"]},
        "live": {"status": "passed", "evidence": ["https://github.com/o/r/issues/2#issuecomment-3"]},
        "human": {"status": "pending", "reason": "direction not confirmed", "evidence": []},
    }}
    record.write_text(json.dumps(data), encoding="utf-8")
    draft = run_script("check_acceptance.py", str(record))
    assert draft.returncode == 0, draft.stderr
    assert run_script("check_acceptance.py", str(record), "--ready").returncode == 1
    data["gates"]["human"] = {"status": "waived", "reason": "explicit acceptance of deferral",
                              "approved_by": "user", "evidence": ["https://github.com/o/r/issues/2#issuecomment-4"]}
    record.write_text(json.dumps(data), encoding="utf-8")
    ready = run_script("check_acceptance.py", str(record), "--ready")
    assert ready.returncode == 0, ready.stderr
    data["gates"]["automated"]["evidence"] = []
    record.write_text(json.dumps(data), encoding="utf-8")
    assert run_script("check_acceptance.py", str(record)).returncode == 1


def test_acceptance_checks_link_existence_without_printing_private_response(tmp_path: Path) -> None:
    record = tmp_path / "acceptance.json"
    record.write_text(json.dumps({"head": "a" * 40, "gates": {
        name: {"status": "passed", "evidence": ["https://github.com/o/r/issues/2#issuecomment-3"]}
        for name in ("automated", "live", "human")
    }}), encoding="utf-8")
    gh = tmp_path / "gh"
    gh.write_text("#!/bin/sh\nprintf '%s\\n' '{\"issue_url\":\"https://api.github.com/repos/o/r/issues/2\",\"body\":\"private-response\",\"run_id\":1}'\nexit 0\n", encoding="utf-8")
    gh.chmod(0o755)
    command = [sys.executable, str(SCRIPTS / "check_acceptance.py"), str(record), "--verify-links"]
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "private-response" not in result.stdout + result.stderr
    data = json.loads(record.read_text())
    data["gates"]["human"]["evidence"] = ["https://github.com/o/r/issues/999#issuecomment-3"]
    record.write_text(json.dumps(data), encoding="utf-8")
    wrong_parent = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert wrong_parent.returncode == 1
    data["gates"]["human"]["evidence"] = ["https://github.com/o/r/actions/runs/999/job/4"]
    record.write_text(json.dumps(data), encoding="utf-8")
    wrong_run = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert wrong_run.returncode == 1
    gh.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "Evidence unavailable" in result.stderr
    assert run_script("check_acceptance.py", str(record), "--head", "b" * 40).returncode == 1


def test_review_ledger_pins_refs_and_bounds_followups_to_repair_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Model pre-commit's outer index without ever letting the fixture touch the real one.
    outer_index = tmp_path / "outer-index"
    outer_index.write_bytes(b"outer-index-sentinel")
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer_index))
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
            env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
        )
        return result.stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    git("config", "commit.gpgsign", "false")
    git("config", "core.hooksPath", "/dev/null")
    (repo / "base.txt").write_text("base", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (repo / "feature.txt").write_text("feature", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "feature")
    feature = git("rev-parse", "HEAD")
    first = tmp_path / "first.json"
    args = ("--repo", str(repo), "--base", base, "--spec", "user-request", "--output", str(first))
    result = run_script("review_scope.py", *args)
    assert result.returncode == 0, result.stderr
    data = json.loads(first.read_text())
    assert data["head"] == feature
    assert data["changed_files"] == ["feature.txt"]
    data["findings"] = [{"id": "S1", "axis": "spec", "status": "open", "evidence": "reproducer"}]
    first.write_text(json.dumps(data), encoding="utf-8")
    (repo / "repair.txt").write_text("repair", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "repair")
    second = tmp_path / "second.json"
    result = run_script("review_scope.py", "--repo", str(repo), "--previous", str(first), "--output", str(second))
    assert result.returncode == 0, result.stderr
    followup = json.loads(second.read_text())
    assert followup["base"] == base
    assert followup["comparison_base"] == feature
    assert followup["changed_files"] == ["repair.txt"]
    assert followup["findings"] == data["findings"]
    assert followup["reviewed_head"] is None
    assert run_script("review_scope.py", *args).returncode == 1
    assert outer_index.read_bytes() == b"outer-index-sentinel"
    contaminated = subprocess.run(
        [sys.executable, str(SCRIPTS / "review_scope.py"), "--repo", str(repo), "--base", base,
         "--spec", "user-request", "--output", str(tmp_path / "contaminated.json")],
        env={**os.environ, "GIT_DIR": str(tmp_path / "nonexistent-git-dir")},
        capture_output=True, text=True, check=False,
    )
    assert contaminated.returncode == 0, contaminated.stderr
    assert json.loads((tmp_path / "contaminated.json").read_text())["head"] == git("rev-parse", "HEAD")
    assert outer_index.read_bytes() == b"outer-index-sentinel"


def test_inventory_filters_candidates_without_claiming_authorship_or_authority() -> None:
    data = {"notebook_id": "uuid", "sources": [
        {"id": "paper", "title": "Other et al. - 2025 - Paper"},
        {"id": "direction", "title": "研究贡献"},
        {"id": "unrelated", "title": "Unrelated private title"},
    ]}
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "notebook_inventory.py"), "--match", "研究贡献"],
        input=json.dumps(data), capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["paper_source_counts_by_year"] == {"2025": 1}
    assert output["candidates"] == [{"id": "direction", "title": "研究贡献", "title_kind": "unclassified"}]
    assert "Unrelated private title" not in result.stdout


def test_acceptance_rejects_null_waiver_approver(tmp_path: Path) -> None:
    record = tmp_path / "acceptance.json"
    record.write_text(json.dumps({"head": "a" * 40, "gates": {
        name: {"status": "waived", "reason": "deferred", "approved_by": None,
               "evidence": ["https://github.com/o/r/issues/2#issuecomment-3"]}
        for name in ("automated", "live", "human")
    }}), encoding="utf-8")
    assert run_script("check_acceptance.py", str(record), "--ready").returncode == 1
