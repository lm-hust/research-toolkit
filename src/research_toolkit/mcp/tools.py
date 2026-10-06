"""
src/research_toolkit/mcp/tools.py
Standardized Model Context Protocol (MCP) tool wrappers for literature discovery,
checkpoint verification, and NotebookLM grounded synthesis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from research_toolkit.discovery.query import QueryTranslator
from research_toolkit.discovery.service import DiscoveryService
from research_toolkit.synthesis.adapters import get_default_gateway
from research_toolkit.zotero.manager import ZoteroManager


def search_literature(
    topic: str,
    limit: int = 8,
    collection_name: Optional[str] = None,
) -> Dict[str, Any]:
    """MCP Tool: Search Semantic Scholar and OpenAlex, deduplicate, rank papers, and sync to Zotero."""
    service = DiscoveryService()
    candidates = service.search_and_rank(topic, top_k=limit)

    if collection_name:
        clean_topic = collection_name.strip().lower().replace(" ", "-")
    else:
        clean_topic = QueryTranslator.to_topic_slug(topic)

    col_name = clean_topic if clean_topic.startswith("research/") else f"research/{clean_topic}"

    zotero_mgr = ZoteroManager()
    col_id = ""
    col_url = ""
    try:
        collection, created = zotero_mgr.sync_to_collection(col_name, candidates)
        col_id = collection.key
        col_url = collection.web_url
    except Exception:
        pass

    return {
        "status": "success",
        "topic": topic,
        "collection_name": col_name,
        "collection_id": col_id,
        "collection_url": col_url,
        "count": len(candidates),
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


def sync_notebook(collection: str, allow_partial: bool = False) -> Dict[str, Any]:
    """MCP Tool: Synchronize ready PDFs from Zotero collection to NotebookLM."""
    manager = ZoteroManager()
    report = manager.scan_collection_checkpoint(collection)

    if report.missing_items and not allow_partial:
        return {
            "status": "error",
            "message": f"FulltextCheckpoint blocked: {len(report.missing_items)} papers lack PDFs. Use allow_partial=True or resolve PDFs.",
            "missing_count": len(report.missing_items),
        }

    if not report.ready_items:
        return {
            "status": "error",
            "message": "No ready PDF files found in collection on disk.",
        }

    gw = get_default_gateway()
    notebook = gw.create_notebook(report.collection_name)
    uploaded = []
    for it in report.ready_items:
        if it.pdf_path:
            src = gw.upload_source(notebook.id, Path(it.pdf_path))
            uploaded.append({"id": src.id, "title": src.title})

    return {
        "status": "success",
        "notebook_id": notebook.id,
        "notebook_title": notebook.title,
        "uploaded_count": len(uploaded),
        "sources": uploaded,
    }


def ask_notebook(query: str, notebook_id: Optional[str] = None) -> Dict[str, Any]:
    """MCP Tool: Query grounded sources in NotebookLM and extract verbatim evidence."""
    if not notebook_id:
        return {"status": "error", "message": "notebook_id is required"}

    gw = get_default_gateway()
    ans = gw.query_sources(notebook_id, query)
    return {
        "status": "success",
        "notebook_id": notebook_id,
        "answer": ans.answer,
        "citations": [
            {
                "quote": c.quote,
                "source_id": c.source_id,
                "source_title": c.source_title,
                "start_offset": c.start_offset,
                "end_offset": c.end_offset,
            }
            for c in ans.citations
        ],
    }


def get_tools_manifest() -> List[Dict[str, Any]]:
    """Returns standardized JSON schema descriptions for Model Context Protocol registration."""
    return [
        {
            "name": "search_literature",
            "description": "Multi-source academic discovery across Semantic Scholar and OpenAlex with composite ranking and review quota.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Research subject or query string"},
                    "limit": {"type": "integer", "description": "Number of top papers to select", "default": 8},
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
        {
            "name": "sync_notebook",
            "description": "Uploads verified local PDF attachments from Zotero into a Google NotebookLM research notebook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string", "description": "Zotero collection name or key"},
                    "allow_partial": {"type": "boolean", "description": "Whether to allow proceeding if some PDFs are missing", "default": False},
                },
                "required": ["collection"],
            },
        },
        {
            "name": "ask_notebook",
            "description": "Executes source-grounded questions against NotebookLM and returns verbatim quoted evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The research synthesis query"},
                    "notebook_id": {"type": "string", "description": "Google NotebookLM notebook ID"},
                },
                "required": ["query", "notebook_id"],
            },
        },
    ]
