"""
src/research_toolkit/notebook/history.py
Keeps a notebook's chat history from being lost when a command needs a fresh conversation.

notebooklm-py has no "new conversation" flag: a fresh conversation means deleting the current
one (what `notebooklm ask --new` does). `clear_conversation` is the only place the toolkit
deletes a conversation, and it first saves any conversation it did not create itself as a
notebook note. If saving fails, it raises and deletes nothing.
"""

from __future__ import annotations

import datetime
from typing import Optional

from notebooklm import Note

from research_toolkit.notebook.client import NotebookClient

HISTORY_LIMIT = 1000


class HistorySaveError(Exception):
    """The current conversation could not be saved, so it must not be deleted."""


def format_history(pairs: list[tuple[str, str]]) -> str:
    """Same layout as `notebooklm history --save`: oldest turn first."""
    return "\n\n---\n\n".join(
        f"### Turn {i}\n\n**Q:** {q}\n\n**A:** {a}" for i, (q, a) in enumerate(pairs, 1)
    )


async def save_conversation_history(
    client: NotebookClient, notebook_id: str, conversation_id: str
) -> Optional[Note]:
    """Saves the conversation as a notebook note; returns None when it has no turns."""
    pairs = await client.chat.get_history(
        notebook_id, limit=HISTORY_LIMIT, conversation_id=conversation_id
    )
    if len(pairs) >= HISTORY_LIMIT:
        raise HistorySaveError(
            f"Conversation {conversation_id} has {HISTORY_LIMIT}+ turns; refusing to save a "
            "possibly truncated history."
        )
    if not pairs:
        return None
    title = f"Chat History (saved {datetime.date.today().isoformat()})"
    note = await client.notes.create(notebook_id, title, format_history(pairs))
    if not note.id:
        raise HistorySaveError(f"Saving conversation {conversation_id} returned no note id.")
    return note


async def clear_conversation(
    client: NotebookClient, notebook_id: str, own_conversations: set[str]
) -> Optional[Note]:
    """
    Deletes the notebook's current conversation so the next ask without a conversation id
    starts fresh. A conversation not in `own_conversations` (ids this run created) is saved
    as a notebook note first; returns that note, or None when nothing needed saving.
    """
    conversation_id = await client.chat.get_conversation_id(notebook_id)
    if conversation_id is None:
        return None
    saved = None
    if conversation_id not in own_conversations:
        saved = await save_conversation_history(client, notebook_id, conversation_id)
    await client.chat.delete_conversation(notebook_id, conversation_id)
    return saved
