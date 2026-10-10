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
- `answers`: {source id: (answer text, [ChatReference])} returned by chat.ask when the ask is
  restricted to that one source; anything else gets a generic answer with no references.
- `ask_errors`: {source id: exception to raise from chat.ask restricted to that source}.
- `note_errors`: exception raised by notes.create (nothing is created), or None.

Chat mirrors the server: each notebook has one current conversation; ask() without a
conversation id extends it (or starts one when there is none); delete_conversation drops it and
its history. Arrange one with `start_conversation(nb_id, [(q, a), ...])`; read
`conversation_id(nb_id)`, `history(nb_id)`, `note_titles(nb_id)`, `notes[nb_id]`.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from notebooklm import AskResult, ChatReference, Note, Notebook, Source, SourceStatus

from research_toolkit.notebook.client import NotebookClient

OPEN_CLIENT = "research_toolkit.notebook.client.open_client"


@dataclass
class FakeNotebookState:
    id: str
    title: str
    sources: list[Source] = field(default_factory=list)
    conversation_id: str | None = None
    history: list[tuple[str, str]] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)


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
        src = self._fake.new_source(notebook_id, title or path.name)
        self._fake.uploaded_paths.append(path)
        return src


class FakeChatAPI:
    def __init__(self, fake: FakeNotebookClient) -> None:
        self._fake = fake

    async def ask(
        self,
        notebook_id: str,
        question: str,
        source_ids: list[str] | None = None,
        conversation_id: str | None = None,
    ) -> AskResult:
        nb = self._fake.state[notebook_id]
        self._fake.writes.append(("ask", notebook_id, tuple(source_ids or ()), conversation_id))
        only = source_ids[0] if source_ids and len(source_ids) == 1 else None
        if only in self._fake.ask_errors:
            raise self._fake.ask_errors[only]
        answer, refs = self._fake.answers.get(only or "", (f"Answer to: {question[:40]}", []))
        follow_up = nb.conversation_id is not None
        if nb.conversation_id is None:
            nb.conversation_id = self._fake.next_id("conv")
        nb.history.append((question, answer))
        return AskResult(
            answer=answer,
            conversation_id=nb.conversation_id,
            turn_number=len(nb.history),
            is_follow_up=follow_up,
            references=list(refs),
        )

    async def get_conversation_id(self, notebook_id: str) -> str | None:
        return self._fake.state[notebook_id].conversation_id

    async def get_history(
        self, notebook_id: str, limit: int = 100, conversation_id: str | None = None
    ) -> list[tuple[str, str]]:
        nb = self._fake.state[notebook_id]
        if conversation_id not in (None, nb.conversation_id):
            return []
        return list(nb.history[:limit])

    async def delete_conversation(self, notebook_id: str, conversation_id: str) -> None:
        nb = self._fake.state[notebook_id]
        self._fake.writes.append(("delete_conversation", notebook_id, conversation_id))
        if nb.conversation_id == conversation_id:
            nb.conversation_id = None
            nb.history = []


class FakeNotesAPI:
    def __init__(self, fake: FakeNotebookClient) -> None:
        self._fake = fake

    async def create(self, notebook_id: str, title: str = "New Note", content: str = "") -> Note:
        self._fake.writes.append(("create_note", notebook_id, title))
        if self._fake.note_errors is not None:
            raise self._fake.note_errors
        note = Note(id=self._fake.next_id("note"), notebook_id=notebook_id, title=title, content=content)
        self._fake.state[notebook_id].notes.append(note)
        return note


class FakeNotebookClient:
    def __init__(self) -> None:
        self.state: dict[str, FakeNotebookState] = {}
        self.writes: list[tuple[Any, ...]] = []
        self.uploaded_paths: list[Path] = []
        self.upload_errors: dict[str, Exception] = {}
        self.answers: dict[str, tuple[str, list[ChatReference]]] = {}
        self.ask_errors: dict[str, Exception] = {}
        self.note_errors: Exception | None = None
        self._ids = itertools.count(1)
        self.notebooks = FakeNotebooksAPI(self)
        self.sources = FakeSourcesAPI(self)
        self.chat = FakeChatAPI(self)
        self.notes = FakeNotesAPI(self)

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

    def next_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._ids)}"

    def start_conversation(self, notebook_id: str, turns: list[tuple[str, str]]) -> str:
        nb = self.state[notebook_id]
        nb.conversation_id = self.next_id("conv")
        nb.history = list(turns)
        return nb.conversation_id

    # --- assert helpers --------------------------------------------------
    def source_titles(self, notebook_id: str) -> list[str | None]:
        return [s.title for s in self.state[notebook_id].sources]

    def conversation_id(self, notebook_id: str) -> str | None:
        return self.state[notebook_id].conversation_id

    def history(self, notebook_id: str) -> list[tuple[str, str]]:
        return list(self.state[notebook_id].history)

    def note_titles(self, notebook_id: str) -> list[str]:
        return [n.title for n in self.state[notebook_id].notes]

    def notebook_ids(self, title: str) -> list[str]:
        return [s.id for s in self.state.values() if s.title == title]

    # --- factory (patch OPEN_CLIENT with this) ---------------------------
    @asynccontextmanager
    async def open(self) -> AsyncIterator[FakeNotebookClient]:
        yield self


def _conforms(fake: FakeNotebookClient) -> NotebookClient:
    """mypy check: the fake satisfies the Protocol production code is typed against."""
    return fake
