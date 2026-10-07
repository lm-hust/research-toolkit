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


def test_query_translator_negation():
    translator = QueryTranslator()
    raw_query = 'robotics NOT simulation'
    s2 = translator.to_semantic_scholar(raw_query)
    oa = translator.to_openalex(raw_query)

    assert "robotics" in s2
    assert "simulation" not in s2
    assert "NOT" not in s2

    assert "robotics" in oa
    assert "simulation" not in oa
    assert "NOT" not in oa


def test_query_translator_to_collection_name():
    translator = QueryTranslator()
    # Explicit topic
    assert translator.to_collection_name("query", topic="custom-name") == "research/custom-name"
    assert translator.to_collection_name("query", topic="research/custom-name") == "research/custom-name"

    # From query slug
    col_name = translator.to_collection_name('("Deep Learning" OR AI) AND robotics')
    assert col_name.startswith("research/")
    assert "(" not in col_name
    assert '"' not in col_name


def test_query_translator_to_openalex_phrase_budget():
    """Ensures queries with more quoted phrases than budget are unquoted beyond the limit."""
    query = '("phrase one" OR "phrase two") AND ("phrase three" OR "phrase four" OR "phrase five")'
    oa = QueryTranslator.to_openalex(query, max_phrases=3)
    # The first 3 should retain quotes
    assert '"phrase one"' in oa
    assert '"phrase two"' in oa
    assert '"phrase three"' in oa
    # Phrases beyond 3 should be unquoted to keep search broad
    assert '"phrase four"' not in oa
    assert "phrase four" in oa
    assert '"phrase five"' not in oa
    assert "phrase five" in oa
