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

    def _parse_work_item(self, item: Dict[str, Any]) -> Optional[PaperCandidate]:
        """Parses an OpenAlex work entity dictionary into PaperCandidate."""
        work_type = (item.get("type") or "").lower()
        if work_type in EXCLUDED_OPENALEX_TYPES or work_type.startswith("book"):
            return None

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
        referenced = item.get("referenced_works") or []

        return PaperCandidate(
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
            referenced_works=referenced,
        )

    def search(self, query: str, limit: int = 10) -> List[PaperCandidate]:
        clean_query = QueryTranslator.to_openalex(query) or query
        params = {
            "search": clean_query,
            "per_page": limit,
            "select": (
                "id,doi,title,abstract_inverted_index,cited_by_count,"
                "primary_location,type,publication_year,authorships,referenced_works"
            ),
        }
        data = self._request("/works", params=params, timeout=30.0)
        if not data:
            return []

        candidates: List[PaperCandidate] = []
        for item in data.get("results", []):
            cand = self._parse_work_item(item)
            if cand:
                candidates.append(cand)
        return candidates

    def get_works_by_ids(self, work_ids: List[str]) -> List[PaperCandidate]:
        """
        Batch retrieves work entities for up to 100 IDs per chunk using the pipe '|' operator.
        """
        if not work_ids:
            return []

        clean_ids = [w.split("/")[-1].strip() for w in work_ids if w.strip()]
        if not clean_ids:
            return []

        candidates: List[PaperCandidate] = []
        batch_size = 50
        for i in range(0, len(clean_ids), batch_size):
            chunk = clean_ids[i : i + batch_size]
            filter_val = "|".join(chunk)
            params = {
                "filter": f"openalex:{filter_val}",
                "per_page": len(chunk),
                "select": (
                    "id,doi,title,abstract_inverted_index,cited_by_count,"
                    "primary_location,type,publication_year,authorships,referenced_works"
                ),
            }
            data = self._request("/works", params=params, timeout=30.0)
            if not data:
                continue
            for item in data.get("results", []):
                cand = self._parse_work_item(item)
                if cand:
                    candidates.append(cand)
        return candidates

    def get_forward_citations(self, work_ids: List[str], limit: int = 50) -> List[PaperCandidate]:
        """
        Retrieves works citing any of the provided seed IDs using 'filter=cites:id1|id2|...'.
        """
        if not work_ids:
            return []

        clean_ids = [w.split("/")[-1].strip() for w in work_ids if w.strip()]
        if not clean_ids:
            return []

        filter_val = "|".join(clean_ids[:50])
        params = {
            "filter": f"cites:{filter_val}",
            "per_page": min(limit, 100),
            "sort": "cited_by_count:desc",
            "select": (
                "id,doi,title,abstract_inverted_index,cited_by_count,"
                "primary_location,type,publication_year,authorships,referenced_works"
            ),
        }
        data = self._request("/works", params=params, timeout=30.0)
        if not data:
            return []

        candidates: List[PaperCandidate] = []
        for item in data.get("results", []):
            cand = self._parse_work_item(item)
            if cand:
                candidates.append(cand)
        return candidates


class CrossrefClient:
    """
    Crossref REST API client.
    Serves as the canonical DOI verification and metadata reconciliation fallback.
    Conforms to CODING_STANDARDS.md (Unified request channel, Polite Pool headers).
    """

    BASE_URL = "https://api.crossref.org"

    def __init__(self, email: Optional[str] = None):
        self.email = email or os.getenv("CROSSREF_MAILTO", "researcher@example.edu")

    def _request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: float = 20.0
    ) -> Optional[Dict[str, Any]]:
        query_params = dict(params or {})
        if self.email and "mailto" not in query_params:
            query_params["mailto"] = self.email

        url = f"{self.BASE_URL}{endpoint}"
        if query_params:
            url = f"{url}?{urllib.parse.urlencode(query_params)}"

        headers = {
            "User-Agent": f"ResearchToolkit/0.1.0 (mailto:{self.email})",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.debug("Crossref resource not found at %s (HTTP 404)", endpoint)
            elif e.code == 429:
                logger.info("Crossref rate limit reached (HTTP 429).")
            else:
                logger.warning("Crossref request to %s failed: %s", endpoint, e)
            return None
        except Exception as e:
            logger.warning("Crossref request to %s failed: %s", endpoint, e)
            return None

    def get_work(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves canonical metadata and deposited references for a given DOI.
        Note: The 'select' parameter is strictly forbidden on /works/{doi} (HTTP 400).
        """
        clean_doi = doi.replace("https://doi.org/", "").strip()
        data = self._request(f"/works/{urllib.parse.quote(clean_doi)}")
        if not data or data.get("status") != "ok":
            return None

        msg = data.get("message") or {}
        title_list = msg.get("title") or []
        title = title_list[0] if title_list else "Untitled"

        container_list = msg.get("container-title") or []
        venue = container_list[0] if container_list else ""

        authors = []
        for a in msg.get("author", []):
            name_parts = [a.get("given"), a.get("family")]
            full_name = " ".join(p for p in name_parts if p)
            if full_name:
                authors.append(full_name)

        created_parts = (msg.get("created") or {}).get("date-parts", [[]])[0]
        year = created_parts[0] if created_parts else None

        refs: List[Dict[str, Any]] = []
        for r in msg.get("reference", []):
            ref_doi = r.get("DOI")
            refs.append({
                "doi": ref_doi,
                "title": r.get("article-title") or r.get("volume-title") or "",
                "year": r.get("year"),
                "unstructured": r.get("unstructured") or "",
            })

        return {
            "doi": msg.get("DOI") or clean_doi,
            "title": title,
            "year": year,
            "authors": authors,
            "venue": venue,
            "citation_count": msg.get("is-referenced-by-count", 0),
            "references": refs,
        }

    def verify_doi(self, doi: str) -> bool:
        """Returns True if the DOI exists and is registered in Crossref."""
        work = self.get_work(doi)
        return work is not None
