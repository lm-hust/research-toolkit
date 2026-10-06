"""
tests/test_query_translator.py
Tests for query translation and topic slug generation across search platforms.
"""

from research_toolkit.discovery.query import QueryTranslator


def test_query_translator_to_semantic_scholar():
    translator = QueryTranslator()
    raw_query = '("artificial intelligence" OR "machine learning") AND robotics'
    # S2 relevance search does not support AND/OR/parentheses.
    # It should extract quoted phrases and terms, stripping boolean operators.
    s2_query = translator.to_semantic_scholar(raw_query)
    assert "AND" not in s2_query
    assert "OR" not in s2_query
    assert "(" not in s2_query
    assert ")" not in s2_query
    assert '"artificial intelligence"' in s2_query or "artificial intelligence" in s2_query
    assert "robotics" in s2_query


def test_query_translator_to_openalex():
    translator = QueryTranslator()
    raw_query = '("artificial intelligence" OR "machine learning") AND robotics'
    # OpenAlex search parameter supports phrases with quotes and standard text.
    oa_query = translator.to_openalex(raw_query)
    assert "artificial intelligence" in oa_query
    assert "robotics" in oa_query


def test_query_translator_to_topic_slug():
    translator = QueryTranslator()
    raw_query = '("artificial intelligence" OR AI) AND robotics'
    slug = translator.to_topic_slug(raw_query)
    # Generates a filesystem and collection friendly slug
    assert "(" not in slug
    assert ")" not in slug
    assert '"' not in slug
    assert "artificial-intelligence" in slug or "artificial" in slug
    assert "robotics" in slug
    assert not slug.startswith("-")
    assert not slug.endswith("-")
