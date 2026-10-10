"""
src/research_toolkit/notebook/skim.py
Skim papers in a Gemini Notebook: one structured question per `[key]` source, asked in a fresh
conversation restricted to that source, written back as a child note on the Zotero item.

Prompt and note are separate steps: `build_prompt()` lists `SECTIONS` as `## <heading>` blocks,
`render_note()` turns Gemini's markdown answer plus its `cited_text` references into the Zotero
note HTML. Gemini's page numbers are unreliable, so provenance is `cited_text` only.

With a focus question the prompt adds a `RELEVANCE_HEADING` section; `parse_relevance()` reads the
level from it and the Zotero item gets one `gemini-skim/relevance:<level>` tag. A level that cannot
be read is reported as "unparsed" and no tag is touched.

Runs are idempotent by the `SKIM_NOTE_TAG` child note: papers that have one are skipped, or with
`refresh` re-read into that same note (updated by version). Before asking, the usage meter's
tightest window is compared with one QNA ask per remaining paper; a shortfall needs `confirm()`.
"""

from __future__ import annotations

import asyncio
import datetime
import html
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

import notebooklm
from notebooklm import AskResult, ChatReference, UsageActionKind, UsageWindow, UsageWindowKind

from research_toolkit.notebook import client as notebook_client
from research_toolkit.notebook.client import NotebookClient
from research_toolkit.notebook.history import clear_conversation
from research_toolkit.notebook.resolve import NotebookResolutionError, resolve_notebook
from research_toolkit.notebook.titles import source_key, source_paper_title
from research_toolkit.zotero.client import ZoteroClient

Progress = Callable[[str], None]
Confirm = Callable[[], bool]

SKIM_NOTE_TAG = "gemini-skim/ai-note"
NOTE_TITLE_PREFIX = "Gemini 初读："
SNIPPET_CHARS = 300
RELEVANCE_TAG_PREFIX = "gemini-skim/relevance:"
RELEVANCE_HEADING = "与研究问题的相关性"
RELEVANCE_LEVELS = ("high", "medium", "low")
UNPARSED = "unparsed"

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


def build_prompt(focus: Optional[str] = None) -> str:
    sections = list(SECTIONS)
    if focus:
        sections.append(
            (
                RELEVANCE_HEADING,
                f"研究问题：{focus}\n第一行只写一个字：高、中 或 低，表示这篇论文与该研究问题的相关性；"
                "从第二行起写理由。",
            )
        )
    blocks = "\n".join(f"## {heading}\n{guide}" for heading, guide in sections)
    return (
        "请只根据这篇来源，用中文对论文做结构化初读。严格按下面的小节输出，"
        "每个小节以给定的二级标题（## 标题）开头，不要增加其他小节，不要写页码。\n\n"
        f"{blocks}"
    )


_LEVEL_WORDS = {"高": "high", "中": "medium", "低": "low", "high": "high", "medium": "medium", "low": "low"}
_LEVEL_AT_START = re.compile(
    r"^(?:(?:相关性|相关程度|relevance)(?:等级|level)?\s*[:：]?\s*)?"
    r"(高|中|低|high|medium|low)(?![a-z/／、|])",
    re.IGNORECASE,
)


def parse_relevance(answer: str) -> Optional[str]:
    """`high|medium|low` from the first line of the relevance section, or None if unreadable."""
    in_section = False
    for raw in answer.splitlines():
        heading = re.match(r"^\s*#{1,6}\s*(.*)$", raw)
        if heading:
            title = heading.group(1).lower()
            in_section = "相关性" in title or "relevance" in title
            if not in_section:
                continue
            # "## 相关性：中" puts the level on the heading line itself
            raw = re.split(r"[:：]", heading.group(1), maxsplit=1)[1] if re.search(r"[:：]", title) else ""
        line = re.sub(r"[*_`>#\-]", "", raw).strip()
        if not in_section or not line:
            continue
        match = _LEVEL_AT_START.match(line)
        return _LEVEL_WORDS[match.group(1).lower()] if match else None
    return None


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
    target: SkimTarget,
    notebook_id: str,
    result: AskResult,
    today: datetime.date,
    focus: Optional[str] = None,
) -> str:
    """Zotero note HTML. Zotero shows a note's first line as its title."""
    lines = [
        f"笔记本 UUID：{html.escape(notebook_id)}",
        f"来源 ID：{html.escape(target.source_id)}",
        f"日期：{today.isoformat()}",
        f"生成工具：notebooklm-py {notebooklm.__version__}",
        f"标签：{SKIM_NOTE_TAG}",
    ]
    if focus:
        lines.append(f"研究问题：{html.escape(focus, quote=False)}")
    header = "<br/>".join(lines)
    relevance = parse_relevance(result.answer) if focus else None
    metadata = (
        f' data-gemini-skim-focus="{html.escape(focus or "", quote=True)}"'
        f' data-gemini-skim-relevance="{relevance}"'
        if relevance else ""
    )
    parts = [
        f"<h1>{html.escape(NOTE_TITLE_PREFIX + target.title, quote=False)}</h1>",
        f"<p{metadata}>{header}</p>",
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
    focus: Optional[str] = None,
    refresh: bool = False,
    confirm: Confirm = lambda: True,
) -> dict[str, Any]:
    """Skims the `[key]` sources named by `keys` (all `[key]` sources when empty) and returns the
    JSON-ready report.

    A paper that already has a skim note is skipped, or with `refresh` re-read into that same note.
    When the quota looks too small for the papers left to read, `confirm()` decides whether to go
    on; False raises SkimError before anything is written.
    With `focus`, each paper is also rated for relevance to that question and tagged in Zotero.
    """
    return asyncio.run(_skim(zotero, notebook_ref, keys, progress, focus, refresh, confirm))


@dataclass(frozen=True)
class _Pending:
    target: SkimTarget
    existing_note: Optional[dict[str, Any]]  # the skim note to rewrite (refresh), or None


def _window_name(window: UsageWindow) -> str:
    return "weekly" if window.kind is UsageWindowKind.WEEKLY else "five_hour"


async def _quota(client: NotebookClient, papers: int = 0) -> Optional[dict[str, Any]]:
    """
    The tightest usage window, plus (for `papers` > 0) the estimated cost of one ask per paper.
    None when the meter is unavailable: an unknown quota never blocks a run.
    """
    try:
        usage = await client.settings.get_usage()
    except Exception:
        return None
    if not usage.available or not usage.windows:
        return None
    window = min(usage.windows, key=lambda w: w.remaining_percent)
    quota: dict[str, Any] = {
        "window": _window_name(window),
        "remaining_percent": round(window.remaining_percent, 3),
        "resets_at": window.resets_at.isoformat(),
    }
    if papers:
        qna = usage.action(UsageActionKind.QNA)
        cost = qna.estimated_cost_percent if qna is not None else None
        quota["needed_percent"] = round(papers * cost, 3) if cost is not None else None
    return quota


async def _skim(
    zotero: ZoteroClient,
    notebook_ref: str,
    keys: list[str],
    progress: Progress,
    focus: Optional[str],
    refresh: bool,
    confirm: Confirm,
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
            "updated": [],
            "skipped": [],
            "failed": [],
            "relevance": {**{level: 0 for level in RELEVANCE_LEVELS}, UNPARSED: 0},
            "quota_before": None,
            "quota_after": None,
        }
        by_key: dict[str, SkimTarget] = {}
        for src in await client.sources.list(notebook.id):
            key = source_key(src.title)
            if key and key not in by_key:
                by_key[key] = SkimTarget(key, source_paper_title(src.title), src.id)

        pending = _plan(zotero, by_key, keys or list(by_key), refresh, report, focus)
        report["quota_before"] = await _check_quota(client, len(pending), progress, confirm)

        own_conversations: set[str] = set()
        for item in pending:
            try:
                saved = await clear_conversation(client, notebook.id, own_conversations)
            except Exception as e:
                raise SkimError(
                    f"Could not save the notebook's current conversation; nothing was deleted: {e}"
                ) from e
            if saved is not None:
                report["saved_history_note"] = True
                progress(f"Saved the existing conversation as notebook note '{saved.title}'")
            await _skim_one(
                client, zotero, notebook.id, item, own_conversations, report, progress, focus
            )
        report["quota_after"] = await _quota(client)
        return report


def _plan(
    zotero: ZoteroClient,
    by_key: dict[str, SkimTarget],
    keys: list[str],
    refresh: bool,
    report: dict[str, Any],
    focus: Optional[str] = None,
) -> list[_Pending]:
    """Papers to ask about; unknown keys go to `failed`, already-skimmed ones to `skipped`."""
    pending: list[_Pending] = []
    for key in keys:
        target = by_key.get(key)
        if target is None:
            report["failed"].append(
                {"key": key, "title": "", "error": f"No source titled '[{key}] ...' in the notebook."}
            )
            continue
        entry = {"key": target.key, "title": target.title, "source_id": target.source_id}
        try:
            notes = zotero.find_child_notes(target.key, SKIM_NOTE_TAG)
        except Exception as e:  # one paper failing must not stop the run
            report["failed"].append({**entry, "error": f"Could not look up its skim note: {e}"})
            continue
        existing = notes[0] if notes else None
        if existing is not None and not refresh:
            entry["note_key"] = existing["key"]
            # A note may have landed before its relevance tag write failed. Reuse its
            # stored judgement only for the exact same focus, without another ask.
            marker = f'data-gemini-skim-focus="{html.escape(focus or "", quote=True)}"'
            stored = existing.get("note", "")
            match = re.search(r'data-gemini-skim-relevance="(high|medium|low)"', stored)
            if focus and marker in stored and match:
                level = match.group(1)
                try:
                    zotero.replace_tags_with_prefix(
                        target.key, RELEVANCE_TAG_PREFIX, [RELEVANCE_TAG_PREFIX + level]
                    )
                except Exception as e:
                    report["failed"].append({**entry, "error": f"Relevance tag not set: {e}"})
                    continue
                entry["relevance"] = level
                report["relevance"][level] += 1
            report["skipped"].append(entry)
            continue
        pending.append(_Pending(target, existing))
    return pending


async def _check_quota(
    client: NotebookClient, papers: int, progress: Progress, confirm: Confirm
) -> Optional[dict[str, Any]]:
    quota = await _quota(client, papers)
    if quota is None:
        progress("Quota unknown (usage meter unavailable); continuing.")
        return None
    needed = quota.get("needed_percent")
    if needed is not None and needed > quota["remaining_percent"]:
        progress(
            f"Skimming {papers} papers needs about {needed:.2f}% of the {quota['window']} quota, "
            f"but only {quota['remaining_percent']:.2f}% remains (resets {quota['resets_at']}). "
            "The run may stop partway; re-running later resumes it."
        )
        if not confirm():
            raise SkimError("Stopped before skimming: not enough quota and the run was not confirmed.")
    return quota


async def _skim_one(
    client: NotebookClient,
    zotero: ZoteroClient,
    notebook_id: str,
    item: _Pending,
    own_conversations: set[str],
    report: dict[str, Any],
    progress: Progress,
    focus: Optional[str] = None,
) -> None:
    target, existing = item.target, item.existing_note
    entry: dict[str, Any] = {"key": target.key, "title": target.title, "source_id": target.source_id}
    progress(f"Skimming [{target.key}] {target.title[:60]} (about 1 min)")
    try:
        result = await client.chat.ask(
            notebook_id, build_prompt(focus), source_ids=[target.source_id]
        )
        own_conversations.add(result.conversation_id)
        note = render_note(target, notebook_id, result, datetime.date.today(), focus)
        if existing is None:
            note_key = zotero.create_child_note(target.key, note, [SKIM_NOTE_TAG])
        else:
            note_key = existing["key"]
            zotero.update_note(existing, note)
    except Exception as e:  # one paper failing must not stop the run
        progress(f"  failed: {e}")
        report["failed"].append({**entry, "error": str(e)})
        return
    entry["note_key"] = note_key
    if focus:
        level = parse_relevance(result.answer)
        if level is None:
            progress("  relevance could not be read from the answer; no tag set")
        else:
            try:
                zotero.replace_tags_with_prefix(
                    target.key, RELEVANCE_TAG_PREFIX, [RELEVANCE_TAG_PREFIX + level]
                )
            except Exception as e:
                progress(f"  note written, relevance tag failed: {e}")
                report["failed"].append({**entry, "error": f"Relevance tag not set: {e}"})
                return
        entry["relevance"] = level or UNPARSED
        report["relevance"][entry["relevance"]] += 1
    report["updated" if existing is not None else "written"].append(entry)
