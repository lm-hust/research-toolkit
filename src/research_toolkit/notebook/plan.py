"""
src/research_toolkit/notebook/plan.py
The sync plan: what a sync-notebook run would do, computed before any upload.

`plan_sync` is pure: it takes the Zotero items (already resolved to full text) and the
notebook's current sources, and returns a `SyncPlan`. What counts as uploadable full text is
`fulltext.upload_kind`'s call (with `allow_url`, a DOI/URL is enough). The plan also carries the guard verdict
(`aborted_reason`): too many sources for the notebook, or a hand-maintained notebook.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Optional

from notebooklm import Source

from research_toolkit.notebook.fulltext import upload_kind
from research_toolkit.notebook.titles import source_key
from research_toolkit.zotero.models import ZoteroItem

SOURCE_LIMIT = 300
"""Sources per notebook on the Pro tier (#49). The server gives no specific error past it."""


@dataclass(frozen=True)
class PlannedUpload:
    item: ZoteroItem
    kind: str
    """What is uploaded: "pdf" | "epub" | "html" | "url" (see `fulltext.upload_kind`)."""
    replaces: tuple[Source, ...] = ()
    """Sources carrying this item's `[key]` that `--replace` deletes before the upload."""


@dataclass(frozen=True)
class SyncPlan:
    uploads: list[PlannedUpload] = field(default_factory=list)
    existing: list[ZoteroItem] = field(default_factory=list)
    missing_fulltext: list[ZoteroItem] = field(default_factory=list)
    orphaned: list[Source] = field(default_factory=list)
    """Sources not matching any input item. Reported only, never deleted."""
    extra_attachments: list[ZoteroItem] = field(default_factory=list)
    """Items with a full-text file and attachments beyond it (`ZoteroItem.extra_attachments`)."""
    source_count: int = 0
    projected_source_count: int = 0
    aborted_reason: Optional[str] = None


def _unique_by_key(items: Iterable[ZoteroItem]) -> list[ZoteroItem]:
    seen: dict[str, ZoteroItem] = {}
    for item in items:
        seen.setdefault(item.key, item)
    return list(seen.values())


def _manual_notebook(sources: Sequence[Source]) -> bool:
    """Most sources lack a `[key]` title: the notebook is maintained by hand."""
    unkeyed = sum(1 for s in sources if source_key(s.title) is None)
    return unkeyed * 2 > len(sources)


def plan_sync(
    items: Iterable[ZoteroItem],
    sources: Sequence[Source],
    replace_keys: Iterable[str] = (),
    force: bool = False,
    allow_url: bool = False,
    limit: int = SOURCE_LIMIT,
) -> SyncPlan:
    """Plans a sync of `items` (one per key; first occurrence wins) into a notebook."""
    unique = _unique_by_key(items)
    replace = set(replace_keys)
    by_key: dict[str, list[Source]] = {}
    for src in sources:
        key = source_key(src.title)
        if key:
            by_key.setdefault(key, []).append(src)

    uploads: list[PlannedUpload] = []
    existing: list[ZoteroItem] = []
    missing: list[ZoteroItem] = []
    for item in unique:
        synced = by_key.get(item.key, [])
        kind = upload_kind(item, allow_url)
        if synced and item.key not in replace:
            existing.append(item)
        elif kind is None:
            missing.append(item)
        else:
            uploads.append(PlannedUpload(item, kind, tuple(synced)))

    input_keys = {i.key for i in unique}
    deleted = sum(len(u.replaces) for u in uploads)
    projected = len(sources) - deleted + len(uploads)
    reason = None
    if _manual_notebook(sources) and not force:
        reason = (
            f"Most of the notebook's {len(sources)} sources have no [key] title, so it looks "
            "maintained by hand; pass --force to sync into it anyway."
        )
    elif projected > limit:
        reason = (
            f"The notebook would hold {projected} sources ({len(sources)} now, "
            f"{len(uploads)} to upload, {deleted} replaced), over the limit of {limit}. "
            "Nothing was uploaded."
        )
    return SyncPlan(
        uploads=uploads,
        existing=existing,
        missing_fulltext=missing,
        orphaned=[s for s in sources if source_key(s.title) not in input_keys],
        extra_attachments=[i for i in unique if i.fulltext_kind and i.extra_attachments > 0],
        source_count=len(sources),
        projected_source_count=projected,
        aborted_reason=reason,
    )
