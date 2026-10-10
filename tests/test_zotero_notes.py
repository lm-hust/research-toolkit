"""
tests/test_zotero_notes.py
ZoteroClient child-note writes, tested at the HTTP boundary by patching urlopen.
"""

import json
import unittest
import urllib.error
from email.message import Message
from typing import Any
from unittest.mock import MagicMock, patch

from research_toolkit.zotero.client import ZoteroClient, ZoteroWriteError


def response(body: Any) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__.return_value = resp
    return resp


class CreateChildNoteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = ZoteroClient(api_key="k", user_id="12345")

    @patch("urllib.request.urlopen")
    def test_posts_a_tagged_note_under_the_parent_and_returns_its_key(self, urlopen: MagicMock) -> None:
        urlopen.return_value = response(
            {"successful": {"0": {"key": "NOTE1234", "version": 7}}, "success": {"0": "NOTE1234"}, "failed": {}}
        )

        key = self.client.create_child_note("PAPER001", "<h1>Gemini 初读：X</h1>", ["gemini-skim/ai-note"])

        self.assertEqual(key, "NOTE1234")
        req = urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.full_url, "https://api.zotero.org/users/12345/items")
        self.assertEqual(
            json.loads(req.data),
            [
                {
                    "itemType": "note",
                    "parentItem": "PAPER001",
                    "note": "<h1>Gemini 初读：X</h1>",
                    "tags": [{"tag": "gemini-skim/ai-note"}],
                }
            ],
        )

    @patch("urllib.request.urlopen")
    def test_a_rejected_write_raises(self, urlopen: MagicMock) -> None:
        urlopen.return_value = response(
            {"successful": {}, "success": {}, "failed": {"0": {"code": 400, "message": "Parent item not found"}}}
        )

        with self.assertRaises(ZoteroWriteError) as ctx:
            self.client.create_child_note("NOPE0000", "<p>x</p>", [])
        self.assertIn("Parent item not found", str(ctx.exception))


class FindChildNotesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = ZoteroClient(api_key="k", user_id="12345")

    @patch("urllib.request.urlopen")
    def test_returns_the_parents_notes_carrying_the_tag_with_their_versions(self, urlopen: MagicMock) -> None:
        urlopen.return_value = response(
            [
                {"key": "NOTE1234", "version": 41, "data": {"key": "NOTE1234", "version": 41, "itemType": "note",
                 "note": "<h1>Gemini 初读：X</h1>", "tags": [{"tag": "gemini-skim/ai-note"}]}},
                {"key": "NOTE9999", "version": 12, "data": {"key": "NOTE9999", "version": 12, "itemType": "note",
                 "note": "<p>mine</p>", "tags": [{"tag": "Gemini-skim/AI-note"}, {"tag": "x"}]}},
            ]
        )

        notes = self.client.find_child_notes("PAPER001", "gemini-skim/ai-note")

        self.assertEqual([(n["key"], n["version"]) for n in notes], [("NOTE1234", 41)])
        req = urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "GET")
        self.assertTrue(req.full_url.startswith("https://api.zotero.org/users/12345/items/PAPER001/children?"))
        self.assertIn("itemType=note", req.full_url)
        self.assertIn("tag=gemini-skim%2Fai-note", req.full_url)

    @patch("urllib.request.urlopen")
    def test_no_tagged_note_gives_an_empty_list(self, urlopen: MagicMock) -> None:
        urlopen.return_value = response([])

        self.assertEqual(self.client.find_child_notes("PAPER001", "gemini-skim/ai-note"), [])


class UpdateNoteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = ZoteroClient(api_key="k", user_id="12345")

    @patch("urllib.request.urlopen")
    def test_patches_only_the_note_body_guarded_by_the_version(self, urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.read.return_value = b""
        resp.__enter__.return_value = resp
        urlopen.return_value = resp

        self.client.update_note("NOTE1234", "<h1>Gemini 初读：X</h1><p>new</p>", 41)

        req = urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "PATCH")
        self.assertEqual(req.full_url, "https://api.zotero.org/users/12345/items/NOTE1234")
        self.assertEqual(req.get_header("If-unmodified-since-version"), "41")
        self.assertEqual(json.loads(req.data), {"note": "<h1>Gemini 初读：X</h1><p>new</p>"})

    @patch("urllib.request.urlopen")
    def test_a_version_conflict_raises_a_write_error(self, urlopen: MagicMock) -> None:
        urlopen.side_effect = urllib.error.HTTPError(
            "https://api.zotero.org/users/12345/items/NOTE1234", 412, "Precondition Failed", Message(), None
        )

        with self.assertRaises(ZoteroWriteError) as ctx:
            self.client.update_note("NOTE1234", "<p>x</p>", 41)
        self.assertIn("NOTE1234", str(ctx.exception))
        self.assertIn("412", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
