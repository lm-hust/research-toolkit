"""
tests/test_sync_notebook_fulltext_cli.py
sync-notebook full-text fallback: which file (or URL) each Zotero item contributes.
Order: first PDF, then EPUB, then HTML snapshot (uploaded as markdown), then DOI/URL only
with --allow-url; otherwise the item is reported in missing_fulltext.
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


class SyncNotebookFulltextTest(unittest.TestCase):
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
            return CliRunner().invoke(cli, ["sync-notebook", "--collection", COLLECTION, *args])

    def report(self, result: Result) -> dict[str, Any]:
        self.assertEqual(result.exit_code, 0, result.output)
        return json.loads(result.stdout)

    @staticmethod
    def keys(entries: list[dict[str, Any]]) -> list[str]:
        return [e["key"] for e in entries]

    def test_only_the_first_pdf_is_uploaded_and_other_attachments_are_counted(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Green AI", pdf=False)
        self.zotero.add_pdf(self.col, "K1", "main.pdf")
        self.zotero.add_pdf(self.col, "K1", "supplement.pdf")
        self.zotero.add_html_snapshot(self.col, "K1", "<p>snapshot</p>")
        self.zotero.add_paper(self.col, "K2", "Energy and Policy")

        report = self.report(self.run_sync())

        self.assertEqual(self.keys(report["added"]), ["K1", "K2"])
        self.assertEqual(self.fake.uploaded_paths[0].name, "main.pdf")
        self.assertEqual(
            report["extra_attachments"], [{"key": "K1", "title": "Green AI", "count": 2}]
        )

    def test_epub_is_uploaded_when_there_is_no_pdf(self) -> None:
        self.zotero.add_paper(self.col, "K1", "A Book", pdf=False)
        self.zotero.add_html_snapshot(self.col, "K1", "<p>catalogue page</p>")
        self.zotero.add_epub(self.col, "K1", "book.epub")

        report = self.report(self.run_sync())

        self.assertEqual(report["added"], [{"key": "K1", "title": "A Book", "kind": "epub"}])
        [nb_id] = self.fake.notebook_ids(COLLECTION)
        self.assertEqual(self.fake.source_titles(nb_id), ["[K1] A Book"])
        self.assertEqual([p.name for p in self.fake.uploaded_paths], ["book.epub"])
        self.assertEqual(
            report["extra_attachments"], [{"key": "K1", "title": "A Book", "count": 1}]
        )

    def test_html_snapshot_is_uploaded_as_markdown_with_the_keyed_title(self) -> None:
        self.zotero.add_paper(self.col, "K1", "储能政策解读", pdf=False)
        self.zotero.add_link(self.col, "K1")
        self.zotero.add_html_snapshot(
            self.col,
            "K1",
            "<html><body><h1>储能政策</h1><p>Capacity is <b>40 GW</b>.</p></body></html>",
            filename="S1364032126004028.html",
        )

        report = self.report(self.run_sync())

        self.assertEqual(report["added"], [{"key": "K1", "title": "储能政策解读", "kind": "html"}])
        [nb_id] = self.fake.notebook_ids(COLLECTION)
        self.assertEqual(self.fake.source_titles(nb_id), ["[K1] 储能政策解读"])
        [uploaded] = self.fake.uploaded_paths
        self.assertEqual(uploaded.suffix, ".md")
        [markdown] = self.fake.uploaded_contents
        self.assertIn("# 储能政策", markdown.decode())
        self.assertIn("**40 GW**", markdown.decode())
        self.assertNotIn("<p>", markdown.decode())
        self.assertEqual(
            report["extra_attachments"], [{"key": "K1", "title": "储能政策解读", "count": 1}]
        )

    def test_item_without_any_file_is_missing_fulltext(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Linked only", pdf=False)
        self.zotero.add_link(self.col, "K1")
        self.zotero.add_paper(self.col, "K2", "Bare record", pdf=False)

        report = self.report(self.run_sync())

        self.assertEqual(report["added"], [])
        self.assertEqual(self.keys(report["missing_fulltext"]), ["K1", "K2"])
        self.assertEqual(report["extra_attachments"], [])
        self.assertEqual(self.fake.writes, [("create_notebook", COLLECTION)])

    def test_doi_and_url_are_not_used_without_allow_url(self) -> None:
        self.zotero.add_paper(self.col, "K1", "Paywalled", pdf=False, doi="10.1000/xyz")
        self.zotero.add_paper(self.col, "K2", "Blog post", pdf=False, url="https://example.org/p")

        report = self.report(self.run_sync())

        self.assertEqual(report["added"], [])
        self.assertEqual(self.keys(report["missing_fulltext"]), ["K1", "K2"])

    def test_allow_url_adds_doi_or_url_as_a_url_source(self) -> None:
        self.zotero.add_paper(
            self.col, "K1", "Paywalled", pdf=False, doi="10.1000/xyz", url="https://pub.example/x"
        )
        self.zotero.add_paper(self.col, "K2", "Blog post", pdf=False, url="https://example.org/p")
        self.zotero.add_paper(self.col, "K3", "Has a PDF", doi="10.1000/pdf")
        self.zotero.add_paper(self.col, "K4", "Nothing at all", pdf=False)

        report = self.report(self.run_sync("--allow-url"))

        self.assertEqual(
            report["added"],
            [
                {"key": "K1", "title": "Paywalled", "kind": "url"},
                {"key": "K2", "title": "Blog post", "kind": "url"},
                {"key": "K3", "title": "Has a PDF", "kind": "pdf"},
            ],
        )
        self.assertEqual(self.keys(report["missing_fulltext"]), ["K4"])
        nb_id = report["notebook_id"]
        self.assertIn(
            ("add_url", nb_id, "[K1] Paywalled", "https://doi.org/10.1000/xyz"), self.fake.writes
        )
        self.assertIn(
            ("add_url", nb_id, "[K2] Blog post", "https://example.org/p"), self.fake.writes
        )
        self.assertEqual(
            self.fake.source_titles(nb_id),
            ["[K1] Paywalled", "[K2] Blog post", "[K3] Has a PDF"],
        )


if __name__ == "__main__":
    unittest.main()
