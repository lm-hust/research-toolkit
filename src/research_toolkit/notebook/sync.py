"""
src/research_toolkit/notebook/sync.py
Incremental sync of a Zotero collection into a Gemini Notebook.

Every uploaded Notebook Source is titled `[<Zotero key>] <title>`; a source whose title carries
an item's `[key]` prefix means that item is already synced. There is no local state: a re-run
recomputes everything from Zotero and the notebook, so an interrupted run resumes by re-running.

The server is unreliable about titles (it may reset a title to the uploaded filename, during
processing or a while after) and about uploads (an UNCONFIRMED_WRITE can leave a residue stuck
in PREPARING). Each upload therefore waits for the source to be ready, checks the title and
renames it if needed; all titles are checked once more after the last upload.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from notebooklm import NotebookLMError, Source

from research_toolkit.notebook import client as notebook_client
from research_toolkit.notebook.client import NotebookClient
from research_toolkit.notebook.resolve import NotebookResolutionError, resolve_notebook
from research_toolkit.notebook.titles import source_key, source_title
from research_toolkit.zotero.manager import ZoteroManager
from research_toolkit.zotero.models import ZoteroItem

Progress = Callable[[str], None]

READY_TIMEOUT = 180.0


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
            "renamed": [],
            "failed": [],
        }
        sources = await client.sources.list(notebook.id)
        existing = {source_key(s.title) for s in sources}
        uploader = _Uploader(client, notebook.id, report, progress, {s.id for s in sources})

        for item in items:
            if item.key in existing:
                report["skipped_existing"].append(_entry(item))
            elif not item.pdf_path:
                report["missing_fulltext"].append(_entry(item))
            else:
                await uploader.upload(item, item.pdf_path)
        await uploader.recheck_titles()
        return report


class _Uploader:
    """Uploads papers one at a time into one notebook and keeps their titles right.

    Fills the report's `added`, `renamed` and `failed` lists.
    """

    def __init__(
        self,
        client: NotebookClient,
        notebook_id: str,
        report: dict[str, Any],
        progress: Progress,
        known_ids: set[str],
    ) -> None:
        self.client = client
        self.notebook_id = notebook_id
        self.report = report
        self.progress = progress
        self.known_ids = known_ids  # sources not left behind by the upload in progress
        self.uploaded: dict[str, ZoteroItem] = {}  # source id -> item, added in this run

    async def upload(self, item: ZoteroItem, path: str) -> None:
        """Upload -> wait until ready -> fix the title. Any failure goes to `failed`."""
        self.progress(f"Uploading [{item.key}] {item.title[:60]}")
        wanted = source_title(item.key, item.title)
        try:
            source = await self._add_file(path, wanted)
            self.known_ids.add(source.id)
            ready = await self.client.sources.wait_until_ready(
                self.notebook_id, source.id, timeout=READY_TIMEOUT
            )
            await self._ensure_title(ready, item)
        except Exception as e:  # one paper failing must not stop the run
            self.progress(f"  failed: {e}")
            self.report["failed"].append({**_entry(item), "error": str(e)})
            return
        self.uploaded[source.id] = item
        self.report["added"].append(_entry(item))

    async def recheck_titles(self) -> None:
        """Catches titles the server reset after the per-paper check."""
        if not self.uploaded:
            return
        for source in await self.client.sources.list(self.notebook_id):
            item = self.uploaded.get(source.id)
            if item is not None:
                await self._ensure_title(source, item)

    async def _add_file(self, path: str, wanted: str) -> Source:
        """add_file; after an UNCONFIRMED_WRITE, removes its residue and retries once."""
        for attempt in (1, 2):
            try:
                return await self.client.sources.add_file(self.notebook_id, path, title=wanted)
            except NotebookLMError as e:
                if not e.unconfirmed:
                    raise
                self.progress(f"  unconfirmed upload ({e}); removing its residue")
                landed = await self._clean_residue(Path(path).name, wanted)
                if landed is not None:
                    return landed
                if attempt == 2:
                    raise
        raise AssertionError("unreachable")

    async def _clean_residue(self, filename: str, wanted: str) -> Optional[Source]:
        """Deletes new non-ready sources left by a failed upload; returns one that did land."""
        landed = None
        for source in await self.client.sources.list(self.notebook_id):
            if source.id in self.known_ids or source.title not in (filename, wanted):
                continue
            if source.is_ready and landed is None:
                landed = source
            else:
                await self.client.sources.delete(self.notebook_id, source.id)
        return landed

    async def _ensure_title(self, source: Source, item: ZoteroItem) -> None:
        wanted = source_title(item.key, item.title)
        if source.title == wanted:
            return
        self.progress(f"  title is '{source.title}'; renaming to '{wanted}'")
        await self.client.sources.rename(self.notebook_id, source.id, wanted)
        if item.key not in {e["key"] for e in self.report["renamed"]}:
            self.report["renamed"].append(_entry(item))
