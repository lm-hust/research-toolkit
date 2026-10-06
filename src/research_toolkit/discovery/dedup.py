"""
src/research_toolkit/discovery/dedup.py
3-tier deduplication engine (DOI -> ArXiv ID -> Fuzzy Title).
"""

from __future__ import annotations

import difflib
import re
from typing import Dict, List, Optional, Tuple

from research_toolkit.discovery.models import PaperCandidate


class Deduplicator:
    """Cascading 3-level deduplicator across DOI, ArXiv ID, and Fuzzy Title."""

    def __init__(self, fuzzy_threshold: float = 0.90):
        self.fuzzy_threshold = fuzzy_threshold
        self.doi_map: Dict[str, PaperCandidate] = {}
        self.arxiv_map: Dict[str, PaperCandidate] = {}
        self.title_list: List[Tuple[str, PaperCandidate]] = []

    @staticmethod
    def clean_doi(doi: Optional[str]) -> Optional[str]:
        if not doi:
            return None
        d = doi.lower().strip()
        d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
        d = re.sub(r"^doi:", "", d)
        return d.strip("/")

    @staticmethod
    def clean_arxiv(aid: Optional[str]) -> Optional[str]:
        if not aid:
            return None
        a = aid.lower().strip()
        a = re.sub(r"^arxiv:", "", a)
        a = re.sub(r"v\d+$", "", a)
        return a.strip()

    @staticmethod
    def clean_title(title: str) -> str:
        t = (title or "").lower()
        t = re.sub(r"[^a-z0-9\s]", "", t)
        return re.sub(r"\s+", " ", t).strip()

    def merge_records(self, existing: PaperCandidate, incoming: PaperCandidate) -> None:
        """Merge incoming record into existing canonical record."""
        existing.citation_count = max(existing.citation_count, incoming.citation_count)
        existing.influential_citation_count = max(
            existing.influential_citation_count, incoming.influential_citation_count
        )
        existing.is_review = existing.is_review or incoming.is_review

        # Retain longer abstract
        if len(incoming.abstract) > len(existing.abstract):
            existing.abstract = incoming.abstract

        # Prefer available PDF URL
        if not existing.pdf_url and incoming.pdf_url:
            existing.pdf_url = incoming.pdf_url

        # Prefer higher venue impact
        if incoming.venue_impact > existing.venue_impact:
            existing.venue_impact = incoming.venue_impact
            existing.venue = incoming.venue

        # Merge external IDs
        existing.external_ids.update(incoming.external_ids)
        if not existing.doi and incoming.doi:
            existing.doi = self.clean_doi(incoming.doi)
        if not existing.arxiv_id and incoming.arxiv_id:
            existing.arxiv_id = self.clean_arxiv(incoming.arxiv_id)

        # Merge authors
        if len(incoming.authors) > len(existing.authors):
            existing.authors = incoming.authors

        # Relevance
        existing.relevance_score = max(existing.relevance_score, incoming.relevance_score)

    def process(self, candidates: List[PaperCandidate]) -> List[PaperCandidate]:
        results: List[PaperCandidate] = []

        for candidate in candidates:
            c_doi = self.clean_doi(candidate.doi)
            c_arxiv = self.clean_arxiv(candidate.arxiv_id)
            c_norm_title = self.clean_title(candidate.title)
            candidate.doi = c_doi
            candidate.arxiv_id = c_arxiv

            matched: Optional[PaperCandidate] = None

            # 1. DOI Matching
            if c_doi and c_doi in self.doi_map:
                matched = self.doi_map[c_doi]

            # 2. ArXiv Matching
            if not matched and c_arxiv and c_arxiv in self.arxiv_map:
                matched = self.arxiv_map[c_arxiv]

            # 3. Fuzzy Title Matching (within 1 publication year)
            if not matched and len(c_norm_title) > 8:
                for existing_norm_title, existing_cand in self.title_list:
                    if candidate.year and existing_cand.year:
                        if abs(candidate.year - existing_cand.year) > 1:
                            continue
                    sim = difflib.SequenceMatcher(None, c_norm_title, existing_norm_title).ratio()
                    if sim >= self.fuzzy_threshold:
                        matched = existing_cand
                        break

            if matched:
                self.merge_records(matched, candidate)
            else:
                if c_doi:
                    self.doi_map[c_doi] = candidate
                if c_arxiv:
                    self.arxiv_map[c_arxiv] = candidate
                if len(c_norm_title) > 8:
                    self.title_list.append((c_norm_title, candidate))
                results.append(candidate)

        return results
