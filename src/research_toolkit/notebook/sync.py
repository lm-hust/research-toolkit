"""
src/research_toolkit/notebook/sync.py
Incremental sync of a Zotero collection into a Gemini Notebook.

Every uploaded Notebook Source is titled `[<Zotero key>] <title>`; a source whose title carries
an item's `[key]` prefix means that item is already synced. There is no local state: a re-run
recomputes everything from Zotero and the notebook, so an interrupted run resumes by re-running.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from research_toolkit.notebook import client as notebook_client
from research_toolkit.notebook.client import NotebookClient
from research_toolkit.notebook.resolve import NotebookResolutionError, resolve_notebook
from research_toolkit.notebook.titles import source_key, source_title
from research_toolkit.zotero.manager import ZoteroManager
from research_toolkit.zotero.models import ZoteroItem

Progress = Callable[[str], None]


class SyncError(Exception):
    """The sync cannot start (unknown collection, ambiguous notebook, ...)."""


def _entry(item: ZoteroItem) -> dict[str, Any]:
    return {"key": item.key, "title": item.title}


def sync_collection(
    manager: ZoteroManager,
    collection_ref: str,
    notebook_ref: Optional[str] = None,
    progress: Progress = lambda _msg: None,
) -> dict[str, Any]:
    """Syncs one Zotero collection (name or key) and returns the JSON-ready report."""
    try:
        collection = manager.client.get_collection(collection_ref)
    except ValueError as e:
        raise SyncError(str(e)) from e
    if collection is None:
        raise SyncError(f"Zotero collection '{collection_ref}' not found.")

    progress(f"Resolving full texts in Zotero collection '{collection.name}'...")
    items = manager.list_fulltext_items(collection.key)
    return asyncio.run(_sync_items(items, notebook_ref, collection.name, progress))


async def _sync_items(
    items: list[ZoteroItem],
    notebook_ref: Optional[str],
    default_title: str,
    progress: Progress,
) -> dict[str, Any]:
    async with notebook_client.open_client() as client:
        try:
            notebook, created = await resolve_notebook(client, notebook_ref, default_title)
        except NotebookResolutionError as e:
            raise SyncError(str(e)) from e
        progress(f"{'Created' if created else 'Using'} notebook '{notebook.title}' ({notebook.id})")

        report: dict[str, Any] = {
            "notebook_id": notebook.id,
            "notebook_title": notebook.title,
            "created": created,
            "added": [],
            "skipped_existing": [],
            "missing_fulltext": [],
            "failed": [],
        }
        existing = {source_key(s.title) for s in await client.sources.list(notebook.id)}

        for item in items:
            if item.key in existing:
                report["skipped_existing"].append(_entry(item))
            elif not item.pdf_path:
                report["missing_fulltext"].append(_entry(item))
            else:
                await _upload(client, notebook.id, item, report, progress)
        return report


async def _upload(
    client: NotebookClient,
    notebook_id: str,
    item: ZoteroItem,
    report: dict[str, Any],
    progress: Progress,
) -> None:
    assert item.pdf_path
    progress(f"Uploading [{item.key}] {item.title[:60]}")
    try:
        await client.sources.add_file(
            notebook_id, item.pdf_path, title=source_title(item.key, item.title)
        )
    except Exception as e:  # one paper failing must not stop the run
        progress(f"  failed: {e}")
        report["failed"].append({**_entry(item), "error": str(e)})
        return
    report["added"].append(_entry(item))
