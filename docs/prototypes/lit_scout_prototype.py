"""
docs/prototypes/lit_scout_prototype.py
PROTOTYPE: Throwaway simulation of lit-scout CIMO decomposition and query synthesis.
Used to validate prompt logic, translation hygiene, and CLI parameter formulation.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List

from research_toolkit.discovery.query import QueryTranslator


@dataclass
class CIMOComponents:
    raw_input: str
    context_en: List[str]
    intervention_en: List[str]
    mechanism_en: List[str]
    outcome_en: List[str]
    topic_slug: str

    def build_tier1_query(self) -> str:
        """Mandatory search block: (C) AND (I) for maximal scoping review recall."""
        c_part = " OR ".join(f'"{term}"' if " " in term else term for term in self.context_en)
        i_part = " OR ".join(f'"{term}"' if " " in term else term for term in self.intervention_en)
        return f"({c_part}) AND ({i_part})"

    def build_tier2_query(self) -> str:
        """Refined diagnostic query: (C) AND (I) AND (M)."""
        tier1 = self.build_tier1_query()
        m_part = " OR ".join(f'"{term}"' if " " in term else term for term in self.mechanism_en)
        return f"{tier1} AND ({m_part})"

    def cli_search_command(self, limit: int = 10, dry_run: bool = True) -> str:
        q = self.build_tier1_query()
        flag = " --dry-run" if dry_run else ""
        return f'python -m research_toolkit.cli search "{q}" -k {limit} --topic {self.topic_slug}{flag}'


SAMPLE_CASES = [
    CIMOComponents(
        raw_input="我想了解多智能体协同做软件工程和代码生成，特别是通过辩论或投票达成共识减少错误。",
        context_en=["software engineering", "code generation", "program synthesis"],
        intervention_en=["multi-agent systems", "LLM agents", "collaborative agents"],
        mechanism_en=["multi-agent debate", "consensus mechanism", "peer review"],
        outcome_en=["error reduction", "code correctness", "pass@k"],
        topic_slug="cimo-multi-agent-code-gen",
    ),
    CIMOComponents(
        raw_input="临床医学场景下大模型如何通过参数高效微调（PEFT/LoRA）防止灾难性遗忘？",
        context_en=["clinical NLP", "medical language models", "healthcare informatics"],
        intervention_en=["parameter-efficient fine-tuning", "PEFT", "LoRA", "low-rank adaptation"],
        mechanism_en=["catastrophic forgetting", "weight freezing", "representation stability"],
        outcome_en=["knowledge retention", "diagnostic accuracy"],
        topic_slug="cimo-peft-clinical-nlp",
    ),
    CIMOComponents(
        raw_input="Autonomous driving perception: sensor fusion between lidar and camera for 3D object detection under adverse weather.",
        context_en=["autonomous driving", "adverse weather", "sensor perception"],
        intervention_en=["sensor fusion", "multimodal fusion", "lidar-camera fusion"],
        mechanism_en=["cross-attention", "feature alignment", "spatial projection"],
        outcome_en=["3D object detection", "robustness", "mAP score"],
        topic_slug="cimo-autonomous-driving-fusion",
    ),
]


def run_prototype_verification() -> None:
    print("=" * 80)
    print("🚀 PROTOTYPE RUN: lit-scout CIMO Decomposition & Platform Query Verification")
    print("=" * 80)

    for idx, case in enumerate(SAMPLE_CASES, 1):
        print(f"\n[Case {idx}] Raw Input: '{case.raw_input}'")
        print("  ┌─ CIMO Breakdown (English & Academic Jargon):")
        print(f"  │  • Context (C)     : {case.context_en}")
        print(f"  │  • Intervention (I): {case.intervention_en}")
        print(f"  │  • Mechanism (M)   : {case.mechanism_en}")
        print(f"  │  • Outcome (O)     : {case.outcome_en}")
        print("  ├─ Generated Queries:")
        t1_query = case.build_tier1_query()
        t2_query = case.build_tier2_query()
        print(f"  │  • Tier 1 (C + I, High Recall): {t1_query}")
        print(f"  │  • Tier 2 (C + I + M, Refined): {t2_query}")

        # Test against QueryTranslator
        s2_stream = QueryTranslator.to_semantic_scholar(t1_query)
        oa_stream = QueryTranslator.to_openalex(t1_query)
        target_col = QueryTranslator.to_collection_name(t1_query, case.topic_slug)

        print("  ├─ Target Search Engines Translation (via QueryTranslator):")
        print(f"  │  • Semantic Scholar Stream : {s2_stream}")
        print(f"  │  • OpenAlex Works Search   : {oa_stream}")
        print(f"  │  • Derived Collection Name : {target_col}")

        cli_cmd = case.cli_search_command(limit=10, dry_run=True)
        print("  └─ Executable CLI Ingestion Command:")
        print(f"     $ {cli_cmd}")

    print("\n" + "=" * 80)
    print("✅ All prototype test cases formatted, parsed, and translated successfully.")
    print("=" * 80)


if __name__ == "__main__":
    run_prototype_verification()
