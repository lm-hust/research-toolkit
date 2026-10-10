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


async def find_notebook(
    client: NotebookClient, ref: Optional[str], default_title: str
) -> Optional[Notebook]:
    """
    Returns the notebook `ref` names (a full notebook id or an exact title), or, with no `ref`,
    the one titled `default_title`; None when that default is absent. Never creates anything.
    Several notebooks with the same title is an error: the caller must pass the UUID.
    """
    notebooks = await client.notebooks.list()
    if ref:
        by_id = [nb for nb in notebooks if nb.id == ref]
        if by_id:
            return by_id[0]
    wanted = ref or default_title
    matches = [nb for nb in notebooks if nb.title == wanted]
    if len(matches) > 1:
        ids = ", ".join(nb.id for nb in matches)
        raise NotebookResolutionError(
            f"{len(matches)} notebooks are titled '{wanted}'; pass --notebook <UUID>: {ids}"
        )
    if matches:
        return matches[0]
    if ref:
        raise NotebookResolutionError(f"No notebook with id or title '{ref}'.")
    return None


async def resolve_notebook(
    client: NotebookClient, ref: Optional[str], default_title: str
) -> tuple[Notebook, bool]:
    """Like `find_notebook`, but creates the default notebook when absent: (notebook, created)."""
    notebook = await find_notebook(client, ref, default_title)
    if notebook:
        return notebook, False
    return await client.notebooks.create(ref or default_title), True
