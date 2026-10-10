"""
src/research_toolkit/mcp/tools.py
Standardized Model Context Protocol (MCP) tool wrappers for literature discovery,
and checkpoint verification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from research_toolkit.discovery.query import QueryTranslator
from research_toolkit.discovery.service import DiscoveryService
from research_toolkit.zotero.manager import ZoteroManager


def search_literature(
    topic: str,
    limit: int = 8,
    collection_name: Optional[str] = None,
) -> Dict[str, Any]:
    """MCP Tool: Search Semantic Scholar and OpenAlex, deduplicate, rank papers, and sync to Zotero."""
    service = DiscoveryService()
    candidates = service.search_and_rank(topic, top_k=limit)

    col_name = QueryTranslator.to_collection_name(topic, collection_name)

    zotero_mgr = ZoteroManager()
    col_id = ""
    col_url = ""
    sync_error = None
    try:
        collection, created = zotero_mgr.sync_to_collection(col_name, candidates)
        col_id = collection.key
        col_url = collection.web_url
    except Exception as e:
        sync_error = str(e)

    res: Dict[str, Any] = {
        "status": "success",
        "topic": topic,
        "collection_name": col_name,
        "collection_id": col_id,
        "collection_url": col_url,
        "count": len(candidates),
        "created_count": getattr(created, "created_count", len(candidates)) if "created" in locals() else 0,
        "reused_count": getattr(created, "reused_count", 0) if "created" in locals() else 0,
        "candidates": [
            {
                "paper_id": c.paper_id,
                "title": c.title,
                "year": c.year,
                "authors": c.authors,
                "citation_count": c.citation_count,
                "venue": c.venue,
                "doi": c.doi,
                "is_review": c.is_review,
                "composite_score": c.composite_score,
                "abstract": c.abstract,
            }
            for c in candidates
        ],
    }
    if sync_error:
        res["sync_error"] = sync_error
    return res


def verify_checkpoint(collection: str) -> Dict[str, Any]:
    """MCP Tool: Check collection for missing PDF files and return DOI resolution links."""
    manager = ZoteroManager()
    report = manager.scan_collection_checkpoint(collection)
    return {
        "status": "success",
        "collection": report.collection_name,
        "total": report.total_items,
        "ready_count": len(report.ready_items),
        "missing_count": len(report.missing_items),
        "reconciled_duplicates": report.reconciled_duplicates,
        "ready_items": [
            {"key": it.key, "title": it.title, "pdf_path": it.pdf_path}
            for it in report.ready_items
        ],
        "missing_items": [
            {"key": it.key, "title": it.title, "doi": it.doi, "url": it.doi_url}
            for it in report.missing_items
        ],
    }


def get_tools_manifest() -> List[Dict[str, Any]]:
    """Returns standardized JSON schema descriptions for Model Context Protocol registration."""
    return [
        {
            "name": "search_literature",
            "description": "Multi-source academic discovery across Semantic Scholar and OpenAlex with composite ranking and automatic Zotero collection insertion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Research subject or query string"},
                    "limit": {"type": "integer", "description": "Number of top papers to select", "default": 8},
                    "collection_name": {"type": "string", "description": "Optional custom Zotero collection name"},
                },
                "required": ["topic"],
            },
        },
        {
            "name": "verify_checkpoint",
            "description": "Scans personal Zotero collection to verify presence of local full-text PDFs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Zotero collection name or key"},
                },
                "required": ["collection"],
            },
        },
    ]
