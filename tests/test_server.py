"""
tests/test_server.py
Unit tests for DualStackGateway (FastAPI + FastMCP + Bearer Auth).
"""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from research_toolkit.mcp.server import create_app


class TestDualStackServer(unittest.TestCase):
    def setUp(self):
        # Configure test api key
        self.test_key = "secret_test_token_123"
        os.environ["RESEARCH_TOOLKIT_API_KEY"] = self.test_key
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        os.environ.pop("RESEARCH_TOOLKIT_API_KEY", None)

    def test_health_check_public(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "research-toolkit-gateway")

    def test_openapi_schema_public(self):
        resp = self.client.get("/openapi.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("paths", data)
        self.assertIn("/api/v1/search", data["paths"])
        self.assertIn("/api/v1/checkpoint", data["paths"])
        self.assertIn("/api/v1/sync-notebook", data["paths"])
        self.assertIn("/api/v1/ask", data["paths"])

    def test_unauthorized_access_rejected(self):
        resp = self.client.post("/api/v1/search", json={"topic": "GNN"})
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid or missing authentication token", resp.json()["detail"])

    @patch("research_toolkit.mcp.server.search_literature")
    def test_authorized_access_with_bearer_header(self, mock_search):
        mock_search.return_value = {"status": "success", "count": 1, "candidates": []}

        headers = {"Authorization": f"Bearer {self.test_key}"}
        resp = self.client.post(
            "/api/v1/search",
            json={"topic": "Graph Neural Networks", "limit": 5},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        mock_search.assert_called_once_with(
            topic="Graph Neural Networks", limit=5, collection_name=None
        )

    @patch("research_toolkit.mcp.server.search_literature")
    def test_authorized_access_with_query_token(self, mock_search):
        mock_search.return_value = {"status": "success", "count": 1, "candidates": []}

        resp = self.client.post(
            f"/api/v1/search?token={self.test_key}",
            json={"topic": "Attention Mechanism"},
        )
        self.assertEqual(resp.status_code, 200)
        mock_search.assert_called_once_with(
            topic="Attention Mechanism", limit=8, collection_name=None
        )

    @patch("research_toolkit.mcp.server.verify_checkpoint")
    def test_checkpoint_endpoint(self, mock_verify):
        mock_verify.return_value = {"status": "success", "total": 2, "ready_count": 2}

        headers = {"Authorization": f"Bearer {self.test_key}"}
        resp = self.client.post(
            "/api/v1/checkpoint",
            json={"collection": "my_collection"},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total"], 2)
        mock_verify.assert_called_once_with(collection="my_collection")

    @patch("research_toolkit.mcp.server.sync_notebook")
    def test_sync_notebook_endpoint(self, mock_sync):
        mock_sync.return_value = {"status": "success", "uploaded_count": 3}

        headers = {"Authorization": f"Bearer {self.test_key}"}
        resp = self.client.post(
            "/api/v1/sync-notebook",
            json={"collection": "my_collection", "allow_partial": True},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["uploaded_count"], 3)
        mock_sync.assert_called_once_with(collection="my_collection", allow_partial=True)

    @patch("research_toolkit.mcp.server.ask_notebook")
    def test_ask_notebook_endpoint(self, mock_ask):
        mock_ask.return_value = {"status": "success", "answer": "Synthesized insight"}

        headers = {"Authorization": f"Bearer {self.test_key}"}
        resp = self.client.post(
            "/api/v1/ask",
            json={"query": "What is oversmoothing?", "notebook_id": "nb_123"},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["answer"], "Synthesized insight")
        mock_ask.assert_called_once_with(query="What is oversmoothing?", notebook_id="nb_123")


if __name__ == "__main__":
    unittest.main()
