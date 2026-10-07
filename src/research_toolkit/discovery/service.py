"""
src/research_toolkit/discovery/service.py
DiscoveryService coordinating clients, deduplication, and ranking.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from research_toolkit.discovery.clients import OpenAlexClient, SemanticScholarClient
from research_toolkit.discovery.dedup import Deduplicator
from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.ranker import Ranker
from research_toolkit.discovery.snowballer import CitationSnowballer

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Coordinates multi-source literature retrieval, deduplication, graph snowballing, and stratified ranking."""

    def __init__(
        self,
        s2_client: Optional[SemanticScholarClient] = None,
        oa_client: Optional[OpenAlexClient] = None,
        deduplicator: Optional[Deduplicator] = None,
        ranker: Optional[Ranker] = None,
        snowballer: Optional[CitationSnowballer] = None,
    ):
        self.s2_client = s2_client or SemanticScholarClient()
        self.oa_client = oa_client or OpenAlexClient()
        self.deduplicator = deduplicator or Deduplicator()
        self.ranker = ranker or Ranker()
        self.snowballer = snowballer or CitationSnowballer(oa_client=self.oa_client)

    def search_and_rank(
        self,
        topic: str,
        top_k: int = 8,
        limit_per_source: Optional[int] = None,
        sort_by: str = "composite",
        min_cites: int = 0,
        year_range: Optional[Tuple[int, int]] = None,
        peer_reviewed_only: bool = False,
        snowball: bool = True,
        min_co_cites: int = 1,
    ) -> List[PaperCandidate]:
        """
        Retrieves candidates from Semantic Scholar and OpenAlex, deduplicates them,
        optionally executes 1-hop bidirectional citation snowballing across OpenAlex,
        and returns the top-k candidates ranked with specified sorting and filtering.
        """
        query_limit = limit_per_source or max(15, top_k * 2)

        s2_candidates = self.s2_client.search(topic, limit=query_limit)
        oa_candidates = self.oa_client.search(topic, limit=query_limit)

        combined = list(s2_candidates) + list(oa_candidates)
        if not combined:
            # Auto-relax retry if complex query with quotes or boolean operators yielded 0 results
            if '"' in topic or any(kw in topic for kw in ("AND", "OR", "(", ")")):
                relaxed = re.sub(r'["\'()]', " ", topic)
                relaxed = re.sub(r"\b(AND|OR|NOT)\b", " ", relaxed, flags=re.IGNORECASE)
                relaxed_topic = " ".join(relaxed.split())
                if relaxed_topic and relaxed_topic != topic:
                    logger.info("Zero initial results; auto-relaxing query to: %s", relaxed_topic)
                    s2_retry = self.s2_client.search(relaxed_topic, limit=query_limit)
                    oa_retry = self.oa_client.search(relaxed_topic, limit=query_limit)
                    combined = list(s2_retry) + list(oa_retry)

        if not combined:
            return []

        deduped = self.deduplicator.process(combined)

        # 1-Hop Citation Snowballing expansion
        if snowball and deduped:
            try:
                # Use up to 6 highest-relevance initial seeds for graph expansion
                seed_batch = deduped[:6]
                snowball_res = self.snowballer.snowball(
                    seed_batch,
                    min_co_citations=min_co_cites,
                    max_backward=15,
                    max_forward=15,
                )
                candidates_to_rank = snowball_res.all_candidates
            except Exception as e:
                logger.warning("Citation snowballing failed, falling back to direct seeds: %s", e)
                candidates_to_rank = deduped
        else:
            candidates_to_rank = deduped

        ranked = self.ranker.rank_and_select(
            candidates_to_rank,
            top_k=top_k,
            sort_by=sort_by,
            min_cites=min_cites,
            year_range=year_range,
            peer_reviewed_only=peer_reviewed_only,
        )
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
                if p.is_review:
                    doc_type = "[REV]"
                elif p.is_preprint:
                    doc_type = "[PRE]"
                else:
                    doc_type = "[RES]"

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
                if p.is_review:
                    doc_type = "[REV]"
                elif p.is_preprint:
                    doc_type = "[PRE]"
                else:
                    doc_type = "[RES]"
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
