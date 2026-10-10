"""
src/research_toolkit/notebook/sync.py
Incremental sync of Zotero collections into a Gemini Notebook.

Every uploaded Notebook Source is titled `[<Zotero key>] <title>`; a source whose title carries
an item's `[key]` prefix means that item is already synced. There is no local state: a re-run
recomputes everything from Zotero and the notebook, so an interrupted run resumes by re-running.
The run first computes a `SyncPlan` (notebook/plan.py); a dry run or a guard abort stops there,
before any write (including creating the notebook).

The server is unreliable about titles (it may reset a title to the uploaded filename, during
processing or a while after) and about uploads (an UNCONFIRMED_WRITE can leave a residue stuck
in PREPARING). Each upload therefore waits for the source to be ready, checks the title and
renames it if needed; all titles are checked once more after the last upload.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from notebooklm import Notebook, NotebookLMError, Source

from research_toolkit.notebook import client as notebook_client
from research_toolkit.notebook.client import NotebookClient
from research_toolkit.notebook.fulltext import URL_KIND, upload_target
from research_toolkit.notebook.plan import SyncPlan, plan_sync
from research_toolkit.notebook.resolve import NotebookResolutionError, find_notebook
from research_toolkit.notebook.titles import source_key, source_title
from research_toolkit.zotero.manager import ZoteroManager
from research_toolkit.zotero.models import ZoteroCollection, ZoteroItem

Progress = Callable[[str], None]

READY_TIMEOUT = 180.0


class SyncError(Exception):
    """The sync cannot start (unknown collection, ambiguous notebook, ...)."""


def _entry(item: ZoteroItem) -> dict[str, Any]:
    return {"key": item.key, "title": item.title}


def _source_entry(source: Source) -> dict[str, Any]:
    return {"key": source_key(source.title), "title": source.title, "source_id": source.id}


def _collections(
    manager: ZoteroManager, refs: Sequence[str], recursive: bool
) -> list[ZoteroCollection]:
    """Resolves each name or key; with `recursive`, adds every subcollection below them."""
    found: list[ZoteroCollection] = []
    for ref in refs:
        try:
            collection = manager.client.get_collection(ref)
        except ValueError as e:
            raise SyncError(str(e)) from e
        if collection is None:
            raise SyncError(f"Zotero collection '{ref}' not found.")
        found.append(collection)
    if recursive:
        pending = list(found)
        while pending:
            children = manager.client.get_subcollections(pending.pop().key)
            found.extend(children)
            pending.extend(children)
    unique: dict[str, ZoteroCollection] = {}
    for collection in found:
        unique.setdefault(collection.key, collection)
    return list(unique.values())


def sync_collections(
    manager: ZoteroManager,
    collection_refs: Sequence[str],
    notebook_ref: Optional[str] = None,
    *,
    recursive: bool = False,
    replace: Sequence[str] = (),
    dry_run: bool = False,
    force: bool = False,
    allow_url: bool = False,
    progress: Progress = lambda _msg: None,
) -> dict[str, Any]:
    """
    Syncs Zotero collections (names or keys) into one notebook and returns the JSON-ready
    report. Without `notebook_ref` the notebook is named after the single collection.
    """
    if not collection_refs:
        raise SyncError("Give at least one --collection.")
    if len(collection_refs) > 1 and not notebook_ref:
        raise SyncError("Several collections go into one notebook: pass --notebook.")
    collections = _collections(manager, collection_refs, recursive)

    items: list[ZoteroItem] = []
    for collection in collections:
        progress(f"Resolving full texts in Zotero collection '{collection.name}'...")
        items.extend(manager.list_fulltext_items(collection.key))
    return asyncio.run(
        _sync_items(
            items,
            notebook_ref,
            collections[0].name,
            replace=replace,
            dry_run=dry_run,
            force=force,
            allow_url=allow_url,
            progress=progress,
        )
    )


def _plan_report(
    notebook: Optional[Notebook], title: str, plan: SyncPlan, dry_run: bool
) -> dict[str, Any]:
    return {
        "notebook_id": notebook.id if notebook else None,
        "notebook_title": notebook.title if notebook else title,
        "created": False,
        "dry_run": dry_run,
        "aborted_reason": plan.aborted_reason,
        "added": (
            [{**_entry(u.item), "kind": u.kind} for u in plan.uploads]
            if dry_run and not plan.aborted_reason
            else []
        ),
        "replaced": [],
        "renamed": [],
        "skipped_existing": [_entry(i) for i in plan.existing],
        "missing_fulltext": [_entry(i) for i in plan.missing_fulltext],
        "orphaned": [_source_entry(s) for s in plan.orphaned],
        "failed": [],
        "extra_attachments": [
            {**_entry(i), "count": i.extra_attachments} for i in plan.extra_attachments
        ],
        "source_count": plan.source_count,
        "projected_source_count": plan.projected_source_count,
    }


async def _sync_items(
    items: list[ZoteroItem],
    notebook_ref: Optional[str],
    default_title: str,
    *,
    replace: Sequence[str],
    dry_run: bool,
    force: bool,
    allow_url: bool,
    progress: Progress,
) -> dict[str, Any]:
    async with notebook_client.open_client() as client:
        try:
            notebook = await find_notebook(client, notebook_ref, default_title)
        except NotebookResolutionError as e:
            raise SyncError(str(e)) from e
        if notebook is not None and notebook.title == "Identity":
            raise SyncError("Identity is maintained by hand and must never receive Zotero syncs.")
        sources = await client.sources.list(notebook.id) if notebook else []
        plan = plan_sync(items, sources, replace_keys=replace, force=force, allow_url=allow_url)
        report = _plan_report(notebook, notebook_ref or default_title, plan, dry_run)
        progress(
            f"Plan: {len(plan.uploads)} to upload, {len(plan.existing)} already synced, "
            f"{len(plan.missing_fulltext)} without full text, {len(plan.orphaned)} orphaned"
        )
        if plan.aborted_reason:
            progress(f"Aborted: {plan.aborted_reason}")
            return report
        if dry_run:
            return report

        if notebook is None:
            notebook = await client.notebooks.create(default_title)
            report.update(notebook_id=notebook.id, notebook_title=notebook.title, created=True)
        progress(
            f"{'Created' if report['created'] else 'Using'} notebook "
            f"'{notebook.title}' ({notebook.id})"
        )

        uploader = _Uploader(client, notebook.id, report, progress, {s.id for s in sources})
        existing_by_key = {item.key: item for item in plan.existing}
        for source in sources:
            item = existing_by_key.get(source_key(source.title) or "")
            if item is not None and not source.is_ready:
                await uploader.resume(source, item)
        for planned in plan.uploads:
            try:
                for old in planned.replaces:
                    progress(f"Deleting old source {old.title} ({old.id}) for --replace")
                    await client.sources.delete(notebook.id, old.id)
                    report["replaced"].append(_source_entry(old))
            except Exception as e:
                progress(f"  failed: {e}")
                report["failed"].append({**_entry(planned.item), "error": str(e)})
                continue
            await uploader.upload(planned.item, planned.kind)
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

    async def upload(self, item: ZoteroItem, kind: str) -> None:
        """Upload -> wait until ready -> fix the title. Any failure goes to `failed`."""
        self.progress(f"Uploading [{item.key}] ({kind}) {item.title[:60]}")
        wanted = source_title(item.key, item.title)
        try:
            with upload_target(item, kind) as target:
                source = await self._add(target, wanted, is_url=kind == URL_KIND)
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
        self.report["added"].append({**_entry(item), "kind": kind})

    async def resume(self, source: Source, item: ZoteroItem) -> None:
        """Wait for an earlier interrupted upload; never silently skip an unready source."""
        self.progress(f"Waiting for existing source [{item.key}] to become ready")
        try:
            ready = await self.client.sources.wait_until_ready(
                self.notebook_id, source.id, timeout=READY_TIMEOUT
            )
            await self._ensure_title(ready, item)
        except Exception as e:
            self.progress(f"  failed: {e}")
            self.report["skipped_existing"] = [
                entry for entry in self.report["skipped_existing"] if entry["key"] != item.key
            ]
            self.report["failed"].append({**_entry(item), "error": str(e)})
            return
        self.uploaded[source.id] = item

    async def recheck_titles(self) -> None:
        """Catches titles the server reset after the per-paper check."""
        if not self.uploaded:
            return
        try:
            sources = await self.client.sources.list(self.notebook_id)
        except Exception as e:
            self.progress(f"  final source listing failed: {e}")
            for source_id, uploaded_item in self.uploaded.items():
                self.report["failed"].append(
                    {**_entry(uploaded_item), "source_id": source_id, "error": f"Final title check: {e}"}
                )
            return
        for source in sources:
            item = self.uploaded.get(source.id)
            if item is not None:
                try:
                    await self._ensure_title(source, item)
                except Exception as e:
                    self.progress(f"  final title check failed for [{item.key}]: {e}")
                    self.report["failed"].append(
                        {**_entry(item), "source_id": source.id, "error": f"Final title check: {e}"}
                    )

    async def _add(self, target: str, wanted: str, is_url: bool) -> Source:
        """add_file (or add_url); after an UNCONFIRMED_WRITE, removes its residue, retries once."""
        sources = self.client.sources
        for attempt in (1, 2):
            try:
                if is_url:
                    return await sources.add_url(self.notebook_id, target, title=wanted)
                return await sources.add_file(self.notebook_id, target, title=wanted)
            except NotebookLMError as e:
                if not e.unconfirmed:
                    raise
                self.progress(f"  unconfirmed upload ({e}); removing its residue")
                landed = await self._clean_residue(
                    target if is_url else Path(target).name, wanted
                )
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
