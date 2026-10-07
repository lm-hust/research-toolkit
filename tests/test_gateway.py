"""
tests/test_gateway.py
Tests for NotebookLMGateway, NotebookLMPyAdapter, GeminiGroundingFallbackAdapter,
and grounded Q&A with DistilledEvidence.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from research_toolkit.synthesis.adapters import (
    GeminiGroundingFallbackAdapter,
    NotebookLMPyAdapter,
    get_default_gateway,
)


class TestNotebookLMPyAdapter(unittest.TestCase):
    def test_auth_from_single_line_json_env(self):
        """Parses single-line NOTEBOOKLM_AUTH_JSON environment variable."""
        mock_auth = {"account": "researcher@example.com", "master_token": "aas_mock_token_123"}
        with patch.dict(os.environ, {"NOTEBOOKLM_AUTH_JSON": json.dumps(mock_auth)}):
            adapter = NotebookLMPyAdapter()
            self.assertTrue(adapter.is_configured())
            self.assertEqual(adapter.auth_config.get("account"), "researcher@example.com")
            self.assertEqual(adapter.auth_config.get("master_token"), "aas_mock_token_123")

    def test_auth_from_master_token_file(self):
        """Loads credentials from master_token.json file if env var is absent."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            token_path = Path(tmp_dir) / "master_token.json"
            token_data = {"account": "file@example.com", "master_token": "file_token_456"}
            token_path.write_text(json.dumps(token_data), encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                adapter = NotebookLMPyAdapter(token_file=token_path)
                self.assertTrue(adapter.is_configured())
                self.assertEqual(adapter.auth_config.get("account"), "file@example.com")

    def test_gateway_lifecycle_mocked(self):
        """Tests create_notebook, upload_source, and query_sources flow."""
        adapter = NotebookLMPyAdapter(auth_config={"master_token": "test_tok"})
        with patch.object(adapter, "_execute_rpc") as mock_rpc:
            mock_rpc.side_effect = [
                {"status": "ok"},  # check_health
                {"notebook_id": "nb_001", "title": "GNN Survey"},  # create_notebook
                {"source_id": "src_001", "title": "paper.pdf"},  # upload_source
                {  # query_sources
                    "answer": "Graph Attention Networks use self-attention mechanisms.",
                    "citations": [
                        {
                            "quote": "We present graph attention networks (GATs)...",
                            "source_id": "src_001",
                            "source_title": "paper.pdf",
                            "start_offset": 12,
                            "end_offset": 58,
                        }
                    ],
                },
            ]

            self.assertTrue(adapter.check_health())

            nb = adapter.create_notebook("GNN Survey")
            self.assertEqual(nb.id, "nb_001")
            self.assertEqual(nb.title, "GNN Survey")

            src = adapter.upload_source("nb_001", Path("/tmp/paper.pdf"))
            self.assertEqual(src.id, "src_001")

            resp = adapter.query_sources("nb_001", "What are GATs?")
            self.assertIn("self-attention mechanisms", resp.answer)
            self.assertEqual(len(resp.citations), 1)
            citation = resp.citations[0]
            self.assertEqual(citation.source_id, "src_001")
            self.assertEqual(citation.start_offset, 12)
            self.assertEqual(citation.end_offset, 58)
            self.assertIn("We present graph attention networks", citation.quote)


class TestGeminiGroundingFallbackAdapter(unittest.TestCase):
    def test_gemini_fallback_configuration(self):
        """Configured when GEMINI_API_KEY is provided."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyMockKey123"}):
            adapter = GeminiGroundingFallbackAdapter()
            self.assertTrue(adapter.is_configured())
            self.assertEqual(adapter.api_key, "AIzaSyMockKey123")

    @patch("urllib.request.urlopen")
    def test_gemini_fallback_query(self, mock_urlopen):
        """Simulates querying Gemini API and extracting grounded citations."""
        adapter = GeminiGroundingFallbackAdapter(api_key="mock_key")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Diffusion models generate images by reversing noise."}
                        ]
                    },
                    "groundingMetadata": {
                        "groundingChunks": [
                            {"web": {"title": "DDPM Paper", "uri": "https://arxiv.org/abs/2006.11239"}}
                        ],
                        "groundingSupports": [
                            {
                                "groundingChunkIndices": [0],
                                "segment": {"startIndex": 0, "endIndex": 52, "text": "Diffusion models generate images by reversing noise."},
                            }
                        ],
                    },
                }
            ]
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ans = adapter.query_sources("nb_mock", "Explain diffusion models")
        self.assertIn("reversing noise", ans.answer)
        self.assertEqual(len(ans.citations), 1)
        self.assertEqual(ans.citations[0].start_offset, 0)
        self.assertEqual(ans.citations[0].end_offset, 52)


class TestGatewayFactory(unittest.TestCase):
    def test_prefers_notebooklm_when_auth_json_present(self):
        with patch.dict(os.environ, {"NOTEBOOKLM_AUTH_JSON": '{"master_token": "abc"}'}):
            gw = get_default_gateway()
            self.assertIsInstance(gw, NotebookLMPyAdapter)

    def test_falls_back_to_gemini_when_only_gemini_key_present(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIza123"}, clear=True):
            with patch.object(NotebookLMPyAdapter, "is_configured", return_value=False):
                gw = get_default_gateway()
                self.assertIsInstance(gw, GeminiGroundingFallbackAdapter)



if __name__ == "__main__":
    unittest.main()
