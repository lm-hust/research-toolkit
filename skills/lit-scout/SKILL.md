---
name: lit-scout
description: Ingest arbitrary text, files, keywords, or existing Zotero collections; deconstruct into the CIMO academic scoping review framework; expand synonyms and jargon; synthesize dual-tier queries for Semantic Scholar & OpenAlex; execute bidirectional citation snowballing and topological ranking; and invoke search or expand CLI to ingest papers into Zotero.
---

# Lit-Scout (文献小侦察兵)

`lit-scout` is a research exploration and literature intelligence skill. Given informal text, a draft file, raw keywords, multi-turn dialogues, or an existing Zotero seed collection, `lit-scout`:
1. Translates non-English terminology into standardized English academic vocabulary.
2. Structures concepts using the **CIMO** (Context, Intervention, Mechanisms, Outcomes) academic scoping review framework.
3. Compiles dual-tier search queries optimized for **Semantic Scholar** and **OpenAlex**.
4. Discovers core foundational and frontier literature via 1-hop bidirectional **citation snowballing** (co-citation & bibliographic coupling).
5. Maps user requirements to multimodal ranking filters (`--sort`, `--min-cites`, `--peer-reviewed`, `--year`, `--snowball`).
6. Executes automated paper ingestion or interactive collection expansion into **Zotero** with rich topological tags and citation metadata.

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

## 2. End-to-End Workflow

When invoked, the agent executes four sequential steps:

### Step 1: Ingestion, Pathway Selection & Intent Mapping

Analyze the user's input to determine the execution pathway:
- **Pathway A (Topic / Keyword Discovery)**: User supplies informal text, keywords, questions, or themes. -> Use `search`.
- **Pathway B (Seed Collection Snowballing)**: User references an existing Zotero collection of seed papers to expand. -> Use `expand`.

**Intent-to-Flag Mapping Table**:
| User Intent / Natural Language Clue | CLI Flag | Default / Fallback |
| :--- | :--- | :--- |
| Target paper count (e.g., "找 20 篇", "扩充 15 篇") | `-k <N>` | `8` (`search`) / `10` (`expand`) |
| Target collection (e.g., "存入集合 llm-eval") | `--topic <name>` / `-t <name>` | Auto slug `cimo-<intervention>` |
| Sorting: "经典/高被引/奠基性文献" | `--sort citations` | `--sort composite` (`search`) |
| Sorting: "最新进展/近年/前沿探索" | `--sort recent` | `--sort composite` (`search`) |
| Sorting: "引文拓扑/共引重合/滚雪球核心" | `--sort topological` | Default for `expand` |
| Citation threshold: "被引至少 50 次", "过滤低引" | `--min-cites <N>` | `0` (no minimum) |
| Co-citation threshold (expand): "共引至少 2 次" | `--min-co-cites <N>` | `1` |
| Publication channel: "只要正式发表", "过滤预印本/arxiv" | `--peer-reviewed` | Include preprints |
| Publication year: "2023年以后", "近三年", "2021-2024" | `-y <range>` | No year filter |
| Graph Snowballing: "启用滚雪球/拓扑发现" | `--snowball` | Enabled by default in `search` |
| Bypass Snowballing: "只要关键词搜索/不要滚雪球" | `--no-snowball` | Full snowball expansion |
| Curation mode: "非交互式/静默执行/全选导入" | `--yes` / `-I` | Auto-detect TTY |
| Dry-run: "只看不存", "仅预览检索结果" | `--dry-run` | Sync to Zotero |

### Step 2: CIMO Decomposition & Vocabulary Expansion (Pathway A)

For keyword discovery requests, deconstruct into four explicit dimensions:
- **Context ($C$)**: 2–3 quoted phrases defining the operating domain or setting.
- **Intervention ($I$)**: 2–3 quoted phrases specifying the core technique or artifact.
- **Mechanisms ($M$)**: 2–3 quoted phrases specifying the underlying process or dynamics.
- **Outcomes ($O$)**: 2–3 quoted phrases defining the target evaluation metrics or effects.

### Step 3: Command Formulation

#### Pathway A: Keyword Search & Snowballing (`search`)
1. **Tier 1 Query**: `(C_terms) AND (I_terms)`.
2. **Tier 2 Query**: `(C_terms) AND (I_terms) AND (M_terms)`.
3. **Target Collection Slug**: Derive a kebab-cased topic slug: `cimo-<intervention-slug>`.
4. **Formulate CLI Command**:
   ```bash
   uv run python -m research_toolkit.cli search "<Tier 1 Query>" -k <limit> --topic <slug> [--sort composite|topological|citations|recent] [--min-cites <N>] [-y <year>] [--peer-reviewed] [--snowball/--no-snowball] [--dry-run]
   ```

#### Pathway B: Seed Collection Graph Expansion (`expand`)
When expanding an existing Zotero collection:
```bash
uv run python -m research_toolkit.cli expand "<collection-name>" -k <limit> [--target <target-collection>] [--sort topological|composite|citations|recent] [--min-co-cites <N>] [--dry-run]
```

#### Pathway C: Structured Assessment & MMR Ranking (`rank`)
When ranking candidates with composite scoring (50% relevance, 25% log-citations, 15% venue, 10% recency) and MMR author diversity:
```bash
# Pipe chaining directly from search
uv run python -m research_toolkit.cli search "<Tier 1 Query>" -k 20 | uv run python -m research_toolkit.cli rank -n 10

# Ranking an existing batch with structured assessments
uv run python -m research_toolkit.cli rank --batch <batch_id_or_path> -n 10 [--assessments <assessments.jsonl>] [--topic <slug>]
```

#### Pathway D: Atomic Citation Snowballing (`snowball`)
When expanding 1-hop bidirectional citation networks from multi-source seeds (piped `SelectionResult` or `PaperCandidateBatch`, batch files, explicit DOIs/IDs, or Zotero collections):
```bash
# Pipe chaining: Search -> Snowball -> MMR Rank
uv run python -m research_toolkit.cli search "<Tier 1 Query>" -k 10 | uv run python -m research_toolkit.cli snowball --direction both --max-backward 20 --max-forward 20 | uv run python -m research_toolkit.cli rank -n 10

# Snowball from explicit seed DOIs or platform IDs
uv run python -m research_toolkit.cli snowball --seeds "10.1000/182,10.1000/183" --direction forward --max-forward 15

# Snowball from an existing Zotero collection
uv run python -m research_toolkit.cli snowball --from-collection "<collection-name>" --direction both
```

### Step 4: Presentation & Execution Modes

#### Mode A: Interactive Preview (Default HITL)
Unless the user explicitly asks for immediate one-shot execution, present the structured decomposition and plan before running:

```markdown
### 🎯 CIMO Academic Decomposition & Search Plan

- **Context (C)**: "..." OR "..."
- **Intervention (I)**: "..." OR "..."
- **Mechanisms (M)**: "..." OR "..." (Screening criterion)
- **Outcomes (O)**: "..." OR "..." (Screening criterion)

#### 🔍 Synthesized Queries & Execution Plan
- **Tier 1 (High Recall / Automated)**: `(...) AND (...)`
- **Tier 2 (Refined / Diagnostic)**: `(...) AND (...) AND (...)`
- **Sorting & Filters**: `--sort <mode>`, `--min-cites <N>`, `--peer-reviewed`, `-y <range>`
- **Graph Snowballing**: 1-hop bidirectional citation expansion enabled
- **Target Zotero Collection**: `research/cimo-...`
- **Persistence Metadata**: Topological role tags (`topo/foundational`, `topo/recent-advancement`), citation count tags (`cites:>10`, `cites:>50`), and `extra` metrics.

👉 **Next Step**: Shall I execute the search and sync the top papers into your Zotero library now?
```

#### Mode B: One-Shot Execution
When the user's prompt includes explicit action verbs (e.g., "直接搜", "一键入库", "抓取到 Zotero", "expand immediately", "fetch papers now"):
- Immediately execute the compiled CLI command via `run_command`.
- Render the ranked candidate table and confirmation summary. Candidate badges:
  - `[REV]` (Review), `[PRE]` (Preprint), `[RES]` (Peer-reviewed Research)
  - `[Foundational]` (Co-cited by seed literature)
  - `[Recent Advancement]` (Cites multiple seed papers)

---

## 3. Execution Guardrails & Error Fallbacks

1. **Zero Results Fallback (Auto-relax & Retry)**:
   - If the initial query returns 0 candidates, automatically loosen the query: strip the most restrictive secondary synonym from the $C$ or $I$ block, or unquote a 3-word phrase into core keywords, and retry once.
   - If still zero, provide diagnostic feedback on which keyword block caused the over-filtering.
2. **Missing DOIs in Seed Collection (`expand`)**:
   - When seed items in Zotero lack DOIs, the toolkit uses canonical titles to resolve DOIs on OpenAlex/Crossref before snowballing. If a seed cannot be resolved, a warning is logged and remaining valid seeds continue.
3. **Missing Zotero Credentials Fallback**:
   - If `ZOTERO_USER_ID` or `ZOTERO_API_KEY` is missing or invalid, re-run with `--dry-run -d` to present discovered and ranked literature in the terminal without crashing.
4. **Parameter Precedence**:
   - User-supplied count (`-k`), collection name (`--topic` / `--target`), and sorting modes strictly override defaults.

---

## 4. Reference Exemplars

### Exemplar 1: Multi-Agent Software Engineering (Classic / Peer-Reviewed)
**Input**: *"我想了解用多个大模型智能体协同做软件工程和复杂代码生成的机制，特别是它们怎么通过辩论或投票达成共识减少错误，想收集一些顶级高被引论文，只要正式发表的。"*

**CIMO Matrix**:
- **Context ($C$)**: `"software engineering"`, `"code generation"`, `"program synthesis"`
- **Intervention ($I$)**: `"multi-agent systems"`, `"LLM agents"`, `"collaborative agents"`
- **Mechanisms ($M$)**: `"multi-agent debate"`, `"consensus mechanism"`, `"peer review"`
- **Outcomes ($O$)**: `"error reduction"`, `"code correctness"`, `"pass@k"`

**Synthesized Queries**:
- **Tier 1**: `("software engineering" OR "code generation" OR "program synthesis") AND ("multi-agent systems" OR "LLM agents" OR "collaborative agents")`
- **Tier 2**: `("software engineering" OR "code generation") AND ("multi-agent systems" OR "LLM agents") AND ("multi-agent debate" OR "consensus mechanism" OR "peer review")`
- **Target Collection**: `research/cimo-multi-agent-code-gen`
- **Flags Mapped**: `--sort citations --peer-reviewed`
- **CLI Command**:
  ```bash
  uv run python -m research_toolkit.cli search '("software engineering" OR "code generation" OR "program synthesis") AND ("multi-agent systems" OR "LLM agents" OR "collaborative agents")' -k 10 --topic cimo-multi-agent-code-gen --sort citations --peer-reviewed
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
- **Tier 2**: `("clinical NLP" OR "medical language models") AND ("parameter-efficient fine-tuning" OR LoRA) AND ("catastrophic forgetting" OR "weight freezing")`
- **Target Collection**: `research/cimo-peft-clinical-nlp`
- **Flags Mapped**: `--sort composite` (default)
- **CLI Command**:
  ```bash
  uv run python -m research_toolkit.cli search '("clinical NLP" OR "medical language models" OR "healthcare informatics") AND ("parameter-efficient fine-tuning" OR PEFT OR LoRA OR "low-rank adaptation")' -k 10 --topic cimo-peft-clinical-nlp
  ```

---

### Exemplar 3: Energy Intelligence / Power Systems (Recent & Filtered)
**Input**: *"度电智能是个什么样的概念 查找一下近几年的文献 过滤掉低引用论文 并且一键导入最相关的 10 篇"*

**CIMO Matrix**:
- **Context ($C$)**: `"power systems"`, `"smart grid"`, `"renewable energy"`
- **Intervention ($I$)**: `"energy intelligence"`, `"AI for energy"`, `"computational energy management"`
- **Mechanisms ($M$)**: `"load forecasting"`, `"optimal power flow"`, `"demand response"`
- **Outcomes ($O$)**: `"energy efficiency"`, `"carbon reduction"`, `"levelized cost of energy"`

**Synthesized Queries**:
- **Tier 1**: `("power systems" OR "smart grid" OR "renewable energy") AND ("energy intelligence" OR "AI for energy" OR "computational energy management")`
- **Tier 2**: `("power systems" OR "smart grid") AND ("energy intelligence" OR "AI for energy") AND ("load forecasting" OR "optimal power flow")`
- **Target Collection**: `research/cimo-energy-intelligence`
- **Flags Mapped**: `-y 2023+ --min-cites 5`
- **CLI Command**:
  ```bash
  uv run python -m research_toolkit.cli search '("power systems" OR "smart grid" OR "renewable energy") AND ("energy intelligence" OR "AI for energy" OR "computational energy management")' -k 10 --topic cimo-energy-intelligence -y 2023+ --min-cites 5
  ```

---

### Exemplar 4: Zotero Seed Collection Snowballing (Citation Graph Expansion)
**Input**: *"我 Zotero 里有个集合叫 agent-memory，里面已经放了几篇核心的种子论文。帮我做双向滚雪球，找出共引最频繁的奠基文献和最新的引用前沿，扩充 15 篇论文到这个集合里。"*

**Analysis & Pathway**:
- **Pathway**: B (Seed Collection Snowballing via `expand`)
- **Source Collection**: `agent-memory`
- **Target Count**: `-k 15`
- **Ranking**: `--sort topological` (prioritizes high co-citation frequency)
- **CLI Command**:
  ```bash
  uv run python -m research_toolkit.cli expand "agent-memory" -k 15 --sort topological
  ```

---

## 5. Portability & Global Installation

To link `lit-scout` globally across any Antigravity / Claude workspace:

```bash
mkdir -p ~/.gemini/config/skills
ln -s /home/ling/projects/research-toolkit/skills/lit-scout ~/.gemini/config/skills/lit-scout
mkdir -p ~/.agents/skills
ln -s /home/ling/projects/research-toolkit/skills/lit-scout ~/.agents/skills/lit-scout
```

---

## 6. Verification Checklist

Before reporting completion to the user, ensure:
1. Non-English terms are translated to standard English.
2. Compound terms are quoted (`"..."`); no unescaped or unsupported wildcards (`*`).
3. Tier 1 query contains only $C$ and $I$ blocks combined with `AND`.
4. Topic slug uses clean kebab-case prefixed with `cimo-`.
5. If expanding an existing collection, verify the collection name matches an existing Zotero collection.
6. The CLI command (`search` or `expand`) executes cleanly against `research_toolkit.cli`.
