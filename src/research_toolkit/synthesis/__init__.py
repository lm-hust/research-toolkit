"""
Synthesis package for NotebookLM Gateway and DistilledEvidence.
"""

from research_toolkit.synthesis.adapters import (
    NotebookLMPyAdapter,
    get_default_gateway,
)
from research_toolkit.synthesis.gateway import NotebookLMGateway
from research_toolkit.synthesis.models import (
    DistilledEvidence,
    GroundedAnswer,
    NotebookInfo,
    NotebookSource,
)

__all__ = [
    "NotebookLMGateway",
    "NotebookLMPyAdapter",
    "get_default_gateway",
    "NotebookInfo",
    "NotebookSource",
    "DistilledEvidence",
    "GroundedAnswer",
]
