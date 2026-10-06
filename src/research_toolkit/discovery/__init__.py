"""
Literature discovery module for multi-source retrieval, deduplication, and ranking.
"""

from research_toolkit.discovery.clients import OpenAlexClient, SemanticScholarClient
from research_toolkit.discovery.dedup import Deduplicator
from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.ranker import Ranker
from research_toolkit.discovery.service import DiscoveryService

__all__ = [
    "PaperCandidate",
    "SemanticScholarClient",
    "OpenAlexClient",
    "Deduplicator",
    "Ranker",
    "DiscoveryService",
]
