"""
src/research_toolkit/mcp/server.py
Dual-Stack Gateway daemon providing Model Context Protocol (MCP) Streamable HTTP and
Server-Sent Events (SSE) transports plus OpenAPI 3.0 REST endpoints for Claude and
ChatGPT Actions (ADR-0006).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from research_toolkit.mcp.tools import (
    ask_notebook,
    search_literature,
    sync_notebook,
    verify_checkpoint,
)

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Request Models for ChatGPT Actions / REST Ingress
# ---------------------------------------------------------------------------


class SearchLiteratureRequest(BaseModel):
    topic: str = Field(..., description="Research subject or academic search query string")
    limit: int = Field(8, description="Maximum number of ranked papers to return (default: 8)")
    collection_name: Optional[str] = Field(
        None, description="Optional custom Zotero collection name"
    )


class VerifyCheckpointRequest(BaseModel):
    collection: str = Field(..., description="Target Zotero collection name or key to inspect")


class SyncNotebookRequest(BaseModel):
    collection: str = Field(..., description="Target Zotero collection name or key")
    allow_partial: bool = Field(
        False, description="Proceed with upload even if some PDFs are missing on disk"
    )


class AskNotebookRequest(BaseModel):
    query: str = Field(..., description="The synthesis question or research prompt")
    notebook_id: str = Field(..., description="Target Google NotebookLM notebook ID")


# ---------------------------------------------------------------------------
# Authentication & Verification Dependency
# ---------------------------------------------------------------------------


def get_configured_api_key() -> str:
    """Retrieves required Bearer API key from environment."""
    return os.getenv("RESEARCH_TOOLKIT_API_KEY", "").strip() or os.getenv(
        "API_BEARER_TOKEN", ""
    ).strip()


async def verify_auth_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> bool:
    """
    Validates perimeter authentication token.
    Accepts Bearer token in 'Authorization: Bearer <token>' header
    or '?token=<token>' query parameter (useful for browser/SSE connections).
    """
    expected_key = get_configured_api_key()
    if not expected_key:
        return True  # No token configured; open access

    provided_token = None
    if credentials:
        provided_token = credentials.credentials
    if not provided_token:
        provided_token = request.query_params.get("token")

    if not provided_token or provided_token != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


class MCPTokenGate:
    """
    Pure ASGI perimeter guard for MCP transports.
    Accepts 'Authorization: Bearer <token>' or '?token=<token>'. Clients that cannot
    send custom headers (e.g. claude.ai custom connectors) embed the token in the URL.
    Implemented without BaseHTTPMiddleware so streamed MCP responses are never buffered.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        expected_key = get_configured_api_key()
        if scope["type"] == "http" and expected_key:
            request = Request(scope)
            auth_header = request.headers.get("Authorization", "")
            token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
            if not token:
                token = request.query_params.get("token", "")
            if token != expected_key:
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: Invalid or missing token for MCP access."},
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# FastMCP Server Definition
# ---------------------------------------------------------------------------


def create_fastmcp_server() -> FastMCP:
    """Builds and registers FastMCP server instance for MCP Streamable HTTP and SSE transports."""
    sec_settings = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    # Stateless Streamable HTTP: no per-session server state, so clients survive restarts.
    mcp = FastMCP("research-toolkit", transport_security=sec_settings, stateless_http=True)

    @mcp.tool(
        name="search_literature",
        description="Multi-source academic discovery across Semantic Scholar and OpenAlex with ranking.",
    )
    def mcp_search_literature(
        topic: str,
        limit: int = 8,
        collection_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        return search_literature(topic=topic, limit=limit, collection_name=collection_name)

    @mcp.tool(
        name="verify_checkpoint",
        description="Scans Zotero collection for local/cloud full-text PDF attachments.",
    )
    def mcp_verify_checkpoint(collection: str) -> Dict[str, Any]:
        return verify_checkpoint(collection=collection)

    @mcp.tool(
        name="sync_notebook",
        description="Uploads ready PDF attachments from Zotero into Google NotebookLM.",
    )
    def mcp_sync_notebook(collection: str, allow_partial: bool = False) -> Dict[str, Any]:
        return sync_notebook(collection=collection, allow_partial=allow_partial)

    @mcp.tool(
        name="ask_notebook",
        description="Executes source-grounded questions against NotebookLM and returns verbatim evidence.",
    )
    def mcp_ask_notebook(query: str, notebook_id: str) -> Dict[str, Any]:
        return ask_notebook(query=query, notebook_id=notebook_id)

    return mcp


# ---------------------------------------------------------------------------
# FastAPI Application Factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Builds the dual-stack FastAPI application."""
    fastmcp_server = create_fastmcp_server()
    # Initializes fastmcp_server.session_manager for the Streamable HTTP transport.
    fastmcp_server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Mounted sub-app lifespans never run, so the gateway drives the session manager.
        async with fastmcp_server.session_manager.run():
            yield

    app = FastAPI(
        lifespan=lifespan,
        title="Research Toolkit Dual-Stack Gateway",
        description=(
            "Dual-stack MCP and OpenAPI REST gateway for literature discovery, "
            "Zotero library synchronization, and Google NotebookLM synthesis."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 1. Healthcheck & Discovery
    @app.get("/health", tags=["System"])
    async def health_check() -> Dict[str, str]:
        return {
            "status": "ok",
            "service": "research-toolkit-gateway",
            "version": "0.1.0",
        }

    # 2. REST API Endpoints for ChatGPT Actions
    @app.post(
        "/api/v1/search",
        tags=["Academic Discovery"],
        summary="Search & Rank Literature",
        response_model=Dict[str, Any],
        dependencies=[Depends(verify_auth_token)],
    )
    async def api_search_literature(req: SearchLiteratureRequest) -> Dict[str, Any]:
        """Searches Semantic Scholar & OpenAlex, deduplicates, ranks papers, and syncs to Zotero."""
        return search_literature(
            topic=req.topic,
            limit=req.limit,
            collection_name=req.collection_name,
        )

    @app.post(
        "/api/v1/checkpoint",
        tags=["Zotero Library"],
        summary="Verify Full-Text Checkpoint",
        response_model=Dict[str, Any],
        dependencies=[Depends(verify_auth_token)],
    )
    async def api_verify_checkpoint(req: VerifyCheckpointRequest) -> Dict[str, Any]:
        """Scans Zotero collection for local and cloud full-text attachments."""
        return verify_checkpoint(collection=req.collection)

    @app.post(
        "/api/v1/sync-notebook",
        tags=["NotebookLM Synthesis"],
        summary="Sync PDFs to NotebookLM",
        response_model=Dict[str, Any],
        dependencies=[Depends(verify_auth_token)],
    )
    async def api_sync_notebook(req: SyncNotebookRequest) -> Dict[str, Any]:
        """Uploads ready PDF attachments from Zotero collection to Google NotebookLM."""
        return sync_notebook(collection=req.collection, allow_partial=req.allow_partial)

    @app.post(
        "/api/v1/ask",
        tags=["NotebookLM Synthesis"],
        summary="Ask Grounded Synthesis Question",
        response_model=Dict[str, Any],
        dependencies=[Depends(verify_auth_token)],
    )
    async def api_ask_notebook(req: AskNotebookRequest) -> Dict[str, Any]:
        """Queries NotebookLM notebook and extracts verbatim quoted evidence."""
        return ask_notebook(query=req.query, notebook_id=req.notebook_id)

    # 3. MCP Streamable HTTP at an exact path (no Mount, so no trailing-slash redirect).
    #    Registered before the /mcp mount so it is matched first.
    app.router.routes.append(
        Route(
            "/mcp/http",
            endpoint=MCPTokenGate(StreamableHTTPASGIApp(fastmcp_server.session_manager)),
            methods=["GET", "POST", "DELETE"],
        )
    )

    # 4. Legacy MCP SSE transport (/mcp/sse + /mcp/messages/)
    app.mount("/mcp", MCPTokenGate(fastmcp_server.sse_app()))

    return app


# Export application instance for Uvicorn
app = create_app()
