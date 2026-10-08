"""
tests/test_snowballer.py
Tests for CitationSnowballer graph expansion engine.
Conforms to CONTEXT.md, ADR-0005, and Ticket #43.
"""

import unittest
from unittest.mock import MagicMock

from research_toolkit.discovery.models import (
    CitationEdge,
    PaperCandidate,
    PaperCandidateBatch,
    SelectionResult,
    SnowballResult,
)
from research_toolkit.discovery.snowballer import (
    CitationSnowballer,
    adapt_seeds,
    load_seeds_from_collection,
)


class TestCitationSnowballer(unittest.TestCase):
    def setUp(self):
        self.mock_oa = MagicMock()
        self.mock_crossref = MagicMock()
        self.snowballer = CitationSnowballer(
            oa_client=self.mock_oa,
            crossref_client=self.mock_crossref,
        )

    def test_citation_edge_model_and_serialization(self):
        """Verifies CitationEdge model structure and roundtrip serialization."""
        edge = CitationEdge(
            source_id="doi:10.1000/seed1",
            target_id="https://openalex.org/W_found1",
            direction="referenced_by",
        )
        edge_dict = edge.to_dict()
        self.assertEqual(edge_dict["source_id"], "doi:10.1000/seed1")
        self.assertEqual(edge_dict["target_id"], "https://openalex.org/W_found1")
        self.assertEqual(edge_dict["direction"], "referenced_by")

        edge_json = edge.to_json()
        reconstructed = CitationEdge.from_json(edge_json)
        self.assertEqual(reconstructed.source_id, edge.source_id)
        self.assertEqual(reconstructed.target_id, edge.target_id)
        self.assertEqual(reconstructed.direction, edge.direction)

    def test_snowball_result_model_and_partitioning(self):
        """Verifies SnowballResult clearly partitions seeds from newly discovered candidates."""
        seed = PaperCandidate(
            paper_id="doi:10.1000/s1",
            title="Seed Paper",
            doi="10.1000/s1",
            topological_role="seed",
        )
        foundational = PaperCandidate(
            paper_id="https://openalex.org/W_found1",
            title="Foundational Paper",
            topological_role="foundational",
            co_citation_count=2,
        )
        frontier = PaperCandidate(
            paper_id="https://openalex.org/W_fwd1",
            title="Frontier Paper",
            topological_role="recent_advancement",
            co_citation_count=1,
        )
        edge = CitationEdge(
            source_id="doi:10.1000/s1",
            target_id="https://openalex.org/W_found1",
            direction="referenced_by",
        )

        res = SnowballResult(
            seeds=[seed],
            discovered_candidates=[foundational, frontier],
            citation_edges=[edge],
            direction="both",
            status="completed",
            discovery_path={"https://openalex.org/W_found1": "foundational"},
        )

        # Seed partition check
        self.assertEqual(res.seed_paper_ids, ["doi:10.1000/s1"])
        self.assertEqual(len(res.seeds), 1)
        self.assertEqual(len(res.discovered_candidates), 2)
        self.assertNotIn(seed, res.discovered_candidates)
        self.assertEqual(res.discovery_path["https://openalex.org/W_found1"], "foundational")

        # Backward compatibility properties
        self.assertEqual(len(res.all_candidates), 3)
        self.assertEqual(len(res.foundational), 1)
        self.assertEqual(len(res.recent_advancements), 1)

        # Serialization roundtrip
        res_json = res.to_json()
        reconstructed = SnowballResult.from_json(res_json)
        self.assertEqual(reconstructed.seed_paper_ids, res.seed_paper_ids)
        self.assertEqual(len(reconstructed.seeds), 1)
        self.assertEqual(len(reconstructed.discovered_candidates), 2)
        self.assertEqual(len(reconstructed.citation_edges), 1)
        self.assertEqual(reconstructed.citation_edges[0].direction, "referenced_by")
        self.assertEqual(reconstructed.discovery_path["https://openalex.org/W_found1"], "foundational")

    def test_seed_adapters(self):
        """Verifies seed ingestion across SelectionResult, PaperCandidateBatch, explicit IDs, and Zotero."""
        c1 = PaperCandidate(paper_id="doi:10.1000/1", title="Paper 1", doi="10.1000/1")
        c2 = PaperCandidate(paper_id="doi:10.1000/2", title="Paper 2", doi="10.1000/2")

        # 1. From SelectionResult
        sel = SelectionResult(selected_papers=[c1, c2])
        adapted_sel = adapt_seeds(sel)
        self.assertEqual(len(adapted_sel), 2)
        self.assertEqual(adapted_sel[0].paper_id, "doi:10.1000/1")

        # 2. From PaperCandidateBatch
        batch = PaperCandidateBatch(papers=[c1, c2])
        adapted_batch = adapt_seeds(batch)
        self.assertEqual(len(adapted_batch), 2)

        # 3. From explicit DOI / ID list
        explicit_ids = ["10.1000/1", "https://openalex.org/W12345", "arxiv:2301.00001"]
        adapted_ids = adapt_seeds(explicit_ids)
        self.assertEqual(len(adapted_ids), 3)
        self.assertEqual(adapted_ids[0].doi, "10.1000/1")
        self.assertEqual(adapted_ids[1].paper_id, "https://openalex.org/W12345")
        self.assertEqual(adapted_ids[2].arxiv_id, "2301.00001")

        # 4. From comma-separated string
        adapted_str = adapt_seeds("10.1000/1, 10.1000/2")
        self.assertEqual(len(adapted_str), 2)

        # 5. From mock Zotero collection
        mock_zotero = MagicMock()
        mock_zotero.get_collection_candidates.return_value = [c1, c2]
        adapted_col = load_seeds_from_collection("my-collection", zotero_manager=mock_zotero)
        self.assertEqual(len(adapted_col), 2)
        mock_zotero.get_collection_candidates.assert_called_once_with("my-collection")

    def test_snowball_backward_and_forward_co_citation(self):
        """Verifies backward co-citation extraction and forward citation coupling."""
        seed1 = PaperCandidate(
            paper_id="https://openalex.org/W_seed1",
            title="Seed Paper 1",
            year=2022,
            doi="10.1000/seed1",
            referenced_works=[
                "https://openalex.org/W_found1",
                "https://openalex.org/W_found2",
                "https://openalex.org/W_other",
            ],
        )
        seed2 = PaperCandidate(
            paper_id="https://openalex.org/W_seed2",
            title="Seed Paper 2",
            year=2023,
            doi="10.1000/seed2",
            referenced_works=[
                "https://openalex.org/W_found1",  # Co-cited by both seeds!
                "https://openalex.org/W_found2",  # Co-cited by both seeds!
            ],
        )

        found1 = PaperCandidate(
            paper_id="https://openalex.org/W_found1",
            title="Foundational Attention Paper",
            year=2017,
            doi="10.1000/found1",
            citation_count=50000,
        )
        found2 = PaperCandidate(
            paper_id="https://openalex.org/W_found2",
            title="Foundational Transformer Paper",
            year=2018,
            doi="10.1000/found2",
            citation_count=30000,
        )
        self.mock_oa.get_works_by_ids.return_value = [found1, found2]

        forward_survey = PaperCandidate(
            paper_id="https://openalex.org/W_fwd1",
            title="2025 SOTA Survey on Transformers",
            year=2025,
            doi="10.1000/fwd1",
            is_review=True,
            referenced_works=[
                "https://openalex.org/W_seed1",
                "https://openalex.org/W_seed2",
            ],
        )
        self.mock_oa.get_forward_citations.return_value = [forward_survey]

        result = self.snowballer.snowball(
            seeds=[seed1, seed2],
            min_co_citations=2,
            max_backward=10,
            max_forward=10,
            direction="both",
        )

        self.assertIsInstance(result, SnowballResult)
        self.assertEqual(len(result.seeds), 2)
        self.assertEqual(len(result.discovered_candidates), 3)  # 2 foundational + 1 fwd
        self.assertEqual(len(result.foundational), 2)
        self.assertEqual(len(result.recent_advancements), 1)

        # Check foundational attributes & edges
        f1 = next(c for c in result.foundational if c.doi == "10.1000/found1")
        self.assertEqual(f1.topological_role, "foundational")
        self.assertEqual(f1.co_citation_count, 2)

        # Check recent advancement attributes
        fwd = result.recent_advancements[0]
        self.assertEqual(fwd.topological_role, "recent_advancement")
        self.assertEqual(fwd.co_citation_count, 2)

        # Check citation edges
        edges = result.citation_edges
        self.assertTrue(len(edges) >= 3)
        # Seeds referenced foundational papers
        found_edges = [e for e in edges if e.direction == "referenced_by"]
        self.assertTrue(any(e.target_id in ("doi:10.1000/found1", "https://openalex.org/W_found1") for e in found_edges))
        # Recent advancement cites seeds
        fwd_edges = [e for e in edges if e.direction == "cites"]
        self.assertTrue(any(e.target_id in ("doi:10.1000/fwd1", "https://openalex.org/W_fwd1") for e in fwd_edges))

        # Check that fake 0.85 relevance_score was NOT injected
        self.assertEqual(f1.relevance_score, 0.0)
        self.assertEqual(fwd.relevance_score, 0.0)

        # Check discovery_path populated
        self.assertEqual(result.discovery_path[f1.paper_id], "foundational")
        self.assertEqual(result.discovery_path[fwd.paper_id], "recent_advancement")

    def test_elimination_of_legacy_cutoff_retains_single_seed_forward_citation(self):
        """
        Verifies that candidates citing only 1 seed (without being a review paper)
        are retained in forward expansion within budget caps (Ticket #43 heuristic fix).
        """
        seed = PaperCandidate(
            paper_id="https://openalex.org/W_seed1",
            title="Seed Paper 1",
            year=2023,
            doi="10.1000/seed1",
        )

        # Single-seed citing candidate, NOT a review paper
        single_citing_candidate = PaperCandidate(
            paper_id="https://openalex.org/W_single_cite",
            title="Regular Research Paper Citing Seed 1",
            year=2024,
            doi="10.1000/single_cite",
            is_review=False,
            referenced_works=["https://openalex.org/W_seed1"],
        )
        self.mock_oa.get_forward_citations.return_value = [single_citing_candidate]

        result = self.snowballer.snowball(
            seeds=[seed],
            direction="forward",
            max_forward=10,
        )

        # In legacy logic, coupling < 2 and is_review=False would be discarded.
        # In Ticket #43, it MUST be retained!
        self.assertEqual(len(result.discovered_candidates), 1)
        self.assertEqual(len(result.recent_advancements), 1)
        cand = result.recent_advancements[0]
        self.assertEqual(cand.doi, "10.1000/single_cite")
        self.assertEqual(cand.co_citation_count, 1)
        self.assertEqual(cand.topological_role, "recent_advancement")

        # Edge is recorded
        self.assertEqual(len(result.citation_edges), 1)
        self.assertEqual(result.citation_edges[0].direction, "cites")
        self.assertEqual(result.citation_edges[0].target_id, cand.paper_id)

    def test_direction_controls(self):
        """Verifies direction filtering: forward-only, backward-only, both."""
        seed = PaperCandidate(
            paper_id="https://openalex.org/W_seed",
            title="Seed",
            referenced_works=["https://openalex.org/W_back"],
        )
        back_cand = PaperCandidate(
            paper_id="https://openalex.org/W_back",
            title="Backward Paper",
        )
        fwd_cand = PaperCandidate(
            paper_id="https://openalex.org/W_fwd",
            title="Forward Paper",
            referenced_works=["https://openalex.org/W_seed"],
        )
        self.mock_oa.get_works_by_ids.return_value = [back_cand]
        self.mock_oa.get_forward_citations.return_value = [fwd_cand]

        # 1. Direction = forward only
        res_fwd = self.snowballer.snowball(seeds=[seed], direction="forward")
        self.assertEqual(len(res_fwd.foundational), 0)
        self.assertEqual(len(res_fwd.recent_advancements), 1)
        self.assertEqual(res_fwd.direction, "forward")
        self.mock_oa.get_works_by_ids.assert_not_called()

        # 2. Direction = backward only
        res_back = self.snowballer.snowball(seeds=[seed], direction="backward")
        self.assertEqual(len(res_back.foundational), 1)
        self.assertEqual(len(res_back.recent_advancements), 0)
        self.assertEqual(res_back.direction, "backward")

    def test_budget_caps_enforcement(self):
        """Verifies max_backward and max_forward budget caps."""
        seed = PaperCandidate(
            paper_id="https://openalex.org/W_seed",
            title="Seed",
            referenced_works=[f"https://openalex.org/W_back_{i}" for i in range(10)],
        )
        self.mock_oa.get_works_by_ids.side_effect = lambda ids: [
            PaperCandidate(paper_id=w_id, title=f"Title {w_id}") for w_id in ids
        ]
        self.mock_oa.get_forward_citations.return_value = [
            PaperCandidate(
                paper_id=f"https://openalex.org/W_fwd_{i}",
                title=f"Fwd {i}",
                referenced_works=["https://openalex.org/W_seed"],
            )
            for i in range(10)
        ]

        result = self.snowballer.snowball(
            seeds=[seed],
            direction="both",
            max_backward=3,
            max_forward=4,
        )

        self.assertLessEqual(len(result.foundational), 3)
        self.assertLessEqual(len(result.recent_advancements), 4)

    def test_graceful_degradation_on_partial_source_failure(self):
        """Verifies graceful handling of API exceptions without crashing the batch."""
        seed = PaperCandidate(
            paper_id="https://openalex.org/W_seed",
            title="Seed",
            referenced_works=["https://openalex.org/W_back"],
        )
        back_cand = PaperCandidate(
            paper_id="https://openalex.org/W_back",
            title="Backward Paper",
        )
        self.mock_oa.get_works_by_ids.return_value = [back_cand]
        # OpenAlex forward citation API raises an exception
        self.mock_oa.get_forward_citations.side_effect = RuntimeError("OpenAlex timeout")

        result = self.snowballer.snowball(seeds=[seed], direction="both")

        # Snowballing completes with partial failure status, preserving backward candidates
        self.assertEqual(result.status, "partial_failure")
        self.assertEqual(len(result.foundational), 1)
        self.assertEqual(len(result.recent_advancements), 0)

    def test_snowball_empty_seeds(self):
        """Empty seed list returns empty result safely."""
        result = self.snowballer.snowball([])
        self.assertEqual(len(result.all_candidates), 0)
        self.assertEqual(result.status, "completed")
