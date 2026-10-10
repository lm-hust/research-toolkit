"""
src/research_toolkit/notebook/client.py
Client factory for notebooklm-py, and the Protocol of the API slice the toolkit uses.

Commands open the client with `async with client.open_client() as nb:` and look the factory up
through this module at call time, so tests replace it by patching
`research_toolkit.notebook.client.open_client`. Extend the Protocols below when new code calls
more of the notebooklm-py API; mypy then checks the real client still satisfies them.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Protocol

from notebooklm import AskResult, Note, Notebook, NotebookLMClient, Source, UsageSummary
from notebooklm.options import AndroidBackendConfig, ClientConfig


class NotebooksApi(Protocol):
    async def list(self) -> list[Notebook]: ...

    async def create(self, title: str) -> Notebook: ...


class SourcesApi(Protocol):
    async def list(self, notebook_id: str) -> list[Source]: ...

    async def add_file(
        self,
        notebook_id: str,
        file_path: str | Path,
        mime_type: str | None = None,
        *,
        wait: bool = False,
        wait_timeout: float = 120.0,
        title: str | None = None,
    ) -> Source: ...

    async def add_url(
        self,
        notebook_id: str,
        url: str,
        *,
        wait: bool = False,
        wait_timeout: float = 120.0,
        title: str | None = None,
    ) -> Source: ...

    async def wait_until_ready(
        self, notebook_id: str, source_id: str, timeout: float = 120.0
    ) -> Source: ...

    async def rename(
        self, notebook_id: str, source_id: str, new_title: str, *, return_object: bool = True
    ) -> Source | None: ...

    async def delete(self, notebook_id: str, source_id: str) -> None: ...

class ChatApi(Protocol):
    async def ask(
        self,
        notebook_id: str,
        question: str,
        source_ids: list[str] | None = None,
        conversation_id: str | None = None,
    ) -> AskResult: ...

    async def get_conversation_id(self, notebook_id: str) -> str | None: ...

    async def get_history(
        self, notebook_id: str, limit: int = 100, conversation_id: str | None = None
    ) -> list[tuple[str, str]]: ...

    async def delete_conversation(self, notebook_id: str, conversation_id: str) -> None: ...


class NotesApi(Protocol):
    async def create(self, notebook_id: str, title: str = "New Note", content: str = "") -> Note: ...


class SettingsApi(Protocol):
    async def get_usage(self) -> UsageSummary: ...


class NotebookClient(Protocol):
    @property
    def notebooks(self) -> NotebooksApi: ...

    @property
    def sources(self) -> SourcesApi: ...

    @property
    def chat(self) -> ChatApi: ...

    @property
    def notes(self) -> NotesApi: ...

    @property
    def settings(self) -> SettingsApi: ...


def open_client() -> AbstractAsyncContextManager[NotebookClient]:
    """Opens notebooklm-py with the profile's master token on the android backend."""
    ctx: AbstractAsyncContextManager[NotebookLMClient] = NotebookLMClient.from_storage(
        config=ClientConfig(backend=AndroidBackendConfig())
    )
    return ctx
