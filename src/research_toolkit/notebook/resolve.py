"""
src/research_toolkit/notebook/resolve.py
Resolves the target Gemini Notebook from a full UUID or an exact title.
"""

from __future__ import annotations

from typing import Optional

from notebooklm import Notebook

from research_toolkit.notebook.client import NotebookClient


class NotebookResolutionError(Exception):
    """The notebook reference is ambiguous or names nothing."""


async def resolve_notebook(
    client: NotebookClient, ref: Optional[str], default_title: str
) -> tuple[Notebook, bool]:
    """
    Returns (notebook, created). `ref` matches a full notebook id or an exact title.
    With no `ref`, `default_title` is used and created when absent. Several notebooks with
    the same title is an error: the caller must pass the UUID.
    """
    notebooks = await client.notebooks.list()
    if ref:
        by_id = [nb for nb in notebooks if nb.id == ref]
        if by_id:
            return by_id[0], False
    wanted = ref or default_title
    matches = [nb for nb in notebooks if nb.title == wanted]
    if len(matches) > 1:
        ids = ", ".join(nb.id for nb in matches)
        raise NotebookResolutionError(
            f"{len(matches)} notebooks are titled '{wanted}'; pass --notebook <UUID>: {ids}"
        )
    if matches:
        return matches[0], False
    if ref:
        raise NotebookResolutionError(f"No notebook with id or title '{ref}'.")
    return await client.notebooks.create(wanted), True
