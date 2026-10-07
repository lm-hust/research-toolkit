"""
tests/test_mcp.py
Unit tests for MCP server tool functions and tool manifest.
"""

import unittest
from unittest.mock import MagicMock, patch

from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.mcp.tools import (
    ask_notebook,
    get_tools_manifest,
    search_literature,
    verify_checkpoint,
)
from research_toolkit.synthesis.models import DistilledEvidence, GroundedAnswer
from research_toolkit.zotero.models import CheckpointReport, ZoteroItem


class TestMcpTools(unittest.TestCase):
    def test_tools_manifest_has_all_capabilities(self):
        manifest = get_tools_manifest()
        tool_names = [t["name"] for t in manifest]
        self.assertIn("search_literature", tool_names)
        self.assertIn("verify_checkpoint", tool_names)
        self.assertIn("sync_notebook", tool_names)
        self.assertIn("ask_notebook", tool_names)

        # Check JSON schema format for search_literature
        search_tool = next(t for t in manifest if t["name"] == "search_literature")
        self.assertIn("parameters", search_tool)
        self.assertIn("properties", search_tool["parameters"])
        self.assertIn("topic", search_tool["parameters"]["properties"])

    @patch("research_toolkit.mcp.tools.ZoteroManager")
    @patch("research_toolkit.mcp.tools.DiscoveryService")
    def test_search_literature_tool(self, mock_service_cls, mock_mgr_cls):
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.search_and_rank.return_value = [
            PaperCandidate(
                paper_id="p1",
                title="Graph Attention Networks",
                year=2018,
                doi="10.1000/gat",
                composite_score=0.92,
                is_review=False,
            )
        ]
        mock_mgr = MagicMock()
        mock_mgr_cls.return_value = mock_mgr
        from research_toolkit.zotero.models import ZoteroCollection
        mock_mgr.sync_to_collection.return_value = (
            ZoteroCollection(key="COL_MCP_1", name="research/gnn", user_id="12345"),
            [{"key": "it1"}]
        )

        result = search_literature("GNN", limit=5)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["collection_id"], "COL_MCP_1")
        self.assertEqual(result["collection_url"], "https://www.zotero.org/users/12345/collections/COL_MCP_1")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["title"], "Graph Attention Networks")

    @patch("research_toolkit.mcp.tools.ZoteroManager")
    def test_verify_checkpoint_tool(self, mock_mgr_cls):
        mock_mgr = MagicMock()
        mock_mgr_cls.return_value = mock_mgr
        mock_mgr.scan_collection_checkpoint.return_value = CheckpointReport(
            collection_key="col_1",
            collection_name="test_col",
            total_items=2,
            ready_items=[ZoteroItem(key="k1", title="Paper 1", has_pdf=True)],
            missing_items=[ZoteroItem(key="k2", title="Paper 2", doi="10.1000/p2", has_pdf=False)],
        )

        result = verify_checkpoint("col_1")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["ready_count"], 1)
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["missing_items"][0]["doi"], "10.1000/p2")

    @patch("research_toolkit.mcp.tools.get_default_gateway")
    def test_ask_notebook_tool(self, mock_gw_getter):
        mock_gw = MagicMock()
        mock_gw_getter.return_value = mock_gw
        mock_gw.query_sources.return_value = GroundedAnswer(
            answer="GNN explanation",
            citations=[
                DistilledEvidence(
                    quote="key quote",
                    source_id="src_1",
                    source_title="GNN Survey",
                    start_offset=0,
                    end_offset=9,
                )
            ],
            notebook_id="nb_1",
        )

        result = ask_notebook(query="How does GNN work?", notebook_id="nb_1")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["answer"], "GNN explanation")
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0]["quote"], "key quote")


if __name__ == "__main__":
    unittest.main()
