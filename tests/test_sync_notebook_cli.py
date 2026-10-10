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
from unittest.mock import patch

from click.testing import CliRunner, Result
from notebook_fakes import OPEN_CLIENT, FakeNotebookClient
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

    def test_progress_goes_to_stderr_and_stdout_is_only_json(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI")

        result = self.run_sync("--collection", COLLECTION)

        self.report(result)  # stdout parses as one JSON document
        self.assertIn("[K1]", result.stderr)


if __name__ == "__main__":
    unittest.main()
