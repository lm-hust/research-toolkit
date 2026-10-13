"""Pointers an agent follows: every relative Markdown link and #anchor in fact2query and its trial recipes resolves."""

import functools
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TARGET_DOC_ROOTS = [ROOT / "skills" / "fact2query", ROOT / "docs" / "agents" / "fact2query-trials"]
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*$")
FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})")


def slug(heading: str) -> str:
    """GitHub-style heading anchor."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def prose_lines(path: Path) -> list[str]:
    """Lines outside ``` / ~~~ fences at any indentation (a fence closes on the same character, at least as long)."""
    lines, fence = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if fence:
            if re.match(rf"^\s*{re.escape(fence)}+\s*$", line):
                fence = None
            continue
        opened = FENCE_OPEN.match(line)
        if opened:
            fence = opened.group(1)
            continue
        lines.append(line)
    return lines


@functools.lru_cache(maxsize=None)
def anchors(path: Path) -> frozenset[str]:
    """GitHub anchors: repeated slugs get -1, -2, ... in document order."""
    seen: dict[str, int] = {}
    result = set()
    for line in prose_lines(path):
        heading = HEADING.match(line)
        if not heading:
            continue
        base = slug(heading.group(1))
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.add(f"{base}-{count}" if count else base)
    return frozenset(result)


def relative_links(path: Path) -> list[str]:
    body = "\n".join(prose_lines(path))
    return [target for target in LINK.findall(body) if not re.match(r"^[a-z][a-z0-9+.-]*:", target)]


MARKDOWN = sorted(doc for tree in TARGET_DOC_ROOTS for doc in tree.rglob("*.md"))


@pytest.mark.parametrize("doc", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_skill_links_and_anchors_resolve(doc: Path) -> None:
    broken = []
    for target in relative_links(doc):
        file_part, _, anchor = target.partition("#")
        resolved = (doc.parent / file_part).resolve() if file_part else doc
        if not resolved.exists():
            broken.append(f"{target}: missing file")
        elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
            broken.append(f"{target}: missing anchor")
    assert not broken, broken


def test_slug_matches_github_heading_anchors() -> None:
    assert slug("Identity and access") == "identity-and-access"
    assert slug("1. Load the dependency and pin identity") == "1-load-the-dependency-and-pin-identity"
    assert slug("Access guards (separate fresh fixture runs)") == "access-guards-separate-fresh-fixture-runs"


def test_duplicate_headings_get_github_numeric_suffixes(tmp_path: Path) -> None:
    doc = tmp_path / "dup.md"
    doc.write_text("# Notes\n\n## Notes\n\n### Notes\n", encoding="utf-8")
    assert anchors(doc) == {"notes", "notes-1", "notes-2"}


def test_hash_lines_inside_tilde_and_indented_fences_are_not_headings(tmp_path: Path) -> None:
    doc = tmp_path / "fenced.md"
    doc.write_text(
        "# Real\n\n~~~bash\n# tilde comment\n~~~\n\n- item\n\n  ```bash\n  # indented fence comment\n  ```\n\n"
        "    # indented code block\n",
        encoding="utf-8",
    )
    assert anchors(doc) == {"real"}
