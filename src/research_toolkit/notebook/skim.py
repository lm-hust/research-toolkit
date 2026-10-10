"""
src/research_toolkit/notebook/skim.py
Skim papers in a Gemini Notebook: one structured question per `[key]` source, asked in a fresh
conversation restricted to that source, written back as a child note on the Zotero item.

Prompt and note are separate steps: `build_prompt()` lists `SECTIONS` as `## <heading>` blocks,
`render_note()` turns Gemini's markdown answer plus its `cited_text` references into the Zotero
note HTML. Gemini's page numbers are unreliable, so provenance is `cited_text` only.
"""

from __future__ import annotations

import asyncio
import datetime
import html
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

import notebooklm
from notebooklm import AskResult, ChatReference

from research_toolkit.notebook import client as notebook_client
from research_toolkit.notebook.client import NotebookClient
from research_toolkit.notebook.history import clear_conversation
from research_toolkit.notebook.resolve import NotebookResolutionError, resolve_notebook
from research_toolkit.notebook.titles import source_key, source_paper_title
from research_toolkit.zotero.client import ZoteroClient

Progress = Callable[[str], None]

SKIM_NOTE_TAG = "gemini-skim/ai-note"
NOTE_TITLE_PREFIX = "Gemini 初读："
SNIPPET_CHARS = 300

# (heading Gemini must use, what goes under it)
SECTIONS: tuple[tuple[str, str], ...] = (
    ("研究问题与动机", "论文要解决什么问题，为什么重要。"),
    ("方法与数据", "采用的方法、模型、实验设置与数据来源。"),
    ("主要结论", "主要发现，列出关键数值（含单位与比较对象）。"),
    ("局限", "作者承认的局限，以及你看到的明显不足。"),
    ("复现或深读价值", "是否值得复现或精读，理由是什么。"),
)


class SkimError(Exception):
    """The skim cannot start or must stop (unknown notebook, unsaved conversation, ...)."""


@dataclass(frozen=True)
class SkimTarget:
    key: str
    title: str
    source_id: str


def build_prompt() -> str:
    blocks = "\n".join(f"## {heading}\n{guide}" for heading, guide in SECTIONS)
    return (
        "请只根据这篇来源，用中文对论文做结构化初读。严格按下面的小节输出，"
        "每个小节以给定的二级标题（## 标题）开头，不要增加其他小节，不要写页码。\n\n"
        f"{blocks}"
    )


def _inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _list_html(items: list[tuple[int, str]]) -> str:
    """Nests (indent, item html) pairs into <ul>s by indentation."""
    out: list[str] = []
    open_indents: list[int] = []
    for indent, text in items:
        if not open_indents or indent > open_indents[-1]:
            out.append("<ul>")
            open_indents.append(indent)
        else:
            while len(open_indents) > 1 and indent < open_indents[-1]:
                out.append("</li></ul>")
                open_indents.pop()
            out.append("</li>")
        out.append(f"<li>{text}")
    out.append("</li></ul>" * len(open_indents))
    return "".join(out)


def markdown_to_html(markdown: str) -> str:
    """Minimal markdown -> Zotero note HTML: headings, nested lists, paragraphs, bold, code."""
    out: list[str] = []
    para: list[str] = []
    items: list[tuple[int, str]] = []

    def flush() -> None:
        if para:
            out.append(f"<p>{'<br/>'.join(para)}</p>")
            para.clear()
        if items:
            out.append(_list_html(items))
            items.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        bullet = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*)$", line)
        if not line:
            flush()
        elif heading:
            flush()
            level = 3 if len(heading.group(1)) >= 3 else 2
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif bullet:
            if para:
                flush()
            indent = len(raw.expandtabs(4)) - len(raw.expandtabs(4).lstrip())
            items.append((indent, _inline(bullet.group(1))))
        else:
            if items:
                flush()
            para.append(_inline(line))
    flush()
    return "\n".join(out)


def _provenance(references: list[ChatReference]) -> list[str]:
    seen: set[tuple[Optional[int], str]] = set()
    lines: list[str] = []
    ordered = sorted(references, key=lambda r: r.citation_number or 0)
    for ref in ordered:
        text = " ".join((ref.cited_text or "").split())
        if not text or (ref.citation_number, text) in seen:
            continue
        seen.add((ref.citation_number, text))
        if len(text) > SNIPPET_CHARS:
            text = text[:SNIPPET_CHARS].rstrip() + "…"
        label = f"[{ref.citation_number}] " if ref.citation_number is not None else ""
        lines.append(f"<li>{html.escape(label + text, quote=False)}</li>")
    return lines


def render_note(
    target: SkimTarget, notebook_id: str, result: AskResult, today: datetime.date
) -> str:
    """Zotero note HTML. Zotero shows a note's first line as its title."""
    header = "<br/>".join(
        [
            f"笔记本 UUID：{html.escape(notebook_id)}",
            f"来源 ID：{html.escape(target.source_id)}",
            f"日期：{today.isoformat()}",
            f"生成工具：notebooklm-py {notebooklm.__version__}",
            f"标签：{SKIM_NOTE_TAG}",
        ]
    )
    parts = [
        f"<h1>{html.escape(NOTE_TITLE_PREFIX + target.title, quote=False)}</h1>",
        f"<p>{header}</p>",
        markdown_to_html(result.answer),
    ]
    provenance = _provenance(result.references)
    if provenance:
        parts.append("<h2>出处（cited_text 片段）</h2>")
        parts.append(f"<ul>{''.join(provenance)}</ul>")
    return "\n".join(parts)


def skim_notebook(
    zotero: ZoteroClient,
    notebook_ref: str,
    keys: list[str],
    progress: Progress = lambda _msg: None,
) -> dict[str, Any]:
    """Skims the `[key]` sources named by `keys` and returns the JSON-ready report."""
    return asyncio.run(_skim(zotero, notebook_ref, keys, progress))


async def _skim(
    zotero: ZoteroClient, notebook_ref: str, keys: list[str], progress: Progress
) -> dict[str, Any]:
    async with notebook_client.open_client() as client:
        try:
            notebook, _ = await resolve_notebook(client, notebook_ref, notebook_ref)
        except NotebookResolutionError as e:
            raise SkimError(str(e)) from e
        progress(f"Using notebook '{notebook.title}' ({notebook.id})")

        report: dict[str, Any] = {
            "notebook_id": notebook.id,
            "notebook_title": notebook.title,
            "saved_history_note": False,
            "written": [],
            "failed": [],
        }
        by_key: dict[str, SkimTarget] = {}
        for src in await client.sources.list(notebook.id):
            key = source_key(src.title)
            if key and key not in by_key:
                by_key[key] = SkimTarget(key, source_paper_title(src.title), src.id)

        own_conversations: set[str] = set()
        for key in keys:
            target = by_key.get(key)
            if target is None:
                report["failed"].append(
                    {"key": key, "title": "", "error": f"No source titled '[{key}] ...' in the notebook."}
                )
                continue
            try:
                saved = await clear_conversation(client, notebook.id, own_conversations)
            except Exception as e:
                raise SkimError(
                    f"Could not save the notebook's current conversation; nothing was deleted: {e}"
                ) from e
            if saved is not None:
                report["saved_history_note"] = True
                progress(f"Saved the existing conversation as notebook note '{saved.title}'")
            await _skim_one(client, zotero, notebook.id, target, own_conversations, report, progress)
        return report


async def _skim_one(
    client: NotebookClient,
    zotero: ZoteroClient,
    notebook_id: str,
    target: SkimTarget,
    own_conversations: set[str],
    report: dict[str, Any],
    progress: Progress,
) -> None:
    entry = {"key": target.key, "title": target.title, "source_id": target.source_id}
    progress(f"Skimming [{target.key}] {target.title[:60]} (about 1 min)")
    try:
        result = await client.chat.ask(notebook_id, build_prompt(), source_ids=[target.source_id])
        own_conversations.add(result.conversation_id)
        note = render_note(target, notebook_id, result, datetime.date.today())
        note_key = zotero.create_child_note(target.key, note, [SKIM_NOTE_TAG])
    except Exception as e:  # one paper failing must not stop the run
        progress(f"  failed: {e}")
        report["failed"].append({**entry, "error": str(e)})
        return
    report["written"].append({**entry, "note_key": note_key})
