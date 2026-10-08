---
name: lit-scout
description: Ingest arbitrary text, files, keywords, or existing Zotero collections; deconstruct into the CIMO academic scoping review framework; expand synonyms and jargon; synthesize dual-tier queries for Semantic Scholar & OpenAlex; execute bidirectional citation snowballing and topological ranking; and orchestrate discovery via modular atomic CLI commands (search, rank, snowball, export) or composite scout.
---

# Lit-Scout (文献小侦察兵)

`lit-scout` is a research exploration and literature intelligence skill. Given informal text, a draft file, raw keywords, multi-turn dialogues, or an existing Zotero seed collection, `lit-scout`:
1. Translates non-English terminology into standardized English academic vocabulary.
2. Structures concepts using the **CIMO** (Context, Intervention, Mechanisms, Outcomes) academic scoping review framework.
3. Compiles dual-tier search queries optimized for **Semantic Scholar** and **OpenAlex**.
4. Discovers core foundational and frontier literature via 1-hop bidirectional **citation snowballing** (co-citation & bibliographic coupling).
5. Maps user requirements to multimodal ranking filters (`--sort`, `--min-cites`, `--peer-reviewed`, `--year`, `--direction`).
6. Executes either the **preferred multi-stage agentic workflow** using decoupled atomic commands (`search` -> LLM assessment -> `rank` -> `snowball` -> `rank` -> `export`) or the unified **one-shot composite path** (`scout`).

---

## 1. Theoretical Grounding & Design Principles

Based on systematic scoping review methodologies (Tricco et al. 2011; PRISMA-S; PRESS Guidelines) and bibliometric network analysis:

1. **CIMO Framework for Computational Research**:
   - **Context ($C$)**: The environment, domain, population, operational constraints, or dataset type.
   - **Intervention ($I$)**: The core technique, computational artifact, algorithm, architecture, or policy intervention.
   - **Mechanisms ($M$)**: The internal causal pathways, dynamics, cognitive/algorithmic processes through which the intervention operates.
   - **Outcomes ($O$)**: The measurable qualitative or quantitative effects, metrics, performance gains, or trade-offs.

2. **Decoupled Search vs. Screening (Maximal Recall)**:
   - In publication titles and abstracts, authors consistently report $C$ and $I$. Conversely, $M$ and $O$ are frequently latent, expressed via specialized jargon, or detailed only in empirical tables.
   - **Mandatory Search Block**: $(C) \land (I)$. Hard-filtering on $M$ or $O$ in electronic database queries creates severe false negatives.
   - **Screening Block**: $M$ and $O$ are retained as explicit eligibility criteria for title/abstract screening and terminal curation.

3. **Dual-Tier Query Strategy**:
   - **Tier 1 (High-Recall Scoping Query)**: $(C_1 \lor C_2 \lor \dots) \land (I_1 \lor I_2 \lor \dots)$. Fed directly into automated CLI ingestion.
   - **Tier 2 (Refined Diagnostic Query)**: $(C_1 \lor C_2) \land (I_1 \lor I_2) \land (M_1 \lor M_2)$. Displayed to the user for precision auditing and diagnostic searches.

4. **Bidirectional Citation Snowballing & Topological Saturation (ADR-0005)**:
   - **Backward Snowballing (Co-Citation)**: Candidates cited by multiple seed papers are categorized as `[Foundational]` papers. Co-citation count indicates consensus importance in the seed domain.
   - **Forward Snowballing (Bibliographic Coupling)**: Recent candidates that cite multiple seed papers are categorized as `[Recent Advancement]`.
   - **Logarithmic Topological Scoring**: $s_{\text{topo}} = \min\left(1.0, \frac{\ln(1 + \text{co\_citation\_count})}{\ln(1 + \text{topo\_cap})}\right)$ integrates citation density without drowning out highly relevant papers.

5. **Human-in-the-Loop (HITL) Curation Checkpoint**:
   - High-yield discovery generates large candidate sets. The interactive curation checkpoint allows terminal multi-selection to reject out-of-scope papers before writing items to Zotero, preserving personal library hygiene.

6. **Platform-Specific Syntax Hygiene**:
   - Wrap compound academic phrases in double quotes (`"multi-agent systems"`).
   - Avoid wildcards (`*`, `?`) due to API limitations; explicitly enumerate plural and morphological variants.
   - Provide 2–4 high-impact quoted phrases per concept block to avoid token dilution in Semantic Scholar and OpenAlex.

---

## 2. Execution Pathways

Depending on the task requirements and execution style, `lit-scout` provides two distinct paths:

### Pathway 1: Preferred Multi-Stage Agentic Workflow (Atomic Decomposition)

This is the **preferred path for autonomous coding/research agents**. It splits the discovery pipeline into decoupled atomic CLI steps with file-first persistence and LLM screening:

- **Step 1: Pure Literature Retrieval Atom (`search`)**
  Search across Semantic Scholar and OpenAlex, saving the raw candidates into `.research/batches/<batch_id>.json`.
  ```bash
  uv run python -m research_toolkit.cli search "<Tier 1 Query>" -k 20 --topic <slug> [--min-cites <N>] [-y <year>] [--peer-reviewed]
  ```
- **Step 2: Abstract Reading & Structured Assessment Record Generation**
  The agent inspects candidate abstracts from the batch file, assesses relevance against CIMO ($C \land I \land M \land O$), and emits a structured `assessments.jsonl` file:
  ```json
  {"paper_id": "doi:10.1000/1", "decision": "related", "relevance_score": 0.95, "cimo_match": {"c": true, "i": true, "m": true, "o": true}, "reason": "Directly tackles multi-agent debate..."}
  {"paper_id": "doi:10.1000/2", "decision": "unrelated", "relevance_score": 0.0, "cimo_match": {"c": true, "i": false, "m": false, "o": false}, "reason": "Focuses on single-agent RL without debate"}
  ```
- **Step 3: Initial Composite & MMR Ranking (`rank`)**
  Rank assessed candidates using composite scoring and MMR diversity selection to determine top seeds:
  ```bash
  uv run python -m research_toolkit.cli rank --batch <batch_id> --assessments assessments.jsonl -n 5
  ```
- **Step 4: Citation Snowballing (`snowball`)**
  Expand 1-hop bidirectional citation networks from the ranked seeds:
  ```bash
  uv run python -m research_toolkit.cli snowball --batch <batch_id> --direction both --max-backward 20 --max-forward 20
  ```
- **Step 5: Re-Ranking with Topological Expansion (`rank`)**
  Re-rank the combined pool of seeds and newly discovered foundational/frontier candidates:
  ```bash
  uv run python -m research_toolkit.cli rank --batch <snowball_batch_id> -n 10
  ```
- **Step 6: Zotero Library Export (`export`)**
  Persist the final curated candidates to the designated Zotero collection:
  ```bash
  uv run python -m research_toolkit.cli export --batch <final_selection_file> --collection "<collection-name>"
  ```

### Pathway 2: One-Shot Composite Path (`scout`)

When the user requests an immediate end-to-end run (e.g., "一键检索入库", "直接跑 scout 流程", "端到端检索"), use the unified `scout` composite command:
```bash
uv run python -m research_toolkit.cli scout "<Tier 1 Query>" --collection "<collection-name>" -n 10 --direction both [--dry-run] [--quiet] [--json] [--detail]
```
The composite command automatically executes Search -> Initial Rank -> Snowball -> Re-Rank -> CurationCheckpoint -> Export in one execution.

---

## 3. End-to-End Workflow

When invoked, the agent executes four sequential steps:

### Step 1: Ingestion, Pathway Selection & Intent Mapping

Analyze the user's input to determine the execution pathway and flags:

**Intent-to-Flag Mapping Table**:
| User Intent / Natural Language Clue | CLI Flag | Default / Fallback |
| :--- | :--- | :--- |
| Target paper count (e.g., "找 20 篇", "扩充 15 篇") | `-n <N>` / `-k <N>` | `10` |
| Target collection (e.g., "存入集合 llm-eval") | `--collection <name>` / `-c <name>` | Auto slug `research/cimo-<intervention>` |
| Snowball direction: "只看经典奠基文献 / 历史引文" | `--direction backward` | `both` |
| Snowball direction: "只看最新前沿 / 引用文献" | `--direction forward` | `both` |
| Snowball direction: "双向滚雪球 / 奠基与前沿" | `--direction both` | `both` |
| Sorting: "经典/高被引/奠基性文献" | `--sort citations` | `--sort composite` |
| Sorting: "最新进展/近年/前沿探索" | `--sort recent` | `--sort composite` |
| Citation threshold: "被引至少 50 次", "过滤低引" | `--min-cites <N>` | `0` (no minimum) |
| Publication channel: "只要正式发表", "过滤预印本/arxiv" | `--peer-reviewed` | Include preprints |
| Publication year: "2023年以后", "近三年", "2021-2024" | `-y <range>` | No year filter |
| Dry-run: "只看不存", "仅预览检索结果" | `--dry-run` | Commit to Zotero |
| Machine-readable JSON: "输出 JSON", 管道流 | `--json` | Terminal Rich table |

### Step 2: CIMO Decomposition & Vocabulary Expansion

For topic requests, deconstruct into four explicit dimensions:
- **Context ($C$)**: 2–3 quoted phrases defining the operating domain or setting.
- **Intervention ($I$)**: 2–3 quoted phrases specifying the core technique or artifact.
- **Mechanisms ($M$)**: 2–3 quoted phrases specifying the underlying process or dynamics.
- **Outcomes ($O$)**: 2–3 quoted phrases defining the target evaluation metrics or effects.

### Step 3: Command Formulation

#### Option A: One-Shot Composite Command (`scout`)
```bash
uv run python -m research_toolkit.cli scout '<Tier 1 Query>' --collection "<collection-name>" -n <limit> [--direction both|forward|backward] [--min-cites <N>] [-y <year>] [--peer-reviewed] [--dry-run]
```

#### Option B: Composable Pipeline Chaining (UNIX Streams)
```bash
uv run python -m research_toolkit.cli search '<Tier 1 Query>' -k 20 | uv run python -m research_toolkit.cli snowball --direction both | uv run python -m research_toolkit.cli rank -n 10 | uv run python -m research_toolkit.cli export --collection "<collection-name>"
```

#### Option C: Seed Collection Graph Expansion (`expand`)
When expanding an existing Zotero collection directly:
```bash
uv run python -m research_toolkit.cli expand "<collection-name>" -k <limit> [--sort topological|composite|citations|recent] [--min-co-cites <N>] [--dry-run]
```

---

## 4. Execution Modes & HITL Boundary

### Mode A: Interactive Preview (Default HITL)
Unless the user explicitly asks for immediate execution, present the structured decomposition and plan before running:

```markdown
### 🎯 CIMO Academic Decomposition & Search Plan

- **Context (C)**: "..." OR "..."
- **Intervention (I)**: "..." OR "..."
- **Mechanisms (M)**: "..." OR "..." (Screening criterion)
- **Outcomes (O)**: "..." OR "..." (Screening criterion)

#### 🔍 Synthesized Queries & Execution Plan
- **Tier 1 (High Recall / Automated)**: `(...) AND (...)`
- **Tier 2 (Refined / Diagnostic)**: `(...) AND (...) AND (...)`
- **Direction & Filters**: `--direction both`, `--min-cites <N>`, `--peer-reviewed`, `-y <range>`
- **Target Zotero Collection**: `research/cimo-...`
- **Workflow**: `research-toolkit scout '<Tier 1 Query>' --collection 'research/cimo-...' -n 10`

👉 **Next Step**: Shall I execute the scout pipeline and sync the curated literature into your Zotero library now?
```

### Mode B: One-Shot Execution
When the user gives an explicit directive to run immediately:
- Execute `scout` or the decomposed atomic commands via `run_command`.
- Render the candidate summary table and confirmation report.

---

## 5. Execution Guardrails & Fallbacks

1. **Legacy `search` Deprecation**:
   - If calling `search` with `--collection`, `--snowball`, or `--auto-sync`, a `DeprecationWarning` will be issued. Prefer invoking `scout` directly for end-to-end discovery.
2. **Zero Results Fallback (Auto-relax & Retry)**:
   - If initial search yields 0 candidates, automatically unquote restrictive multi-word terms or strip secondary synonyms from $C$ or $I$, and retry once.
3. **Missing Zotero Credentials Fallback**:
   - If `ZOTERO_USER_ID` or `ZOTERO_API_KEY` is missing or invalid, execute with `--dry-run` to inspect discovered papers in terminal without failing.

---

## 6. Reference Exemplars

### Exemplar 1: Multi-Agent Software Engineering (Classic / Peer-Reviewed)
**Input**: *"我想了解用多个大模型智能体协同做软件工程和复杂代码生成的机制，特别是它们怎么通过辩论或投票达成共识减少错误，想收集一些顶级高被引论文，只要正式发表的。"*

**CIMO Matrix**:
- **Context ($C$)**: `"software engineering"`, `"code generation"`, `"program synthesis"`
- **Intervention ($I$)**: `"multi-agent systems"`, `"LLM agents"`, `"collaborative agents"`
- **Mechanisms ($M$)**: `"multi-agent debate"`, `"consensus mechanism"`, `"peer review"`
- **Outcomes ($O$)**: `"error reduction"`, `"code correctness"`, `"pass@k"`

**Synthesized Queries**:
- **Tier 1**: `("software engineering" OR "code generation" OR "program synthesis") AND ("multi-agent systems" OR "LLM agents" OR "collaborative agents")`
- **Target Collection**: `research/cimo-multi-agent-code-gen`
- **Command (One-shot scout)**:
  ```bash
  uv run python -m research_toolkit.cli scout '("software engineering" OR "code generation" OR "program synthesis") AND ("multi-agent systems" OR "LLM agents" OR "collaborative agents")' --collection research/cimo-multi-agent-code-gen -n 10 --peer-reviewed
  ```

---

### Exemplar 2: Parameter-Efficient Fine-Tuning in Clinical NLP (Balanced Composite)
**Input**: *"How to fine-tune medical foundation models with PEFT/LoRA without forgetting general clinical knowledge under low compute?"*

**CIMO Matrix**:
- **Context ($C$)**: `"clinical NLP"`, `"medical language models"`, `"healthcare informatics"`
- **Intervention ($I$)**: `"parameter-efficient fine-tuning"`, `PEFT`, `LoRA`, `"low-rank adaptation"`
- **Mechanisms ($M$)**: `"catastrophic forgetting"`, `"weight freezing"`, `"representation stability"`
- **Outcomes ($O$)**: `"knowledge retention"`, `"diagnostic accuracy"`, `"memory efficiency"`

**Synthesized Queries**:
- **Tier 1**: `("clinical NLP" OR "medical language models" OR "healthcare informatics") AND ("parameter-efficient fine-tuning" OR PEFT OR LoRA OR "low-rank adaptation")`
- **Target Collection**: `research/cimo-peft-clinical-nlp`
- **Command (Decomposed agentic pipeline)**:
  ```bash
  # Step 1: Pure retrieval
  uv run python -m research_toolkit.cli search '("clinical NLP" OR "medical language models" OR "healthcare informatics") AND ("parameter-efficient fine-tuning" OR PEFT OR LoRA OR "low-rank adaptation")' -k 20
  # Step 2: Snowball & Rank
  uv run python -m research_toolkit.cli snowball --direction both | uv run python -m research_toolkit.cli rank -n 10
  # Step 3: Export
  uv run python -m research_toolkit.cli export --collection research/cimo-peft-clinical-nlp
  ```

---

## 7. Verification Checklist

Before reporting completion to the user, ensure:
1. Non-English terms are translated to standard English.
2. Compound terms are quoted (`"..."`); no unescaped wildcards (`*`).
3. Tier 1 query contains only $C$ and $I$ blocks combined with `AND`.
4. Topic slug uses clean kebab-case prefixed with `research/cimo-`.
5. The CLI command (`scout`, decomposed atomic pipeline, or `expand`) executes cleanly.
