"""
tests/test_curation.py
Tests for interactive CurationCheckpoint terminal boundary.
Conforms to CONTEXT.md and ADR-0005.
"""

import unittest
from unittest.mock import patch

from research_toolkit.discovery.curation import CurationCheckpoint
from research_toolkit.discovery.models import PaperCandidate


class TestCurationCheckpoint(unittest.TestCase):
    def setUp(self):
        self.p1 = PaperCandidate(
            paper_id="p1",
            title="Foundational Attention Paper",
            year=2017,
            citation_count=50000,
            co_citation_count=4,
            topological_role="foundational",
            composite_score=0.95,
            doi="10.1000/1",
        )
        self.p2 = PaperCandidate(
            paper_id="p2",
            title="2025 SOTA Survey",
            year=2025,
            citation_count=100,
            co_citation_count=3,
            topological_role="recent_advancement",
            is_review=True,
            composite_score=0.88,
            doi="10.1000/2",
        )
        self.p3 = PaperCandidate(
            paper_id="p3",
            title="Marginal Seed Paper",
            year=2023,
            citation_count=10,
            co_citation_count=0,
            topological_role="seed",
            composite_score=0.45,
            doi="10.1000/3",
        )
        self.candidates = [self.p1, self.p2, self.p3]

    def test_curation_checkpoint_auto_confirm(self):
        """When auto_confirm is True, returns all candidates without blocking."""
        checkpoint = CurationCheckpoint()
        selected = checkpoint.review(self.candidates, auto_confirm=True)
        self.assertEqual(len(selected), 3)

    def test_curation_checkpoint_toggle_and_confirm(self):
        """Simulates user toggling off paper #3 and pressing Enter to confirm."""
        checkpoint = CurationCheckpoint()
        # Input '3' to toggle off paper 3, then '' to confirm
        user_inputs = iter(["3", ""])
        with patch("builtins.input", side_effect=lambda _: next(user_inputs)):
            selected = checkpoint.review(self.candidates, auto_confirm=False, interactive=True)

        self.assertEqual(len(selected), 2)
        self.assertIn(self.p1, selected)
        self.assertIn(self.p2, selected)
        self.assertNotIn(self.p3, selected)

    def test_curation_checkpoint_abort(self):
        """Typing 'q' aborts and returns an empty list."""
        checkpoint = CurationCheckpoint()
        with patch("builtins.input", return_value="q"):
            selected = checkpoint.review(self.candidates, auto_confirm=False, interactive=True)
        self.assertEqual(len(selected), 0)

    def test_curation_format_table(self):
        """Formats the curation table displaying topological roles and statuses."""
        checkpoint = CurationCheckpoint()
        table_str = checkpoint.render_table(self.candidates, selected_indices={0, 1})
        self.assertIn("Foundational Attention Paper", table_str)
        self.assertIn("[FOUNDATIONAL]", table_str)
        self.assertIn("[SOTA/ADV]", table_str)
        self.assertIn("[X]", table_str)  # selected
        self.assertIn("[ ]", table_str)  # unselected
