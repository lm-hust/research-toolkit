"""
src/research_toolkit/discovery/curation.py
Interactive CurationCheckpoint terminal boundary for human-in-the-loop candidate screening.
Conforms to CONTEXT.md and ADR-0005.
"""

from __future__ import annotations

import io
import sys
from typing import Any, List, Optional, Set

from research_toolkit.discovery.models import PaperCandidate


class CurationCheckpoint:
    """
    Interactive terminal boundary allowing the researcher to inspect, toggle,
    and curate candidate papers (highlighting topological roles and co-citation counts)
    before writing to ZoteroCollection.
    """

    def __init__(self, stream: Optional[Any] = None):
        self.stream = stream or sys.stdout

    def _format_role_tag(self, role: str) -> str:
        role_lower = (role or "").lower()
        if "foundational" in role_lower:
            return "[FOUNDATIONAL]"
        elif "recent" in role_lower or "sota" in role_lower:
            return "[SOTA/ADV]"
        elif "seed" in role_lower:
            return "[SEED]"
        return "[-]"

    def render_table(self, candidates: List[PaperCandidate], selected_indices: Set[int]) -> str:
        try:
            from rich.console import Console
            from rich.table import Table

            buf = io.StringIO()
            console = Console(file=buf, force_terminal=False, color_system=None, width=130)
            table = Table(
                title="🔍 CurationCheckpoint: Review Discovered Literature Candidates",
                show_header=True,
                header_style="bold",
            )
            table.add_column("Sel", justify="center", width=5)
            table.add_column("#", justify="right", width=4)
            table.add_column("Topology Role", justify="center", width=16)
            table.add_column("Title", style="bold", min_width=30)
            table.add_column("Year", justify="center", width=6)
            table.add_column("Co-Cites", justify="right", width=9)
            table.add_column("Total Cites", justify="right", width=11)
            table.add_column("Score", justify="right", width=7)
            table.add_column("Venue / DOI", min_width=20)

            for idx, p in enumerate(candidates, start=1):
                status_icon = "[X]" if (idx - 1) in selected_indices else "[ ]"
                role_tag = self._format_role_tag(p.topological_role)
                title_disp = (p.title[:50] + "...") if len(p.title) > 53 else p.title
                venue_doi = p.doi or p.venue or p.paper_id
                venue_disp = (venue_doi[:22] + "...") if len(venue_doi) > 25 else venue_doi

                table.add_row(
                    status_icon,
                    str(idx),
                    role_tag,
                    title_disp,
                    str(p.year or "-"),
                    str(p.co_citation_count),
                    str(p.citation_count),
                    f"{p.composite_score:.3f}",
                    venue_disp,
                )

            console.print(table)
            return buf.getvalue()
        except ImportError:
            # Fallback plain text representation
            lines = [
                "Sel  #   Role           Title                                Year Co-Cites Total Score DOI"
            ]
            for idx, p in enumerate(candidates, start=1):
                status_icon = "[X]" if (idx - 1) in selected_indices else "[ ]"
                role_tag = self._format_role_tag(p.topological_role).ljust(14)
                title_disp = (
                    (p.title[:35] + "...").ljust(38)
                    if len(p.title) > 35
                    else p.title.ljust(38)
                )
                lines.append(
                    f"{status_icon}  {idx:<3} {role_tag} {title_disp} {p.year or '-'}  {p.co_citation_count:<8} {p.citation_count:<5} {p.composite_score:.3f} {p.doi or ''}"
                )
            return "\n".join(lines) + "\n"

    def review(
        self,
        candidates: List[PaperCandidate],
        auto_confirm: bool = False,
        interactive: Optional[bool] = None,
    ) -> List[PaperCandidate]:
        if not candidates:
            return []

        selected_indices: Set[int] = set(range(len(candidates)))
        is_interactive = (
            interactive
            if interactive is not None
            else (hasattr(sys.stdin, "isatty") and sys.stdin.isatty())
        )

        if auto_confirm or not is_interactive:
            output = self.render_table(candidates, selected_indices)
            print(output, file=self.stream)
            return [candidates[i] for i in sorted(selected_indices)]

        while True:
            output = self.render_table(candidates, selected_indices)
            print(output, file=self.stream)
            print(
                f"\n📌 CurationCheckpoint: {len(selected_indices)}/{len(candidates)} papers selected.\n"
                "Commands:\n"
                "  - Enter numbers (e.g. '1 3 5') to toggle selection\n"
                "  - 'a' to select all, 'n' to select none\n"
                "  - 'f' to toggle all [FOUNDATIONAL], 's' to toggle all [SOTA/ADV]\n"
                "  - Press [Enter] to confirm and write selected to Zotero\n"
                "  - 'q' to abort without saving",
                file=self.stream,
            )
            try:
                choice = input("\nAction: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return []

            if choice == "q":
                print("CurationCheckpoint aborted.", file=self.stream)
                return []
            elif choice == "":
                break
            elif choice == "a":
                selected_indices = set(range(len(candidates)))
            elif choice == "n":
                selected_indices = set()
            elif choice == "f":
                foundational_indices = {
                    i
                    for i, c in enumerate(candidates)
                    if "foundational" in c.topological_role.lower()
                }
                if foundational_indices.issubset(selected_indices):
                    selected_indices -= foundational_indices
                else:
                    selected_indices |= foundational_indices
            elif choice == "s":
                sota_indices = {
                    i
                    for i, c in enumerate(candidates)
                    if "recent" in c.topological_role.lower()
                    or "sota" in c.topological_role.lower()
                }
                if sota_indices.issubset(selected_indices):
                    selected_indices -= sota_indices
                else:
                    selected_indices |= sota_indices
            else:
                tokens = choice.replace(",", " ").split()
                for tok in tokens:
                    try:
                        num = int(tok)
                        idx = num - 1
                        if 0 <= idx < len(candidates):
                            if idx in selected_indices:
                                selected_indices.remove(idx)
                            else:
                                selected_indices.add(idx)
                    except ValueError:
                        pass

        curated = [candidates[i] for i in sorted(selected_indices)]
        print(f"✅ Confirmed {len(curated)} curated papers.", file=self.stream)
        return curated
