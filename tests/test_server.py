"""
tests/test_server.py
Unit tests for DualStackGateway (FastAPI + FastMCP + Bearer Auth).
"""

import json
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
        self.assertNotIn("/api/v1/sync-notebook", data["paths"])
        self.assertNotIn("/api/v1/ask", data["paths"])

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


MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _jsonrpc(method: str, params: dict, req_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}


def _parse_mcp_response(resp) -> dict:
    """Streamable HTTP replies are either plain JSON or a single SSE 'data:' event."""
    if resp.headers.get("content-type", "").startswith("application/json"):
        return resp.json()
    data_lines = [line[5:].strip() for line in resp.text.splitlines() if line.startswith("data:")]
    return json.loads(data_lines[-1])


class TestMcpStreamableHttp(unittest.TestCase):
    def setUp(self):
        self.test_key = "secret_test_token_123"
        os.environ["RESEARCH_TOOLKIT_API_KEY"] = self.test_key
        # Context-managed client runs the lifespan that starts the MCP session manager.
        self.client = TestClient(create_app())
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        os.environ.pop("RESEARCH_TOOLKIT_API_KEY", None)

    def test_missing_token_rejected(self):
        resp = self.client.post(
            "/mcp/http",
            json=_jsonrpc("tools/list", {}),
            headers=MCP_HEADERS,
        )
        self.assertEqual(resp.status_code, 401)

    def test_wrong_token_rejected(self):
        resp = self.client.post(
            "/mcp/http?token=wrong",
            json=_jsonrpc("tools/list", {}),
            headers=MCP_HEADERS,
        )
        self.assertEqual(resp.status_code, 401)

    def test_initialize_with_query_token(self):
        resp = self.client.post(
            f"/mcp/http?token={self.test_key}",
            json=_jsonrpc(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            ),
            headers=MCP_HEADERS,
        )
        self.assertEqual(resp.status_code, 200)
        result = _parse_mcp_response(resp)["result"]
        self.assertEqual(result["serverInfo"]["name"], "research-toolkit")

    def test_tools_list_with_bearer_header(self):
        resp = self.client.post(
            "/mcp/http",
            json=_jsonrpc("tools/list", {}, req_id=2),
            headers={**MCP_HEADERS, "Authorization": f"Bearer {self.test_key}"},
        )
        self.assertEqual(resp.status_code, 200)
        tool_names = {t["name"] for t in _parse_mcp_response(resp)["result"]["tools"]}
        self.assertEqual(
            tool_names,
            {"search_literature", "verify_checkpoint"},
        )

    def test_legacy_sse_requires_token(self):
        resp = self.client.get("/mcp/sse")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
