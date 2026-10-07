"""
tests/test_zotero.py
Unit tests for Zotero Personal Library Sync, PDF resolution, duplicate reconciliation,
and FulltextCheckpoint.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.zotero.client import ZoteroClient
from research_toolkit.zotero.manager import ZoteroManager
from research_toolkit.zotero.models import CheckpointReport, ZoteroCollection, ZoteroItem


class TestZoteroClient(unittest.TestCase):
    def test_strictly_enforces_user_library(self):
        """Must raise ValueError if group library is specified."""
        with self.assertRaises(ValueError):
            ZoteroClient(api_key="mock_key", user_id="12345", library_type="group")

    def test_user_library_url_structure(self):
        """Constructs endpoints strictly targeting /users/<user_id>/."""
        client = ZoteroClient(api_key="mock_key", user_id="12345", library_type="user")
        self.assertEqual(client.library_type, "user")
        self.assertEqual(client.base_path, "/users/12345")
        self.assertIn("https://api.zotero.org/users/12345", client.url("/collections"))

    @patch("urllib.request.urlopen")
    def test_get_or_create_collection(self, mock_urlopen):
        """Returns existing collection or creates new collection in user library."""
        client = ZoteroClient(api_key="mock_key", user_id="12345")

        # Mock GET returning empty list
        mock_resp_get = MagicMock()
        mock_resp_get.read.return_value = b"[]"
        mock_resp_get.__enter__.return_value = mock_resp_get

        # Mock POST returning newly created collection
        mock_resp_post = MagicMock()
        mock_resp_post.read.return_value = b'{"success": {"0": "COL_123"}, "successful": {"0": {"key": "COL_123", "data": {"name": "Graph Neural Networks"}}}}'
        mock_resp_post.__enter__.return_value = mock_resp_post

        mock_urlopen.side_effect = [mock_resp_get, mock_resp_post]

        col = client.get_or_create_collection("Graph Neural Networks")
        self.assertEqual(col.name, "Graph Neural Networks")
        self.assertEqual(col.key, "COL_123")
        self.assertEqual(col.web_url, "https://www.zotero.org/users/12345/collections/COL_123")

    @patch("urllib.request.urlopen")
    def test_find_existing_item_by_doi(self, mock_urlopen):
        """Finds existing item in library matching normalized DOI."""
        client = ZoteroClient(api_key="mock_key", user_id="12345")
        mock_resp = MagicMock()
        mock_items = [
            {
                "key": "EXISTING_KEY",
                "version": 10,
                "data": {
                    "title": "GNN Overview",
                    "DOI": "10.1016/j.gnn.2023",
                    "collections": ["COL_A"],
                },
            }
        ]
        mock_resp.read.return_value = json.dumps(mock_items).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        found = client.find_existing_item(doi="https://doi.org/10.1016/j.gnn.2023")
        self.assertIsNotNone(found)
        self.assertEqual(found["key"], "EXISTING_KEY")

    @patch("urllib.request.urlopen")
    def test_find_existing_item_no_title_fallback_when_doi_present(self, mock_urlopen):
        """When DOI is present but not found, do not fall back to title search."""
        client = ZoteroClient(api_key="mock_key", user_id="12345")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        found = client.find_existing_item(doi="10.1016/j.unknown.2023", title="GNN Overview")
        self.assertIsNone(found)
        # Verify urlopen called only once (for DOI), not for title
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_find_existing_item_by_title_when_no_doi(self, mock_urlopen):
        """When candidate has no DOI, fall back to normalized title search."""
        client = ZoteroClient(api_key="mock_key", user_id="12345")
        mock_resp = MagicMock()
        mock_items = [
            {
                "key": "TITLE_MATCH_KEY",
                "version": 10,
                "data": {
                    "title": "Graph Attention Networks",
                    "collections": [],
                },
            }
        ]
        mock_resp.read.return_value = json.dumps(mock_items).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        found = client.find_existing_item(doi=None, title="Graph Attention Networks")
        self.assertIsNotNone(found)
        self.assertEqual(found["key"], "TITLE_MATCH_KEY")

    @patch("urllib.request.urlopen")
    def test_add_item_to_collection_with_dict(self, mock_urlopen):
        """Accepts raw item dict and appends collection."""
        client = ZoteroClient(api_key="mock_key", user_id="12345")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        raw_item = {
            "key": "ITEM_KEY_1",
            "version": 12,
            "data": {
                "collections": ["COL_1"],
            },
        }

        success = client.add_item_to_collection(item=raw_item, collection_key="COL_2")
        self.assertTrue(success)
        self.assertIn("COL_2", raw_item["data"]["collections"])

    @patch("urllib.request.urlopen")
    def test_add_item_to_collection_with_key(self, mock_urlopen):
        """Appends new collection to existing item collections without overwriting other fields."""
        client = ZoteroClient(api_key="mock_key", user_id="12345")
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success = client.add_item_to_collection(
            item_key="EXISTING_KEY",
            collection_key="NEW_COL",
            version=10,
            existing_collections=["COL_A"],
        )
        self.assertTrue(success)


class TestZoteroManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.temp_dir) / "storage"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.mock_client = MagicMock(spec=ZoteroClient)
        self.mock_client.library_type = "user"
        self.mock_client.user_id = "12345"

        self.manager = ZoteroManager(
            client=self.mock_client,
            storage_dir=self.storage_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_sync_candidates_inserts_canonical_doi(self):
        """PaperCandidate is converted to Zotero schema with clean canonical DOI without proxy prefix."""
        col = ZoteroCollection(key="COL_123", name="GNN Research")
        self.mock_client.get_or_create_collection.return_value = col
        self.mock_client.create_items.return_value = [{"key": "ITEM_001"}]

        candidate = PaperCandidate(
            paper_id="p1",
            title="Graph Attention Networks",
            year=2018,
            authors=["Petar Velickovic", "Guillem Cucurull"],
            citation_count=5000,
            doi="10.48550/arXiv.1710.10903",
            venue="ICLR",
            abstract="We present graph attention networks...",
        )

        created_items = self.manager.sync_candidates(
            collection_name="GNN Research",
            candidates=[candidate],
            auto_download_oa=False,
        )

        self.mock_client.create_items.assert_called_once()
        payload = self.mock_client.create_items.call_args[0][0]
        self.assertEqual(len(payload), 1)
        item_data = payload[0]

        # Verify clean canonical DOI & URL
        self.assertEqual(item_data["DOI"], "10.48550/arxiv.1710.10903")
        self.assertEqual(item_data["url"], "https://doi.org/10.48550/arxiv.1710.10903")
        self.assertNotIn("libproxy.ucl.ac.uk", item_data["url"])
        self.assertIn("COL_123", item_data["collections"])

    def test_sync_candidates_persists_citations_extra_and_tags(self):
        """Item payload includes citations in extra field and citation tier tags."""
        col = ZoteroCollection(key="COL_123", name="AI Research")
        self.mock_client.get_or_create_collection.return_value = col
        self.mock_client.create_items.return_value = [{"key": "ITEM_001"}]

        candidate = PaperCandidate(
            paper_id="p1",
            title="Highly Cited Paper",
            year=2023,
            citation_count=150,
            influential_citation_count=25,
            composite_score=0.885,
            venue="Nature",
            is_review=True,
            doi="10.1038/nature12345",
        )

        self.manager.sync_candidates(
            collection_name="AI Research",
            candidates=[candidate],
            auto_download_oa=False,
        )

        payload = self.mock_client.create_items.call_args[0][0]
        item_data = payload[0]

        # Verify extra field contains citations and score
        self.assertIn("extra", item_data)
        self.assertIn("Citations: 150", item_data["extra"])
        self.assertIn("Influential Citations: 25", item_data["extra"])
        self.assertIn("Discovery Score: 0.885", item_data["extra"])

        # Verify citation tier tag
        tags = [t["tag"] for t in item_data["tags"]]
        self.assertIn("cites:>100", tags)
        self.assertIn("type/review", tags)
        self.assertIn("type/peer-reviewed", tags)

    def test_sync_to_collection_reuses_existing_items(self):
        """If a candidate already exists in Zotero, it is appended to collection without duplicating."""
        col = ZoteroCollection(key="COL_TARGET", name="GNN Research", user_id="12345")
        self.mock_client.get_or_create_collection.return_value = col

        existing_item = {
            "key": "EXISTING_ITEM_KEY",
            "version": 5,
            "data": {
                "title": "Existing GNN Paper",
                "DOI": "10.1000/existing",
                "collections": ["OLD_COL"],
            },
        }

        def mock_find(doi=None, title=None):
            if doi and "10.1000/existing" in doi:
                return existing_item
            return None

        self.mock_client.find_existing_item.side_effect = mock_find
        self.mock_client.add_item_to_collection.return_value = True
        self.mock_client.create_items.return_value = [{"key": "NEW_ITEM_KEY"}]

        cand_existing = PaperCandidate(
            paper_id="p1",
            title="Existing GNN Paper",
            doi="10.1000/existing",
        )
        cand_new = PaperCandidate(
            paper_id="p2",
            title="Brand New Paper",
            doi="10.1000/brand_new",
        )

        collection, result = self.manager.sync_to_collection(
            collection_name="GNN Research",
            candidates=[cand_existing, cand_new],
            auto_download_oa=False,
        )

        self.assertEqual(collection.key, "COL_TARGET")
        self.mock_client.add_item_to_collection.assert_called_once_with(
            item=existing_item,
            collection_key="COL_TARGET",
        )
        self.mock_client.create_items.assert_called_once()
        created_payload = self.mock_client.create_items.call_args[0][0]
        self.assertEqual(len(created_payload), 1)
        self.assertEqual(created_payload[0]["DOI"], "10.1000/brand_new")

        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.reused_count, 1)
        self.assertEqual(result.total_count, 2)

    def test_local_storage_pdf_probing(self):
        """Verifies local ~/Zotero/storage/<key>/*.pdf detection."""
        # Create a mock local storage attachment folder with a PDF
        attach_key = "ATT_999"
        attach_dir = self.storage_dir / attach_key
        attach_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = attach_dir / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock content")

        found_path = self.manager.find_local_pdf(attach_key)
        self.assertIsNotNone(found_path)
        self.assertEqual(found_path, pdf_file)

        # Probing non-existent attachment returns None
        self.assertIsNone(self.manager.find_local_pdf("ATT_NONEXISTENT"))

    def test_reconcile_duplicates_by_canonical_doi(self):
        """Connector duplicate with PDF attachment is adopted as winner over skeleton item."""
        # Item 1: Toolkit skeleton item (no PDF)
        item_skeleton = ZoteroItem(
            key="ITEM_SKEL",
            title="Geometric Deep Learning",
            doi="10.1038/s41586-021-03819-2",
            has_pdf=False,
            tags=["checkpoint/awaiting-fulltext"],
        )
        # Item 2: Connector imported duplicate (has PDF)
        item_connector = ZoteroItem(
            key="ITEM_CONN",
            title="Geometric deep learning: Grids, groups, graphs, geodesics",
            doi="https://doi.org/10.1038/s41586-021-03819-2",
            has_pdf=True,
            pdf_path="/path/to/storage/XYZ/paper.pdf",
            tags=[],
        )

        reconciled, count = self.manager.reconcile_duplicates([item_skeleton, item_connector])

        self.assertEqual(count, 1)
        self.assertEqual(len(reconciled), 1)
        winner = reconciled[0]
        self.assertTrue(winner.has_pdf)
        self.assertEqual(winner.key, "ITEM_CONN")
        self.assertEqual(winner.doi, "10.1038/s41586-021-03819-2")

    def test_checkpoint_scan_segregates_ready_and_missing(self):
        """FulltextCheckpoint properly partitions items into ready and missing with canonical DOI links."""
        # Mock collection items
        attach_key = "ATT_READY"
        attach_dir = self.storage_dir / attach_key
        attach_dir.mkdir(parents=True, exist_ok=True)
        (attach_dir / "article.pdf").write_bytes(b"%PDF-1.4")

        raw_items = [
            {
                "key": "P1",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Ready Paper",
                    "DOI": "10.1000/ready",
                },
            },
            {
                "key": attach_key,
                "data": {
                    "itemType": "attachment",
                    "parentItem": "P1",
                    "contentType": "application/pdf",
                },
            },
            {
                "key": "P2",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Missing Paper",
                    "DOI": "10.1000/missing",
                },
            },
        ]
        self.mock_client.get_collection_items.return_value = raw_items

        report = self.manager.scan_collection_checkpoint("col_key", "Test Collection")
        self.assertEqual(report.total_items, 2)
        self.assertEqual(len(report.ready_items), 1)
        self.assertEqual(len(report.missing_items), 1)
        self.assertEqual(report.ready_items[0].key, "P1")
        self.assertEqual(report.missing_items[0].key, "P2")
        self.assertEqual(report.missing_items[0].doi_url, "https://doi.org/10.1000/missing")


if __name__ == "__main__":
    unittest.main()
