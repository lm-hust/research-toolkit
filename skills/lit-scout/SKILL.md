---
name: lit-scout
description: Ingest arbitrary text, files, keywords, or dialogues, translate to English, deconstruct into the CIMO academic scoping review framework, expand synonyms and jargon, synthesize dual-tier queries for Semantic Scholar & OpenAlex, and automatically invoke search CLI to ingest papers into Zotero.
---

# Lit-Scout (文献小侦察兵)

`lit-scout` is a portable research skill that accelerates literature exploration and concept grasping in unfamiliar or emerging domains. Given messy input—a paragraph of informal thoughts, a draft file, a list of raw keywords, or multi-turn conversational context—`lit-scout` translates non-English terminology, structures concepts using the **CIMO** (Context, Intervention, Mechanisms, Outcomes) academic framework, synthesizes dual-tier search queries optimized for **Semantic Scholar** and **OpenAlex**, and drives the toolkit's `search` command to archive top papers into **Zotero**.

---

## 1. Theoretical Grounding & Design Principles

Based on primary evidence syntheses standards (Tricco et al. 2011; OSF Systematic Review Registration Protocol; PRISMA-S; PRESS Guidelines):

1. **CIMO over PICO for Generative & Computational Research**:
   - **Context ($C$)**: The environment, domain, population, operational constraints, or dataset type.
   - **Intervention ($I$)**: The core technique, computational artifact, algorithm, architecture, or policy intervention.
   - **Mechanisms ($M$)**: The internal causal pathways, dynamics, cognitive/algorithmic processes through which the intervention operates.
   - **Outcomes ($O$)**: The measurable qualitative or quantitative effects, metrics, performance gains, or trade-offs.
2. **Decoupled Search vs. Screening (Maximal Sensitivity / Recall)**:
   - In titles and abstracts, authors consistently report $C$ and $I$. Conversely, $M$ and $O$ are frequently latent, expressed via specialized jargon, or detailed only in empirical tables.
   - **Mandatory Search Block**: $(C) \land (I)$. Hard-filtering on $M$ or $O$ in electronic database queries creates severe false negatives.
   - **Screening Block**: $M$ and $O$ are retained as explicit eligibility criteria for title/abstract and full-text screening.
3. **Dual-Tier Query Strategy**:
   - **Tier 1 (High-Recall Scoping Query)**: $(C_1 \lor C_2 \lor \dots) \land (I_1 \lor I_2 \lor \dots)$. Fed directly into automated CLI ingestion.
   - **Tier 2 (Refined Diagnostic Query)**: $(C_1 \lor C_2) \land (I_1 \lor I_2) \land (M_1 \lor M_2)$. Displayed to the user for precision auditing and diagnostic searches.
4. **Platform-Specific Syntax Hygiene**:
   - Wrap compound academic phrases in double quotes (`"multi-agent systems"`).
   - Avoid wildcards (`*`, `?`) due to API limitations; explicitly enumerate plural and morphological variants.
   - Provide 2–4 high-impact quoted phrases per concept block to avoid token dilution in Semantic Scholar and OpenAlex.

---

## 2. End-to-End Workflow

When invoked, the agent executes four sequential steps:

### Step 1: Ingestion & Multilingual Transduction
- If the input is non-English (e.g. Chinese, German, Japanese), accurately translate and map concepts to standard English academic nomenclature (e.g., matching ACM CCS, IEEE Taxonomy, or arXiv categories).
- Extract the core research intent from the prompt, referenced file, or conversational thread.
- Parse any explicit user parameter overrides (e.g., "找 20 篇" -> `-k 20`, "放入集合 my-col" -> `--topic my-col`). Default is `-k 10` and auto slug.

### Step 2: CIMO Decomposition & Vocabulary Expansion
Deconstruct the problem into four explicit dimensions:
- **Context ($C$)**: 2–3 quoted phrases defining the operating domain or setting.
- **Intervention ($I$)**: 2–3 quoted phrases specifying the core technique or artifact.
- **Mechanisms ($M$)**: 2–3 quoted phrases specifying the underlying process or dynamics.
- **Outcomes ($O$)**: 2–3 quoted phrases defining the target evaluation metrics or effects.

### Step 3: Query Compilation & Collection Derivation
1. **Tier 1 Query**: Compile `(C_terms) AND (I_terms)`.
2. **Tier 2 Query**: Compile `(C_terms) AND (I_terms) AND (M_terms)`.
3. **Target Collection Slug**: Derive a kebab-cased topic slug: `cimo-<intervention-slug>`. Canonical Zotero collection name is `research/cimo-<intervention-slug>`.
4. **Formulate CLI Command**:
   ```bash
   uv run python -m research_toolkit.cli search "<Tier 1 Query>" -k <limit> --topic <slug>
   ```

### Step 4: Presentation & Execution Modes

#### Mode A: Interactive Preview (Default HITL)
Unless the user explicitly specifies immediate execution, present the structured CIMO matrix and proposed queries:

```markdown
### 🎯 CIMO Academic Decomposition & Search Plan

- **Context (C)**: "..." OR "..."
- **Intervention (I)**: "..." OR "..."
- **Mechanisms (M)**: "..." OR "..." (Screening criterion)
- **Outcomes (O)**: "..." OR "..." (Screening criterion)

#### 🔍 Synthesized Queries
- **Tier 1 (High Recall / Automated)**: `(...) AND (...)`
- **Tier 2 (Refined / Diagnostic)**: `(...) AND (...) AND (...)`
- **Target Zotero Collection**: `research/cimo-...`

👉 **Next Step**: Shall I execute the search and sync the top papers into your Zotero library now?
```

#### Mode B: One-Shot Bypass (Direct Execution)
If the user's prompt includes explicit action verbs (e.g., "直接搜", "一键入库", "抓取到 Zotero", "run search directly", "fetch papers now"):
- Immediately execute the compiled CLI command via `run_command`.
- Render the resulting paper candidates and confirmation in the response.

---

## 3. Execution Guardrails & Error Fallbacks

1. **Zero Results Fallback (Auto-relax & Retry)**:
   - If the search returns 0 papers, automatically loosen the query: strip the most restrictive secondary synonym from the $C$ or $I$ block, or unquote a 3-word phrase into core keywords, and retry once.
   - If still zero, inform the user with diagnostic advice on which term block caused over-filtering.
2. **Missing Zotero Credentials Fallback**:
   - If Zotero configuration (`ZOTERO_USER_ID` or `ZOTERO_API_KEY`) is missing or fails authentication, automatically re-run with `--dry-run -d`.
   - Present the top-ranked paper candidates in a structured Markdown table without terminating with an unhandled exception, alerting the user to add Zotero credentials to `.env`.
3. **Explicit Parameter Precedence**:
   - User-supplied count (`-k`) or collection name (`--topic`) strictly overrides the defaults.

---

## 4. Reference Exemplars

### Exemplar 1: Multi-Agent Software Engineering
**Input**: *"我想了解用多个大模型智能体协同做软件工程和复杂代码生成的机制，特别是它们怎么通过辩论或投票达成共识减少错误，想收集一些顶级论文。"*

**CIMO Matrix**:
- **Context ($C$)**: `"software engineering"`, `"code generation"`, `"program synthesis"`
- **Intervention ($I$)**: `"multi-agent systems"`, `"LLM agents"`, `"collaborative agents"`
- **Mechanisms ($M$)**: `"multi-agent debate"`, `"consensus mechanism"`, `"peer review"`
- **Outcomes ($O$)**: `"error reduction"`, `"code correctness"`, `"pass@k"`

**Synthesized Queries**:
- **Tier 1**: `("software engineering" OR "code generation" OR "program synthesis") AND ("multi-agent systems" OR "LLM agents" OR "collaborative agents")`
- **Tier 2**: `("software engineering" OR "code generation") AND ("multi-agent systems" OR "LLM agents") AND ("multi-agent debate" OR "consensus mechanism" OR "peer review")`
- **Target Collection**: `research/cimo-multi-agent-code-gen`
- **CLI Ingestion**:
  ```bash
  uv run python -m research_toolkit.cli search '("software engineering" OR "code generation" OR "program synthesis") AND ("multi-agent systems" OR "LLM agents" OR "collaborative agents")' -k 10 --topic cimo-multi-agent-code-gen
  ```

---

### Exemplar 2: Parameter-Efficient Fine-Tuning in Clinical NLP
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
- **CLI Ingestion**:
  ```bash
  uv run python -m research_toolkit.cli search '("clinical NLP" OR "medical language models" OR "healthcare informatics") AND ("parameter-efficient fine-tuning" OR PEFT OR LoRA OR "low-rank adaptation")' -k 10 --topic cimo-peft-clinical-nlp
  ```

---

## 5. Portability & Installation

To make `lit-scout` globally available across any workspace in Antigravity / Claude:

```bash
ln -s /home/ling/projects/research-toolkit/skills/lit-scout ~/.gemini/config/skills/lit-scout
```

---

## 6. Verification Checklist

Before reporting completion to the user, ensure:
1. Non-English terms are translated to standard English.
2. Compound terms are quoted (`"..."`); no unescaped or unsupported wildcards (`*`).
3. Tier 1 query contains only $C$ and $I$ blocks combined with `AND`.
4. Topic slug uses clean kebab-case prefixed with `cimo-`.
5. The `search` command executes cleanly against `research_toolkit.cli`.
