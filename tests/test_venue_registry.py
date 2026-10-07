"""
tests/test_venue_registry.py
Unit tests for VenueRegistry offline lookup and Ranker integration.
"""

import unittest

from research_toolkit.discovery.models import PaperCandidate
from research_toolkit.discovery.ranker import Ranker
from research_toolkit.discovery.venue_registry import VenueRegistry


class TestVenueRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = VenueRegistry()

    def test_lookup_top_journals(self):
        """Resolves Nature and TPAMI to high impact factor scores."""
        nature_if = self.registry.get_impact("Nature")
        self.assertGreaterEqual(nature_if, 40.0)

        tpami_if = self.registry.get_impact("IEEE Transactions on Pattern Analysis and Machine Intelligence")
        self.assertGreaterEqual(tpami_if, 20.0)

        tpami_alias = self.registry.get_impact("IEEE TPAMI")
        self.assertGreaterEqual(tpami_alias, 20.0)

    def test_lookup_top_conferences_fuzzy(self):
        """Resolves CVPR and NeurIPS even with conference prefixes or years."""
        # Exact acronym
        self.assertGreaterEqual(self.registry.get_impact("CVPR"), 20.0)
        self.assertGreaterEqual(self.registry.get_impact("NeurIPS"), 20.0)
        self.assertGreaterEqual(self.registry.get_impact("ICLR"), 20.0)

        # Full title with year and organization prefix
        fuzzy_cvpr = "2024 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)"
        self.assertGreaterEqual(self.registry.get_impact(fuzzy_cvpr), 20.0)

        fuzzy_nips = "Advances in Neural Information Processing Systems 36 (NeurIPS 2023)"
        self.assertGreaterEqual(self.registry.get_impact(fuzzy_nips), 20.0)

    def test_lookup_unknown_venue(self):
        """Returns 0.0 for unknown or empty venue."""
        self.assertEqual(self.registry.get_impact("Unknown Preprint Archive"), 0.0)
        self.assertEqual(self.registry.get_impact(""), 0.0)

    def test_ranker_integrates_venue_registry(self):
        """Ranker boosts papers published in top conferences even if OpenAlex dynamic impact was 0.0."""
        ranker = Ranker(venue_registry=self.registry)

        paper_cvpr = PaperCandidate(
            paper_id="p_cvpr",
            title="Deep Residual Learning for Image Recognition",
            year=2024,
            citation_count=100,
            venue="IEEE/CVF Conference on Computer Vision and Pattern Recognition",
            venue_impact=0.0,  # Missing dynamic metric
        )

        paper_unindexed = PaperCandidate(
            paper_id="p_unknown",
            title="Deep Learning Notes",
            year=2024,
            citation_count=100,
            venue="Unknown Workshop",
            venue_impact=0.0,
        )

        score_cvpr = ranker.score(paper_cvpr)
        score_unindexed = ranker.score(paper_unindexed)

        # CVPR paper must score significantly higher due to venue impact boost
        self.assertGreater(score_cvpr, score_unindexed)
        self.assertGreater(score_cvpr, 0.45)


    def test_expanded_venues_lookup(self):
        """Resolves premier venues from expanded CCF/JCR lists like ICML, ACL, and ACM CSUR."""
        self.assertGreaterEqual(self.registry.get_impact("ICML"), 18.0)
        self.assertGreaterEqual(self.registry.get_impact("ACL"), 15.0)
        self.assertGreaterEqual(self.registry.get_impact("ACM Computing Surveys"), 15.0)

    def test_dynamic_cache_lookup(self):
        """When not in offline registry, checks local cache for source_id."""
        import json
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            cache_data = {
                "https://openalex.org/S4306401280": {
                    "impact": 7.8,
                    "name": "Journal of Green Computing",
                    "timestamp": 2000000000
                }
            }
            tf.write(json.dumps(cache_data).encode("utf-8"))
            tf_path = Path(tf.name)

        registry_with_cache = VenueRegistry(cache_path=tf_path)
        impact = registry_with_cache.get_impact("Unknown Venue", source_id="https://openalex.org/S4306401280")
        self.assertEqual(impact, 7.8)
        tf_path.unlink(missing_ok=True)

    def test_venue_registry_delegates_to_openalex_client(self):
        """When source_id is uncached, VenueRegistry delegates to OpenAlexClient and caches result."""
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.get_source_impact.return_value = 8.4

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            tf_path = Path(tf.name)

        registry = VenueRegistry(cache_path=tf_path, openalex_client=mock_client)
        impact = registry.get_impact("Unindexed Venue", source_id="https://openalex.org/S99999")

        self.assertEqual(impact, 8.4)
        mock_client.get_source_impact.assert_called_once_with("S99999")
        # Verify cached
        self.assertIn("https://openalex.org/S99999", registry._cache)
        tf_path.unlink(missing_ok=True)

    def test_energy_venues_lookup(self):
        """Resolves sustainable energy journals relevant to energy intelligence domains."""
        self.assertGreaterEqual(self.registry.get_impact("Nature Energy"), 40.0)
        self.assertGreaterEqual(self.registry.get_impact("IEEE Transactions on Smart Grid"), 9.0)
        self.assertGreaterEqual(self.registry.get_impact("Applied Energy"), 10.0)

    def test_paper_candidate_is_preprint(self):
        """Validates is_preprint logic across venues, IDs, and manual overrides."""
        p_arxiv_nodoi = PaperCandidate(paper_id="1", title="A", arxiv_id="2301.0001", doi=None)
        self.assertTrue(p_arxiv_nodoi.is_preprint)

        p_arxiv_withdoi = PaperCandidate(paper_id="2", title="B", arxiv_id="2301.0001", doi="10.1000/123", venue="IEEE Trans")
        self.assertFalse(p_arxiv_withdoi.is_preprint)

        p_biorxiv = PaperCandidate(paper_id="3", title="C", venue="bioRxiv")
        self.assertTrue(p_biorxiv.is_preprint)

        p_peer = PaperCandidate(paper_id="4", title="D", venue="Nature", doi="10.1038/nature1")
        self.assertFalse(p_peer.is_preprint)

        # Explicit override
        p_peer.is_preprint = True
        self.assertTrue(p_peer.is_preprint)


if __name__ == "__main__":
    unittest.main()
