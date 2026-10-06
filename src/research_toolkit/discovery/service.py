"""
src/research_toolkit/discovery/service.py
DiscoveryService coordinating clients, deduplication, and ranking.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from research_toolkit.discovery.clients import OpenAlexClient, SemanticScholarClient
from research_toolkit.discovery.dedup import Deduplicator
from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.ranker import Ranker

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Coordinates multi-source literature retrieval, deduplication, and stratified ranking."""

    def __init__(
        self,
        s2_client: Optional[SemanticScholarClient] = None,
        oa_client: Optional[OpenAlexClient] = None,
        deduplicator: Optional[Deduplicator] = None,
        ranker: Optional[Ranker] = None,
    ):
        self.s2_client = s2_client or SemanticScholarClient()
        self.oa_client = oa_client or OpenAlexClient()
        self.deduplicator = deduplicator or Deduplicator()
        self.ranker = ranker or Ranker()

    def search_and_rank(
        self, topic: str, top_k: int = 8, limit_per_source: Optional[int] = None
    ) -> List[PaperCandidate]:
        """
        Retrieves candidates from Semantic Scholar and OpenAlex, deduplicates them,
        and returns the top-k candidates ranked with review quota guarantees.
        """
        query_limit = limit_per_source or max(15, top_k * 2)

        s2_candidates = self.s2_client.search(topic, limit=query_limit)
        oa_candidates = self.oa_client.search(topic, limit=query_limit)

        combined = list(s2_candidates) + list(oa_candidates)
        if not combined:
            return []

        deduped = self.deduplicator.process(combined)
        ranked = self.ranker.rank_and_select(deduped, top_k=top_k)
        return ranked

    def format_table(self, candidates: List[PaperCandidate]) -> str:
        """Formats ranked candidates into a structured terminal table."""
        if not candidates:
            return "No candidates found."

        try:
            import io

            from rich.console import Console
            from rich.table import Table

            buf = io.StringIO()
            console = Console(file=buf, force_terminal=False, color_system=None, width=120)
            table = Table(title="Literature Discovery Candidates", show_header=True, header_style="bold")
            table.add_column("Rank", justify="right", style="cyan", width=5)
            table.add_column("Type", justify="center", width=6)
            table.add_column("Title", style="bold", min_width=30)
            table.add_column("Year", justify="center", width=6)
            table.add_column("Cites", justify="right", width=7)
            table.add_column("Venue", min_width=15)
            table.add_column("Score", justify="right", width=7)
            table.add_column("DOI / Identifier", min_width=20)

            for idx, p in enumerate(candidates, start=1):
                doc_type = "[REV]" if p.is_review else "[RES]"
                doi_or_id = p.doi or p.arxiv_id or p.paper_id
                title_disp = (p.title[:55] + "...") if len(p.title) > 58 else p.title
                venue_disp = (p.venue[:22] + "...") if len(p.venue) > 25 else (p.venue or "-")
                table.add_row(
                    str(idx),
                    doc_type,
                    title_disp,
                    str(p.year or "-"),
                    str(p.citation_count),
                    venue_disp,
                    f"{p.composite_score:.3f}",
                    doi_or_id,
                )

            console.print(table)
            return buf.getvalue()
        except ImportError:
            # Fallback plain ASCII table
            headers = ["#", "Type", "Title", "Year", "Cites", "Score", "DOI"]
            rows = []
            for idx, p in enumerate(candidates, start=1):
                doc_type = "[REV]" if p.is_review else "[RES]"
                doi_disp = p.doi or p.arxiv_id or p.paper_id
                title_disp = (p.title[:45] + "...") if len(p.title) > 48 else p.title
                rows.append([
                    str(idx),
                    doc_type,
                    title_disp,
                    str(p.year or "-"),
                    str(p.citation_count),
                    f"{p.composite_score:.3f}",
                    doi_disp,
                ])
            col_widths = [max(len(row[i]) for row in [headers] + rows) for i in range(len(headers))]
            fmt = " | ".join(f"{{:<{w}}}" for w in col_widths)
            sep = "-+-".join("-" * w for w in col_widths)
            lines = [fmt.format(*headers), sep]
            for row in rows:
                lines.append(fmt.format(*row))
            return "\n".join(lines)
