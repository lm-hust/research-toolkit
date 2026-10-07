"""
src/research_toolkit/discovery/query.py
Query parsing and cross-platform translation for Semantic Scholar and OpenAlex.
"""

from __future__ import annotations

import re
from typing import Optional


class QueryTranslator:
    """Translates user academic boolean queries to platform-specific query formats."""

    @staticmethod
    def to_semantic_scholar(query: str) -> str:
        """
        Translates query for Semantic Scholar /paper/search relevance endpoint.
        S2 does not support boolean operators (AND/OR/NOT) or parentheses.
        Extracts quoted phrases and keywords while stripping boolean keywords, negated terms, and syntax symbols.
        """
        if not query:
            return ""

        # Remove negated clauses: NOT "phrase" or NOT term
        text = re.sub(r'\bNOT\s+("[^"]+"|\S+)', ' ', query, flags=re.IGNORECASE)

        # Remove parentheses
        text = re.sub(r"[()]", " ", text)

        # Remove remaining boolean operators (AND, OR)
        text = re.sub(r"\b(AND|OR)\b", " ", text, flags=re.IGNORECASE)

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
    def to_openalex(query: str, max_phrases: int = 4) -> str:
        """
        Translates query for OpenAlex works search.
        OpenAlex supports phrase quotes and space-separated term search.
        Removes negation and boolean connector keywords to prevent literal matching.
        Limits quoted phrases to prevent over-constraining the search space.
        """
        if not query:
            return ""

        # Remove negated clauses: NOT "phrase" or NOT term
        text = re.sub(r'\bNOT\s+("[^"]+"|\S+)', ' ', query, flags=re.IGNORECASE)

        # Clean up stray/unbalanced parentheses
        text = re.sub(r"[()]", " ", text)

        # Remove boolean connectors
        text = re.sub(r"\b(AND|OR)\b", " ", text, flags=re.IGNORECASE)

        # Extract tokens and unquote phrases beyond max_phrases budget
        tokens = []
        quoted_count = 0
        for match in re.finditer(r'("[^"]+"|\S+)', text):
            token = match.group(0).strip()
            if token.startswith('"') and token.endswith('"'):
                quoted_count += 1
                if quoted_count <= max_phrases:
                    tokens.append(token)
                else:
                    inner = token[1:-1].strip()
                    if inner:
                        tokens.append(inner)
            else:
                tokens.append(token)

        return " ".join(tokens).strip()

    @staticmethod
    def to_topic_slug(query: str) -> str:
        """
        Extracts a clean, URL- and collection-friendly topic slug from a complex query expression.
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
        slug = "-".join(words[:6])  # limit to top 6 terms for clean ZoteroCollection naming
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug or "literature"

    @classmethod
    def to_collection_name(cls, query: str, topic: Optional[str] = None) -> str:
        """
        Derives the canonical ZoteroCollection name prefixed with research/.
        Uses explicit topic if provided, otherwise derives slug from query.
        """
        if topic:
            clean = topic.strip().lower().replace(" ", "-")
        else:
            clean = cls.to_topic_slug(query)
        return clean if clean.startswith("research/") else f"research/{clean}"
