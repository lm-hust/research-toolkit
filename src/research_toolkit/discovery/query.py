"""
src/research_toolkit/discovery/query.py
Query parsing and cross-platform translation for Semantic Scholar and OpenAlex.
"""

from __future__ import annotations

import re


class QueryTranslator:
    """Translates user academic boolean queries to platform-specific query formats."""

    @staticmethod
    def to_semantic_scholar(query: str) -> str:
        """
        Translates query for Semantic Scholar /paper/search relevance endpoint.
        S2 does not support boolean operators (AND/OR/NOT) or parentheses.
        Extracts quoted phrases and keywords while stripping boolean keywords and syntax symbols.
        """
        if not query:
            return ""

        # Remove parentheses
        text = re.sub(r"[()]", " ", query)

        # Remove boolean keywords at word boundaries
        text = re.sub(r"\b(AND|OR|NOT)\b", " ", text)

        # Extract tokens while preserving quoted phrases
        tokens = []
        for match in re.finditer(r'("[^"]+"|\S+)', text):
            token = match.group(0).strip()
            # Clean punctuation from unquoted tokens
            if not (token.startswith('"') and token.endswith('"')):
                token = re.sub(r'^[^\w]+|[^\w]+$', '', token)
            if token and token.upper() not in {"AND", "OR", "NOT"}:
                tokens.append(token)

        return " ".join(tokens).strip()

    @staticmethod
    def to_openalex(query: str) -> str:
        """
        Translates query for OpenAlex works search.
        OpenAlex supports phrase quotes and basic text search.
        """
        if not query:
            return ""
        # Clean up stray/unbalanced parentheses
        cleaned = re.sub(r"[()]", " ", query)
        # Collapse multiple spaces
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def to_topic_slug(query: str) -> str:
        """
        Extracts a clean, URL- and folder-friendly topic slug from a complex query expression.
        Strips quotes, boolean operators, and special characters.
        """
        if not query:
            return "literature"

        # Remove quotes, parentheses, special characters
        text = re.sub(r'["\'()]', " ", query)
        # Remove boolean keywords
        text = re.sub(r"\b(AND|OR|NOT)\b", " ", text, flags=re.IGNORECASE)
        # Remove any non-alphanumeric except spaces
        text = re.sub(r"[^\w\s-]", " ", text)
        # Convert to lowercase and split
        words = [w.lower() for w in text.split() if w]
        slug = "-".join(words[:6])  # limit to top 6 terms for clean folder naming
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug or "literature"
