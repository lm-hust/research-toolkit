"""
src/research_toolkit/synthesis/gateway.py
Protocol definition for NotebookLMGateway conforming to CONTEXT.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from research_toolkit.synthesis.models import (
    GroundedAnswer,
    NotebookInfo,
    NotebookSource,
)


@runtime_checkable
class NotebookLMGateway(Protocol):
    """Protocol abstraction for NotebookLM and grounded synthesis backends."""

    def check_health(self) -> bool:
        """Verifies session validity and backend responsiveness."""
        ...

    def create_notebook(self, title: str) -> NotebookInfo:
        """Creates a dedicated research notebook."""
        ...

    def upload_source(self, notebook_id: str, file_path: Path) -> NotebookSource:
        """Uploads a local PDF attachment as a grounded source document."""
        ...

    def query_sources(self, notebook_id: str, prompt: str) -> GroundedAnswer:
        """Queries notebook sources and extracts grounded response with verbatim evidence."""
        ...
