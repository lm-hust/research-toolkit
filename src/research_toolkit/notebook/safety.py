"""Durable safety records for unconfirmed uploads, not an incremental-sync database."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

from notebooklm import Source


class UnconfirmedWrites:
    """Keep unknown writes across invocations until cleanup or a ready keyed source confirms them.

    The caller supplies a local cache directory. Missing sources do not clear a record: absence
    in a lagging listing is not proof of absence on the server. No notebook writes are made here.
    """

    def __init__(self, directory: Path, notebook_id: str) -> None:
        digest = hashlib.sha256(notebook_id.encode()).hexdigest()
        self.path = directory / f"{digest}.json"
        self.pending: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or any(
                not isinstance(key, str) or not isinstance(entry, dict)
                or not isinstance(entry.get("title"), str)
                or not isinstance(entry.get("baseline_ids"), list)
                or any(not isinstance(value, str) for value in entry["baseline_ids"])
                for key, entry in data.items()
            ):
                raise ValueError(f"Invalid unconfirmed-write safety record: {self.path}")
            self.pending = data

    def record(self, key: str, title: str, baseline_ids: set[str]) -> None:
        self.pending[key] = {"title": title, "baseline_ids": sorted(baseline_ids)}
        self._save()

    def confirmed(self, key: str) -> None:
        if self.pending.pop(key, None) is not None:
            self._save()

    def unresolved(self, sources: Sequence[Source], *, dry_run: bool) -> list[str]:
        remaining = []
        for key, entry in list(self.pending.items()):
            landed = any(
                source.is_ready and source.title == entry["title"]
                and source.id not in entry["baseline_ids"] for source in sources
            )
            if landed:
                if not dry_run:
                    self.confirmed(key)
            else:
                remaining.append(key)
        return remaining

    def _save(self) -> None:
        if not self.pending:
            self.path.unlink(missing_ok=True)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(self.pending, output)
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
