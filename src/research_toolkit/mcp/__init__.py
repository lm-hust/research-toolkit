"""
Model Context Protocol (MCP) server foundation and tool definitions.
"""

from research_toolkit.mcp.server import app, create_app
from research_toolkit.mcp.tools import (
    ask_notebook,
    get_tools_manifest,
    search_literature,
    sync_notebook,
    verify_checkpoint,
)

__all__ = [
    "search_literature",
    "verify_checkpoint",
    "sync_notebook",
    "ask_notebook",
    "get_tools_manifest",
    "create_app",
    "app",
]

