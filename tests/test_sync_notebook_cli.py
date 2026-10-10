"""
tests/test_sync_notebook_cli.py
sync-notebook through the CLI, with the in-memory notebook client and fake Zotero data.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner, Result
from notebook_fakes import OPEN_CLIENT, FakeNotebookClient
from notebooklm import SourceStatus
from zotero_fakes import FakeZoteroLibrary

from research_toolkit.cli import cli

COLLECTION = "intelligence-per-kwh"


class SyncNotebookCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.zotero = FakeZoteroLibrary(self.tmp / "storage")
        self.col = self.zotero.add_collection(COLLECTION, key="KS2HSWPE")
        self.fake = FakeNotebookClient()

    def run_sync(self, *args: str) -> Result:
        with patch(OPEN_CLIENT, self.fake.open), patch(
            "research_toolkit.cli.ZoteroManager", self.zotero.manager
        ):
            return CliRunner().invoke(cli, ["sync-notebook", *args])

    def report(self, result: Result) -> dict[str, Any]:
        self.assertEqual(result.exit_code, 0, result.output)
        return json.loads(result.stdout)

    @staticmethod
    def keys(entries: list[dict[str, Any]]) -> list[str]:
        return [e["key"] for e in entries]

    def test_first_sync_creates_notebook_named_after_collection(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Energy and Policy Considerations")
        self.zotero.add_paper(self.col, "K2", "Green AI")
        self.zotero.add_paper(self.col, "K3", "No PDF here", pdf=False)

        report = self.report(self.run_sync("--collection", COLLECTION))

        [nb_id] = self.fake.notebook_ids(COLLECTION)
        self.assertEqual(report["notebook_id"], nb_id)
        self.assertEqual(report["notebook_title"], COLLECTION)
        self.assertTrue(report["created"])
        self.assertEqual(self.keys(report["added"]), ["K1", "K2"])
        self.assertEqual(report["skipped_existing"], [])
        self.assertEqual(report["missing_fulltext"], [{"key": "K3", "title": "No PDF here"}])
        self.assertEqual(report["failed"], [])
        self.assertEqual(
            self.fake.source_titles(nb_id),
            ["[K1] Energy and Policy Considerations", "[K2] Green AI"],
        )

    def test_rerun_skips_keys_already_in_the_notebook(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Energy and Policy Considerations")
        self.zotero.add_paper(self.col, "K2", "Green AI")
        nb_id = self.fake.add_notebook(COLLECTION, ["[K1] Title edited by hand"])

        report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertEqual(report["notebook_id"], nb_id)
        self.assertFalse(report["created"])
        self.assertEqual(report["skipped_existing"], [{"key": "K1", "title": "Energy and Policy Considerations"}])
        self.assertEqual(self.keys(report["added"]), ["K2"])
        self.assertEqual(self.fake.source_titles(nb_id), ["[K1] Title edited by hand", "[K2] Green AI"])

        again = self.report(self.run_sync("--collection", COLLECTION))
        self.assertEqual(self.keys(again["skipped_existing"]), ["K1", "K2"])
        self.assertEqual(again["added"], [])
        self.assertEqual(len(self.fake.source_titles(nb_id)), 2)

    def test_notebook_option_targets_existing_notebook_by_title(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.fake.add_notebook(COLLECTION)
        target = self.fake.add_notebook("度电智能")

        report = self.report(self.run_sync("--collection", COLLECTION, "--notebook", "度电智能"))

        self.assertEqual(report["notebook_id"], target)
        self.assertEqual(report["notebook_title"], "度电智能")
        self.assertFalse(report["created"])
        self.assertEqual(self.fake.source_titles(target), ["[K1] Green AI"])

    def test_notebook_option_accepts_full_uuid(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        first = self.fake.add_notebook("Same")
        second = self.fake.add_notebook("Same")

        report = self.report(self.run_sync("--collection", COLLECTION, "--notebook", second))

        self.assertEqual(report["notebook_id"], second)
        self.assertEqual(self.fake.source_titles(first), [])
        self.assertEqual(self.fake.source_titles(second), ["[K1] Green AI"])

    def test_duplicate_notebook_titles_are_an_error(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        first = self.fake.add_notebook(COLLECTION)
        second = self.fake.add_notebook(COLLECTION)

        result = self.run_sync("--collection", COLLECTION)

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn(first, result.stderr)
        self.assertIn(second, result.stderr)
        self.assertIn("UUID", result.stderr)
        self.assertEqual(self.fake.writes, [])

    def test_unknown_notebook_reference_is_an_error(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")

        result = self.run_sync("--collection", COLLECTION, "--notebook", "nope")

        self.assertEqual(result.exit_code, 1)
        self.assertIn("nope", result.stderr)
        self.assertEqual(self.fake.writes, [])

    def test_unknown_collection_is_an_error(self) -> None:
        result = self.run_sync("--collection", "missing")

        self.assertEqual(result.exit_code, 1)
        self.assertIn("missing", result.stderr)
        self.assertEqual(self.fake.writes, [])

    def test_child_notes_are_not_papers(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_child_note(self.col, "K1", "NOTE0001")

        report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertEqual(self.keys(report["added"]), ["K1"])
        self.assertEqual(report["missing_fulltext"], [])

    def test_one_failed_upload_does_not_stop_the_run(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        self.fake.upload_errors["[K1]"] = RuntimeError("upload exploded")

        report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertEqual(
            report["failed"], [{"key": "K1", "title": "Green AI", "error": "upload exploded"}]
        )
        self.assertEqual(self.keys(report["added"]), ["K2"])

    def test_failed_replace_deletion_is_reported_and_other_papers_continue(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        nb_id = self.fake.add_notebook(COLLECTION, ["[K1] Old Green AI"])
        with patch.object(self.fake.sources, "delete", AsyncMock(side_effect=RuntimeError("delete refused"))):
            report = self.report(self.run_sync("--collection", COLLECTION, "--replace", "K1"))

        self.assertEqual(self.keys(report["added"]), ["K2"])
        self.assertEqual(report["failed"], [{"key": "K1", "title": "Green AI", "error": "delete refused"}])
        self.assertEqual(self.fake.source_titles(nb_id), ["[K1] Old Green AI", "[K2] Energy and Policy"])

    def test_identity_is_never_synced_even_with_force_and_uuid(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        nb_id = self.fake.add_notebook("Identity", ["Personal statement"])
        result = self.run_sync("--collection", COLLECTION, "--notebook", nb_id, "--force")

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Identity", result.stderr)
        self.assertEqual(self.fake.writes, [])

    def test_sync_never_creates_identity_from_a_collection_name(self) -> None:
        col = self.zotero.add_collection("Identity", key="IDENTITY")
        self.zotero.add_paper(col, "K1", "Green AI")

        result = self.run_sync("--collection", "Identity", "--force")

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Identity", result.stderr)
        self.assertEqual(self.fake.writes, [])

    def test_rerun_waits_for_an_unready_keyed_source_instead_of_skipping_it(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        nb_id = self.fake.add_notebook(COLLECTION)
        source = self.fake.new_source(nb_id, "[K1] Green AI", status=SourceStatus.PROCESSING)

        report = self.report(self.run_sync("--collection", COLLECTION))
        self.assertEqual(report["skipped_existing"], [])
        self.assertEqual(self.keys(report["failed"]), ["K1"])
        self.assertEqual(report["added"], [])

        source.status = SourceStatus.READY
        resumed = self.report(self.run_sync("--collection", COLLECTION))
        self.assertEqual(resumed["failed"], [])
        self.assertEqual(self.keys(resumed["skipped_existing"]), ["K1"])
        self.assertEqual(len(self.fake.source_titles(nb_id)), 1)

    def test_final_title_repair_failure_keeps_the_report_and_checks_other_papers(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        self.fake.title_resets.update({"[K1]": "late", "[K2]": "late"})
        rename = self.fake.sources.rename

        async def failing_rename(notebook_id: str, source_id: str, title: str) -> Any:
            if title.startswith("[K1]"):
                raise RuntimeError("rename refused")
            return await rename(notebook_id, source_id, title)

        with patch.object(self.fake.sources, "rename", failing_rename):
            report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertEqual(self.keys(report["added"]), ["K1", "K2"])
        self.assertEqual(self.keys(report["failed"]), ["K1"])
        self.assertIn("rename refused", report["failed"][0]["error"])
        self.assertEqual(self.keys(report["renamed"]), ["K2"])

    def test_final_source_listing_failure_preserves_successful_upload_report(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        with patch.object(self.fake.sources, "list", AsyncMock(side_effect=RuntimeError("list refused"))):
            report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertEqual(self.keys(report["added"]), ["K1"])
        self.assertEqual(self.keys(report["failed"]), ["K1"])
        self.assertIn("list refused", report["failed"][0]["error"])

    def test_failed_replacement_cannot_spend_capacity_that_was_not_freed(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        nb_id = self.fake.add_notebook(
            COLLECTION, ["[K1] Old", "[K1] Duplicate"] + [f"[OLD{i}] Paper" for i in range(298)]
        )
        with patch.object(self.fake.sources, "delete", AsyncMock(side_effect=RuntimeError("delete refused"))):
            report = self.report(self.run_sync("--collection", COLLECTION, "--replace", "K1"))

        self.assertEqual(report["projected_source_count"], 300)
        self.assertEqual(report["added"], [])
        self.assertEqual(self.keys(report["failed"]), ["K1", "K2"])
        self.assertIn("300", report["failed"][1]["error"])
        self.assertEqual(len(self.fake.source_titles(nb_id)), 300)

    def test_immediate_title_repair_failure_reports_the_landed_source_for_recovery(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.fake.title_resets["[K1]"] = "immediate"
        with patch.object(self.fake.sources, "rename", AsyncMock(side_effect=RuntimeError("rename refused"))):
            report = self.report(self.run_sync("--collection", COLLECTION))

        [nb_id] = self.fake.notebook_ids(COLLECTION)
        [failed] = report["failed"]
        self.assertEqual(failed["source_id"], self.fake.state[nb_id].sources[0].id)
        self.assertIn("Title check", failed["error"])
        self.assertEqual(len(self.fake.source_titles(nb_id)), 1)

    def test_title_reverted_to_filename_on_upload_is_renamed(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        self.fake.title_resets["[K1]"] = "immediate"

        report = self.report(self.run_sync("--collection", COLLECTION))

        [nb_id] = self.fake.notebook_ids(COLLECTION)
        self.assertEqual(self.keys(report["added"]), ["K1", "K2"])
        self.assertEqual(report["renamed"], [{"key": "K1", "title": "Green AI"}])
        self.assertEqual(self.fake.source_titles(nb_id), ["[K1] Green AI", "[K2] Energy and Policy"])

    def test_title_reverted_after_the_paper_was_checked_is_fixed_by_the_final_check(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        self.fake.title_resets["[K1]"] = "late"

        report = self.report(self.run_sync("--collection", COLLECTION))

        [nb_id] = self.fake.notebook_ids(COLLECTION)
        self.assertEqual(self.keys(report["added"]), ["K1", "K2"])
        self.assertEqual(report["renamed"], [{"key": "K1", "title": "Green AI"}])
        self.assertEqual(self.fake.source_titles(nb_id), ["[K1] Green AI", "[K2] Energy and Policy"])

    def test_unconfirmed_upload_residue_is_deleted_and_the_retry_is_added(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        # a keyed notebook, so the hand-maintained guard does not trip on the unkeyed source
        nb_id = self.fake.add_notebook(COLLECTION, ["[K0] Synced earlier"])
        self.fake.new_source(nb_id, "Green AI.pdf", status=SourceStatus.PREPARING)  # not ours
        self.fake.unconfirmed_uploads["[K1]"] = 1

        report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertEqual(self.keys(report["added"]), ["K1", "K2"])
        self.assertEqual(report["failed"], [])
        self.assertEqual(
            self.fake.source_titles(nb_id),
            ["[K0] Synced earlier", "Green AI.pdf", "[K1] Green AI", "[K2] Energy and Policy"],
        )
        self.assertEqual(len([w for w in self.fake.writes if w[0] == "delete_source"]), 1)
        self.assertEqual(len([w for w in self.fake.writes if w[0] == "add_file"]), 3)

    def test_upload_unconfirmed_twice_fails_without_leaving_residue(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        nb_id = self.fake.add_notebook(COLLECTION)
        self.fake.unconfirmed_uploads["[K1]"] = 2

        report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertEqual(self.keys(report["failed"]), ["K1"])
        self.assertIn("upload failed during start", report["failed"][0]["error"])
        self.assertEqual(self.keys(report["added"]), ["K2"])
        self.assertEqual(len([w for w in self.fake.writes if w[0] == "add_file"]), 3)
        self.assertEqual(self.fake.source_titles(nb_id), ["[K2] Energy and Policy"])
        self.assertEqual(len([w for w in self.fake.writes if w[0] == "delete_source"]), 2)

    def test_source_not_ready_within_180_seconds_is_failed(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        self.fake.processing_timeouts.add("[K1]")

        report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertEqual(self.keys(report["failed"]), ["K1"])
        self.assertIn("180", report["failed"][0]["error"])
        self.assertEqual(self.keys(report["added"]), ["K2"])
        self.assertEqual(report["renamed"], [])

    def test_progress_goes_to_stderr_and_stdout_is_only_json(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")

        result = self.run_sync("--collection", COLLECTION)

        self.report(result)  # stdout parses as one JSON document
        self.assertIn("[K1]", result.stderr)


    def test_dry_run_reports_the_plan_without_writing(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        self.zotero.add_paper(self.col, "K3", "No PDF here", pdf=False)
        nb_id = self.fake.add_notebook(COLLECTION, ["[K1] Green AI", "[GONE] Removed paper"])

        report = self.report(self.run_sync("--collection", COLLECTION, "--dry-run"))

        self.assertTrue(report["dry_run"])
        self.assertIsNone(report["aborted_reason"])
        self.assertEqual(report["notebook_id"], nb_id)
        self.assertEqual(self.keys(report["added"]), ["K2"])
        self.assertEqual(self.keys(report["skipped_existing"]), ["K1"])
        self.assertEqual(self.keys(report["missing_fulltext"]), ["K3"])
        self.assertEqual(self.keys(report["orphaned"]), ["GONE"])
        self.assertEqual(self.fake.writes, [])

    def test_dry_run_does_not_create_a_missing_notebook(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")

        report = self.report(self.run_sync("--collection", COLLECTION, "--dry-run"))

        self.assertIsNone(report["notebook_id"])
        self.assertEqual(report["notebook_title"], COLLECTION)
        self.assertFalse(report["created"])
        self.assertEqual(self.keys(report["added"]), ["K1"])
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(self.fake.notebook_ids(COLLECTION), [])


    def test_over_the_source_limit_uploads_nothing(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        nb_id = self.fake.add_notebook(COLLECTION, [f"[OLD{i}] Paper {i}" for i in range(299)])

        report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertIn("301", report["aborted_reason"])
        self.assertIn("300", report["aborted_reason"])
        self.assertEqual(report["added"], [])
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(len(self.fake.source_titles(nb_id)), 299)

    def test_exactly_at_the_source_limit_still_syncs(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.fake.add_notebook(COLLECTION, [f"[OLD{i}] Paper {i}" for i in range(299)])

        report = self.report(self.run_sync("--collection", COLLECTION))

        self.assertIsNone(report["aborted_reason"])
        self.assertEqual(self.keys(report["added"]), ["K1"])

    def test_manual_notebook_is_refused_without_force(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        nb_id = self.fake.add_notebook(
            "Manual research", ["Overview.pdf", "Research plan.pdf", "[K9] One synced paper"]
        )

        refused = self.report(self.run_sync("--collection", COLLECTION, "--notebook", "Manual research"))

        self.assertIn("--force", refused["aborted_reason"])
        self.assertEqual(refused["added"], [])
        self.assertEqual(self.fake.writes, [])

        forced = self.report(
            self.run_sync("--collection", COLLECTION, "--notebook", "Manual research", "--force")
        )

        self.assertIsNone(forced["aborted_reason"])
        self.assertEqual(self.keys(forced["added"]), ["K1"])
        self.assertIn("[K1] Green AI", self.fake.source_titles(nb_id))

    def test_several_collections_sync_into_one_notebook(self) -> None:
        other = self.zotero.add_collection("data-centres", key="DC000001")
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(other, "K2", "Data centre PUE")
        self.zotero.add_paper(other, "K1", "Green AI")  # the same item in both collections
        target = self.fake.add_notebook("度电智能")

        report = self.report(
            self.run_sync(
                "--collection", COLLECTION, "--collection", "DC000001", "--notebook", "度电智能"
            )
        )

        self.assertEqual(report["notebook_id"], target)
        self.assertEqual(self.keys(report["added"]), ["K1", "K2"])
        self.assertEqual(
            self.fake.source_titles(target), ["[K1] Green AI", "[K2] Data centre PUE"]
        )

    def test_several_collections_need_an_explicit_notebook(self) -> None:
        self.zotero.add_collection("data-centres")

        result = self.run_sync("--collection", COLLECTION, "--collection", "data-centres")

        self.assertEqual(result.exit_code, 1)
        self.assertIn("--notebook", result.stderr)
        self.assertEqual(self.fake.writes, [])

    def test_subcollections_only_with_recursive(self) -> None:
        sub = self.zotero.add_collection("pue", parent=self.col)
        subsub = self.zotero.add_collection("cooling", parent=sub)
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(sub, "K2", "PUE trends")
        self.zotero.add_paper(subsub, "K3", "Liquid cooling")

        flat = self.report(self.run_sync("--collection", COLLECTION, "--dry-run"))
        self.assertEqual(self.keys(flat["added"]), ["K1"])

        deep = self.report(self.run_sync("--collection", COLLECTION, "--recursive"))
        self.assertEqual(sorted(self.keys(deep["added"])), ["K1", "K2", "K3"])
        [nb_id] = self.fake.notebook_ids(COLLECTION)
        self.assertEqual(len(self.fake.source_titles(nb_id)), 3)

    def test_replace_deletes_the_old_source_then_uploads(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")
        nb_id = self.fake.add_notebook(COLLECTION, ["[K1] Green AI (preprint)", "[K2] Energy and Policy"])
        [old_k1, _] = self.fake.state[nb_id].sources

        report = self.report(self.run_sync("--collection", COLLECTION, "--replace", "K1"))

        self.assertEqual(self.keys(report["added"]), ["K1"])
        self.assertEqual(self.keys(report["skipped_existing"]), ["K2"])
        self.assertEqual(
            report["replaced"],
            [{"key": "K1", "title": "[K1] Green AI (preprint)", "source_id": old_k1.id}],
        )
        self.assertEqual(
            [w[0] for w in self.fake.writes], ["delete_source", "add_file"]
        )
        self.assertEqual(
            self.fake.source_titles(nb_id), ["[K2] Energy and Policy", "[K1] Green AI"]
        )

    def test_replace_on_dry_run_writes_nothing(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        self.fake.add_notebook(COLLECTION, ["[K1] Green AI (preprint)"])

        report = self.report(
            self.run_sync("--collection", COLLECTION, "--replace", "K1", "--dry-run")
        )

        self.assertEqual(self.keys(report["added"]), ["K1"])
        self.assertEqual(self.fake.writes, [])

    def test_orphaned_sources_are_reported_not_deleted(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")
        nb_id = self.fake.add_notebook(COLLECTION, ["[GONE] Removed paper", "[K1] Green AI"])

        report = self.report(self.run_sync("--collection", COLLECTION))

        [orphan] = report["orphaned"]
        self.assertEqual(orphan["key"], "GONE")
        self.assertEqual(orphan["title"], "[GONE] Removed paper")
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(
            self.fake.source_titles(nb_id), ["[GONE] Removed paper", "[K1] Green AI"]
        )


if __name__ == "__main__":
    unittest.main()
