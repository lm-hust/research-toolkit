"""Skill pointers an agent follows: every relative Markdown link and #anchor under skills/ resolves."""

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "skills"
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def slug(heading: str) -> str:
    """GitHub-style heading anchor."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    body = FENCE.sub("", path.read_text(encoding="utf-8"))
    return {slug(h) for h in HEADING.findall(body)}


def relative_links(path: Path) -> list[str]:
    body = FENCE.sub("", path.read_text(encoding="utf-8"))
    return [t for t in LINK.findall(body) if not re.match(r"^[a-z][a-z0-9+.-]*:", t)]


MARKDOWN = sorted(SKILLS.rglob("*.md"))


@pytest.mark.parametrize("doc", MARKDOWN, ids=lambda p: str(p.relative_to(SKILLS)))
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
