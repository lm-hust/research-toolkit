"""
tests/test_zotero_notes.py
ZoteroClient child-note writes, tested at the HTTP boundary by patching urlopen.
"""

import json
import unittest
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


if __name__ == "__main__":
    unittest.main()
