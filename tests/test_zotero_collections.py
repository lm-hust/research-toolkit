"""
tests/test_zotero_collections.py
ZoteroClient collection lookup and paged listing, tested at the urlopen seam.
"""

import json
import unittest
import urllib.parse
from typing import Any
from unittest.mock import MagicMock, patch

from research_toolkit.zotero.client import ZoteroClient


def _resp(body: Any) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__.return_value = resp
    return resp


def _query(mock_urlopen: MagicMock, call_index: int) -> dict[str, list[str]]:
    req = mock_urlopen.call_args_list[call_index][0][0]
    return urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)


def _rows(prefix: str, n: int) -> list[dict[str, Any]]:
    return [{"key": f"{prefix}{i}", "data": {"itemType": "journalArticle"}} for i in range(n)]


class TestCollectionItemsPaging(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_collection_items_are_fetched_past_the_first_page(self, mock_urlopen):
        mock_urlopen.side_effect = [_resp(_rows("A", 100)), _resp(_rows("B", 34))]
        client = ZoteroClient(api_key="k", user_id="1")

        items = client.get_collection_items("KS2HSWPE")

        self.assertEqual(len(items), 134)
        self.assertEqual(_query(mock_urlopen, 0)["start"], ["0"])
        self.assertEqual(_query(mock_urlopen, 1)["start"], ["100"])

    @patch("urllib.request.urlopen")
    def test_short_first_page_makes_one_request(self, mock_urlopen):
        mock_urlopen.side_effect = [_resp(_rows("A", 34))]
        client = ZoteroClient(api_key="k", user_id="1")

        self.assertEqual(len(client.get_collection_items("KS2HSWPE")), 34)
        self.assertEqual(mock_urlopen.call_count, 1)


class TestGetCollection(unittest.TestCase):
    COLLECTIONS = [
        {"key": "KS2HSWPE", "version": 7, "data": {"name": "intelligence-per-kwh", "parentCollection": False}},
        {"key": "ZZZZ0001", "version": 3, "data": {"name": "Other", "parentCollection": "KS2HSWPE"}},
    ]

    @patch("urllib.request.urlopen")
    def test_resolves_name_case_insensitively(self, mock_urlopen):
        mock_urlopen.side_effect = [_resp(self.COLLECTIONS)]
        client = ZoteroClient(api_key="k", user_id="1")

        col = client.get_collection("Intelligence-Per-KWH")

        assert col is not None
        self.assertEqual(col.key, "KS2HSWPE")
        self.assertEqual(col.name, "intelligence-per-kwh")

    @patch("urllib.request.urlopen")
    def test_resolves_exact_key(self, mock_urlopen):
        mock_urlopen.side_effect = [_resp(self.COLLECTIONS)]
        client = ZoteroClient(api_key="k", user_id="1")

        col = client.get_collection("ZZZZ0001")

        assert col is not None
        self.assertEqual(col.name, "Other")
        self.assertEqual(col.parent_collection, "KS2HSWPE")

    @patch("urllib.request.urlopen")
    def test_unknown_collection_returns_none_without_creating(self, mock_urlopen):
        mock_urlopen.side_effect = [_resp(self.COLLECTIONS)]
        client = ZoteroClient(api_key="k", user_id="1")

        self.assertIsNone(client.get_collection("missing"))
        methods = [c[0][0].get_method() for c in mock_urlopen.call_args_list]
        self.assertEqual(methods, ["GET"])

    @patch("urllib.request.urlopen")
    def test_ambiguous_name_raises(self, mock_urlopen):
        dup = {"key": "DUP00001", "version": 1, "data": {"name": "Other", "parentCollection": False}}
        mock_urlopen.side_effect = [_resp([*self.COLLECTIONS, dup])]
        client = ZoteroClient(api_key="k", user_id="1")

        with self.assertRaises(ValueError) as ctx:
            client.get_collection("other")
        self.assertIn("DUP00001", str(ctx.exception))
        self.assertIn("ZZZZ0001", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()


class TestGetSubcollections(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_lists_direct_subcollections_of_a_key(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _resp([{"key": "SUB00001", "version": 2, "data": {"name": "pue", "parentCollection": "KS2HSWPE"}}])
        ]
        client = ZoteroClient(api_key="k", user_id="1")

        [sub] = client.get_subcollections("KS2HSWPE")

        self.assertEqual((sub.key, sub.name, sub.parent_collection), ("SUB00001", "pue", "KS2HSWPE"))
        req = mock_urlopen.call_args_list[0][0][0]
        self.assertEqual(req.get_method(), "GET")
        self.assertIn("/users/1/collections/KS2HSWPE/collections?", req.full_url)
