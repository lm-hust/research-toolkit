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
        import tempfile
        from pathlib import Path
        import json

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


if __name__ == "__main__":
    unittest.main()
