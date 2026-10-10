"""
tests/notebook_fakes.py
In-memory stand-in for the notebooklm-py client, injected through the client factory.

Usage:
    fake = FakeNotebookClient()
    nb_id = fake.add_notebook("intelligence-per-kwh", ["[K1] Paper one"])
    with patch(OPEN_CLIENT, fake.open):
        ...run the command...
    fake.source_titles(nb_id); fake.writes

The fake returns the real `notebooklm.Notebook` / `notebooklm.Source` dataclasses so code
under test sees the same attribute shapes as in production.

Extending it for a new server behaviour: add a knob (a public attribute, set by the test
before running) and consult it inside the API method the behaviour belongs to. Existing knobs:
- `upload_errors`: {substring of the requested title: exception to raise from add_file}.
  The upload does not land (no residue).
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from notebooklm import Notebook, Source, SourceStatus, ValidationError

from research_toolkit.notebook.client import NotebookClient

OPEN_CLIENT = "research_toolkit.notebook.client.open_client"
HTML_SUFFIXES = (".html", ".htm", ".xhtml", ".xht")


@dataclass
class FakeNotebookState:
    id: str
    title: str
    sources: list[Source] = field(default_factory=list)


class FakeNotebooksAPI:
    def __init__(self, fake: FakeNotebookClient) -> None:
        self._fake = fake

    async def list(self) -> list[Notebook]:
        return [Notebook(id=s.id, title=s.title, sources_count=len(s.sources)) for s in self._fake.state.values()]

    async def create(self, title: str) -> Notebook:
        self._fake.writes.append(("create_notebook", title))
        nb_id = self._fake.add_notebook(title)
        return Notebook(id=nb_id, title=title)


class FakeSourcesAPI:
    def __init__(self, fake: FakeNotebookClient) -> None:
        self._fake = fake

    async def list(self, notebook_id: str) -> list[Source]:
        return list(self._fake.state[notebook_id].sources)

    async def add_file(
        self,
        notebook_id: str,
        file_path: str | Path,
        mime_type: str | None = None,
        *,
        wait: bool = False,
        wait_timeout: float = 120.0,
        title: str | None = None,
    ) -> Source:
        path = Path(file_path)
        self._fake.writes.append(("add_file", notebook_id, title, path.name))
        for needle, error in self._fake.upload_errors.items():
            if needle in (title or path.name):
                raise error
        if path.suffix.lower() in HTML_SUFFIXES:  # real client: notebooklm.ValidationError
            raise ValidationError("HTML file uploads are not supported")
        src = self._fake.new_source(notebook_id, title or path.name)
        self._fake.uploaded_paths.append(path)
        self._fake.uploaded_contents.append(path.read_bytes())
        return src

    async def add_url(
        self,
        notebook_id: str,
        url: str,
        *,
        wait: bool = False,
        wait_timeout: float = 120.0,
        title: str | None = None,
    ) -> Source:
        self._fake.writes.append(("add_url", notebook_id, title, url))
        for needle, error in self._fake.upload_errors.items():
            if needle in (title or url):
                raise error
        return self._fake.new_source(notebook_id, title or url)


class FakeNotebookClient:
    def __init__(self) -> None:
        self.state: dict[str, FakeNotebookState] = {}
        self.writes: list[tuple[Any, ...]] = []
        self.uploaded_paths: list[Path] = []
        self.uploaded_contents: list[bytes] = []  # file bytes at upload time
        self.upload_errors: dict[str, Exception] = {}
        self._ids = itertools.count(1)
        self.notebooks = FakeNotebooksAPI(self)
        self.sources = FakeSourcesAPI(self)

    # --- arrange helpers -------------------------------------------------
    def add_notebook(self, title: str, source_titles: list[str] | tuple[str, ...] = ()) -> str:
        nb_id = str(uuid.uuid4())
        self.state[nb_id] = FakeNotebookState(id=nb_id, title=title)
        for t in source_titles:
            self.new_source(nb_id, t)
        return nb_id

    def new_source(
        self, notebook_id: str, title: str | None, status: SourceStatus = SourceStatus.READY
    ) -> Source:
        src = Source(id=f"src-{next(self._ids)}", title=title, status=status)
        self.state[notebook_id].sources.append(src)
        return src

    # --- assert helpers --------------------------------------------------
    def source_titles(self, notebook_id: str) -> list[str | None]:
        return [s.title for s in self.state[notebook_id].sources]

    def notebook_ids(self, title: str) -> list[str]:
        return [s.id for s in self.state.values() if s.title == title]

    # --- factory (patch OPEN_CLIENT with this) ---------------------------
    @asynccontextmanager
    async def open(self) -> AsyncIterator[FakeNotebookClient]:
        yield self


def _conforms(fake: FakeNotebookClient) -> NotebookClient:
    """mypy check: the fake satisfies the Protocol production code is typed against."""
    return fake
