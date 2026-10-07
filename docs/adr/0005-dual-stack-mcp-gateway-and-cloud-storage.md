# 5. Dual-Stack MCP Gateway and Zotero Cloud Storage Resolution

We expose the research toolkit via a unified dual-stack daemon supporting both Model Context Protocol (MCP) Server-Sent Events (SSE) and OpenAPI 3.0 REST endpoints, coupled with automatic Zotero Cloud Storage resolution for headless VPS execution.

## Context
Researchers deploying to remote headless VPS instances (`do-vps`) require their AI agents—both desktop MCP clients (Claude Desktop, Cursor) and cloud-hosted platforms (ChatGPT Custom GPTs / Actions)—to trigger literature discovery, checkpoint scans, and grounded synthesis.
ChatGPT Actions mandates public HTTPS endpoints conforming to OpenAPI 3.0 with standard Bearer authentication, rejecting raw IP addresses and non-standard JSON-RPC transports. Conversely, Claude Desktop relies on native MCP SSE transport.
Furthermore, on a headless VPS without desktop Zotero, relying solely on local disk storage (`~/Zotero/storage`) breaks the synthesis pipeline unless full-text attachments are resolved remotely. Users with Zotero Cloud Storage subscriptions have their PDF attachments synced to the Zotero Cloud.

## Decision
1. **DualStackGateway Architecture**:
   - Implement `research_toolkit.mcp.server` powered by FastAPI and FastMCP.
   - Serve MCP SSE endpoints at `/mcp/sse` and `/mcp/messages/` for Claude Desktop and MCP clients.
   - Serve standard OpenAPI 3.0 REST endpoints at `/api/v1/search`, `/api/v1/checkpoint`, `/api/v1/sync-notebook`, and `/api/v1/ask` alongside `/openapi.json` for ChatGPT Actions.
2. **Perimeter Authentication**:
   - Enforce Bearer Token authorization (`RESEARCH_TOOLKIT_API_KEY`) on all execution endpoints.
   - Expose public discovery docs (`/openapi.json`, `/health`, `/docs`) to permit zero-friction schema ingestion by ChatGPT.
3. **CloudStorageResolver for Zotero**:
   - Enhance `ZoteroClient` and `ZoteroManager` with on-demand attachment downloads via the official Zotero Web API (`GET /users/{user_id}/items/{item_key}/file`).
   - If an attachment PDF is missing locally on disk during `scan_collection_checkpoint` or `sync_notebook`, fetch it directly from Zotero Cloud Storage into the local cache (`/app/data/storage/{key}/`).
4. **Ingress & TLS Packaging**:
   - Deploy a companion Caddy container in `docker-compose.yml` to automatically terminate HTTPS using Let's Encrypt for DuckDNS domains.

## Consequences
- Single container deployment supports both Claude Desktop (MCP SSE) and ChatGPT Actions (OpenAPI).
- Headless VPS functions autonomously without requiring continuous local file syncing.
- Upstream credentials (Google Master Token, Gemini API Key, Zotero API Key) remain strictly isolated on the VPS server.
