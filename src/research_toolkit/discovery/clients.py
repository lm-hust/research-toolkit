"""
src/research_toolkit/discovery/clients.py
Semantic Scholar and OpenAlex API clients with rate-limiting and abstract reconstruction.
Conforms to CONTEXT.md and ADR-0001.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.query import QueryTranslator

logger = logging.getLogger(__name__)

REVIEW_KEYWORD_REGEX = re.compile(
    r"\b(review|survey|systematic review|meta-analysis|overview|progress in)\b",
    re.IGNORECASE,
)

EXCLUDED_OPENALEX_TYPES = {
    "book",
    "book-chapter",
    "book-review",
    "book-section",
    "book-series",
    "dataset",
    "paratext",
    "erratum",
}


def reconstruct_openalex_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """Reconstructs text from OpenAlex abstract_inverted_index."""
    if not inverted_index:
        return ""
    pos_pairs: List[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            pos_pairs.append((pos, word))
    pos_pairs.sort(key=lambda x: x[0])
    return " ".join(word for _, word in pos_pairs)


class SemanticScholarClient:
    """
    Semantic Scholar Academic Graph API client.
    Enforces 1 request/second throttling to respect API rate limits.
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None, min_interval: float = 1.0):
        self.api_key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.min_interval = min_interval
        self._last_call_time = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call_time = time.time()

    def search(self, query: str, limit: int = 10, offset: int = 0) -> List[PaperCandidate]:
        self._throttle()
        clean_query = QueryTranslator.to_semantic_scholar(query) or query
        fields = (
            "paperId,title,abstract,year,citationCount,influentialCitationCount,"
            "publicationTypes,openAccessPdf,externalIds,venue,journal,authors"
        )
        params = {
            "query": clean_query,
            "limit": limit,
            "offset": offset,
            "fields": fields,
        }
        url = f"{self.BASE_URL}/paper/search?{urllib.parse.urlencode(params)}"
        headers = {"User-Agent": "ResearchToolkit/0.1.0"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.info(
                    "Semantic Scholar unauthenticated pool rate limit (HTTP 429). Gracefully falling back to OpenAlex."
                )
            else:
                logger.warning("Semantic Scholar search failed: %s", e)
            return []
        except Exception as e:
            logger.warning("Semantic Scholar search failed: %s", e)
            return []

        candidates: List[PaperCandidate] = []
        for item in data.get("data", []):
            pub_types = item.get("publicationTypes") or []
            if any("book" in pt.lower() for pt in pub_types):
                continue

            title = item.get("title") or "Untitled"
            is_rev = "Review" in pub_types or bool(REVIEW_KEYWORD_REGEX.search(title))

            ext_ids = item.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            arxiv = ext_ids.get("ArXiv")

            oa_pdf = item.get("openAccessPdf") or {}
            pdf_url = oa_pdf.get("url") if isinstance(oa_pdf, dict) else None

            authors = [a.get("name") for a in item.get("authors", []) if a.get("name")]

            candidate = PaperCandidate(
                paper_id=item.get("paperId", f"s2_{title[:10]}"),
                title=title,
                year=item.get("year"),
                authors=authors,
                citation_count=item.get("citationCount") or 0,
                influential_citation_count=item.get("influentialCitationCount") or 0,
                venue=item.get("venue") or "",
                is_review=is_rev,
                doi=doi,
                arxiv_id=arxiv,
                abstract=item.get("abstract") or "",
                pdf_url=pdf_url,
                source_platform="semantic_scholar",
                relevance_score=0.85,
                external_ids=ext_ids,
            )
            candidates.append(candidate)

        return candidates


class OpenAlexClient:
    """
    OpenAlex Works API client.
    Supports inverted index abstract reconstruction and 2-year citedness metric.
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENALEX_API_KEY")

    def _request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """Unified outbound request channel conforming to CODING_STANDARDS.md."""
        query_params = dict(params or {})
        if self.api_key:
            query_params["api_key"] = self.api_key

        url = f"{self.BASE_URL}{endpoint}"
        if query_params:
            url = f"{url}?{urllib.parse.urlencode(query_params)}"

        headers = {"User-Agent": "ResearchToolkit/0.1.0"}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.info("OpenAlex pool rate limit (HTTP 429).")
            else:
                logger.warning("OpenAlex request to %s failed: %s", endpoint, e)
            return None
        except Exception as e:
            logger.warning("OpenAlex request to %s failed: %s", endpoint, e)
            return None

    def get_source_impact(self, source_id: str) -> float:
        """Fetches 2-year mean citedness for an OpenAlex source ID (e.g. S4306401280)."""
        clean_id = source_id.split("/")[-1].strip()
        if not clean_id.startswith("S"):
            return 0.0

        data = self._request(f"/sources/{clean_id}", timeout=5.0)
        if not data:
            return 0.0

        summary_stats = data.get("summary_stats") or {}
        return float(summary_stats.get("2yr_mean_citedness") or 0.0)

    def search(self, query: str, limit: int = 10) -> List[PaperCandidate]:
        clean_query = QueryTranslator.to_openalex(query) or query
        params = {
            "search": clean_query,
            "per_page": limit,
            "select": (
                "id,doi,title,abstract_inverted_index,cited_by_count,"
                "primary_location,type,publication_year,authorships"
            ),
        }
        data = self._request("/works", params=params, timeout=30.0)
        if not data:
            return []

        candidates: List[PaperCandidate] = []
        for item in data.get("results", []):
            work_type = (item.get("type") or "").lower()
            if work_type in EXCLUDED_OPENALEX_TYPES or work_type.startswith("book"):
                continue

            title = item.get("title") or "Untitled"
            is_rev = work_type == "review" or bool(REVIEW_KEYWORD_REGEX.search(title))

            abstract = reconstruct_openalex_abstract(item.get("abstract_inverted_index"))

            primary_loc = item.get("primary_location") or {}
            pdf_url = primary_loc.get("pdf_url")
            source_info = primary_loc.get("source") or {}
            venue_name = source_info.get("display_name") or ""
            summary_stats = source_info.get("summary_stats") or {}
            venue_impact = float(summary_stats.get("2yr_mean_citedness") or 0.0)

            authors = []
            for authorship in item.get("authorships", []):
                author = authorship.get("author", {})
                if author.get("display_name"):
                    authors.append(author["display_name"])

            raw_doi = item.get("doi")
            doi_val = raw_doi.replace("https://doi.org/", "") if raw_doi else None

            source_id = source_info.get("id") or ""
            ext_ids = {"openalex_source_id": source_id} if source_id else {}

            candidate = PaperCandidate(
                paper_id=item.get("id", f"oa_{title[:10]}"),
                title=title,
                year=item.get("publication_year"),
                authors=authors,
                citation_count=item.get("cited_by_count") or 0,
                venue=venue_name,
                venue_impact=venue_impact,
                is_review=is_rev,
                doi=doi_val,
                abstract=abstract,
                pdf_url=pdf_url,
                source_platform="openalex",
                relevance_score=0.85,
                external_ids=ext_ids,
            )
            candidates.append(candidate)

        return candidates
