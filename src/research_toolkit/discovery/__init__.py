"""
Literature discovery module for multi-source retrieval, deduplication, and ranking.
"""

from research_toolkit.discovery.clients import OpenAlexClient, SemanticScholarClient
from research_toolkit.discovery.dedup import Deduplicator
from research_toolkit.discovery.models import (
    PaperCandidate,
    PaperCandidateBatch,
    clean_doi,
    compute_paper_id,
)
from research_toolkit.discovery.ranker import Ranker
from research_toolkit.discovery.service import DiscoveryService
from research_toolkit.discovery.venue_registry import VenueRegistry

__all__ = [
    "PaperCandidate",
    "PaperCandidateBatch",
    "clean_doi",
    "compute_paper_id",
    "SemanticScholarClient",
    "OpenAlexClient",
    "Deduplicator",
    "Ranker",
    "DiscoveryService",
    "VenueRegistry",
]

