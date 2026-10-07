# Research Report: CIMO Scoping Review Query Formulation Principles

**Issue Reference**: `lm-hust/research-toolkit#16`  
**Parent Map**: `lm-hust/research-toolkit#15` (Develop portable `lit-scout` skill)  
**Conforming Standard**: `CONTEXT.md` (`PaperCandidate`, `ReviewPaper`, `Ranker`, `ZoteroCollection`, `FulltextCheckpoint`)  
**Primary Literature**:
- Tricco, A. C., Tetzlaff, J., & Moher, D. (2011). *The art and science of knowledge synthesis*. Journal of Clinical Epidemiology, 64(1), 11–20. [PDF](file:///home/ling/projects/research-toolkit-query/docs/research/query-builder/Tricco%20et%20al.%20-%202011%20-%20The%20art%20and%20science%20of%20knowledge%20synthesis.pdf)
- Van den Akker, O. R., Peters, G. Y., Bakker, C., et al. (2020/2023). *OSF Generalized Systematic Review Registration Template*. Center for Open Science / MetaArXiv. [PDF](file:///home/ling/projects/research-toolkit-query/docs/research/query-builder/OSF%20Generalized%20Systematic%20Review%20Registration%20Template.pdf)
- Denyer, D., Tranfield, D., & van Aken, J. E. (2008). *Developing Design Propositions through Research Synthesis*. Organization Studies, 29(3), 393–413.
- Rethlefsen, M. L., et al. (2021). *PRISMA-S: An Extension to the PRISMA Statement for Reporting Literature Searches in Systematic Reviews*. Systematic Reviews, 10(1), 39.
- McGowan, J., et al. (2016). *PRESS Peer Review of Electronic Search Strategies: 2015 Guideline Statement*. Journal of Clinical Epidemiology, 75, 40–46.
- Peters, M. D. J., et al. (2020). *Updated methodological guidance for the conduct of scoping reviews*. JBI Evidence Synthesis, 18(10), 2119–2126.
- Arksey, H., & O'Malley, L. (2005). *Scoping studies: towards a methodological framework*. International Journal of Social Research Methodology, 8(1), 19–32.

---

## Executive Summary

This research report establishes the theoretical and algorithmic principles for translating unstructured user research intentions (prompts, raw keywords, or notes) into high-recall academic search queries using the **CIMO** framework. 

In automated literature discovery pipelines—such as the `research-toolkit` discovery subsystem and the forthcoming `lit-scout` skill—the primary hazard is **catastrophic recall drop**: constructing over-constrained boolean queries that exclude seminal literature because authors described mechanisms or outcomes using non-standardized vocabulary.

By synthesizing primary evidence from knowledge synthesis methodology (Tricco et al. 2011, OSF Registration Template, PRISMA-S, JBI Scoping Review Manual), we demonstrate that:
1. **Scoping queries must decouple the Search stage from the Screening stage**: The mandatory search block consists exclusively of **$\text{Context } (C) \land \text{Intervention } (I)$**, maximizing bibliographic sensitivity.
2. **Mechanisms ($M$) and Outcomes ($O$) must be reserved for title/abstract screening and qualitative synthesis**, rather than injected as hard boolean exclusions.
3. **Multi-platform adaptation is essential**: While classical search platforms rely on nested boolean strings, modern academic discovery engines (Semantic Scholar Graph API and OpenAlex Works API) employ neural/lexical or tokenized search requiring explicit phrase preservation and token pruning, exactly as codified in [`QueryTranslator`](file:///home/ling/projects/research-toolkit-query/src/research_toolkit/discovery/query.py).

---

## 1. Methodological Foundations: The CIMO Framework in Scoping Reviews

### 1.1 Structural Definitions of CIMO

The **CIMO** framework was formulated by Denyer, Tranfield, and van Aken (2008) in design science and management to construct grounded, prescriptive design propositions ("*In Context $C$, to achieve Outcome $O$, use Intervention $I$, triggered by Mechanism $M$*"). 

| Dimension | Definition | Role in Question Deconstruction | Typical Manifestation in Primary Literature |
| :--- | :--- | :--- | :--- |
| **Context ($C$)** | The surrounding environment, domain, population, organizational setting, or technical architecture. | Defines boundary conditions under which interventions are tested. Answers: *Where, for whom, and under what constraints?* | Application domain (e.g., healthcare systems, distributed edge computing, multi-agent frameworks, enterprise knowledge management). |
| **Intervention ($I$)** | The specific action, technological artifact, algorithm, policy, or methodology introduced. | Identifies the independent variable or technological lever. Answers: *What action, tool, or approach is being deployed?* | Methodological or algorithmic artifacts (e.g., retrieval-augmented generation, parameter-efficient fine-tuning, consensus protocols, self-reflection agents). |
| **Mechanisms ($M$)** | The underlying causal dynamics, theoretical pathways, or system processes triggered by the intervention. | Explains the explanatory pathway bridging action and result. Answers: *How and why does the intervention generate effects?* | Latent processes (e.g., cognitive load reduction, attention routing, hallucination mitigation, communication bandwidth minimization). |
| **Outcomes ($O$)** | The observed consequences, metrics, qualitative shifts, or empirical endpoints produced. | Evaluates efficacy, failure modes, or performance changes. Answers: *What results, impacts, or tradeoffs occur?* | Benchmark metrics and empirical outcomes (e.g., BLEU score, inference latency, decision accuracy, organizational retention, energy efficiency). |

### 1.2 Comparative Analysis: CIMO vs. PICO vs. PCC

Tricco et al. (2011, Section 3) note that while **PICO** (Population, Intervention, Comparator, Outcome) is the classic paradigm for clinical effectiveness reviews (evaluating whether Intervention A outperforms Comparator B in Population P), it fails to fit broader, complex, or qualitative syntheses.

| Feature | PICO (Tricco et al. 2011) | PCC (JBI / Peters et al. 2020) | CIMO (Denyer et al. 2008) |
| :--- | :--- | :--- | :--- |
| **Primary Domain** | Clinical trials, medicine, epidemiology. | Healthcare scoping reviews, broad social mapping. | Engineering, computer science, management, socio-technical systems. |
| **Core Components** | Population, Intervention, Comparator, Outcome. | Population, Concept, Context. | Context, Intervention, Mechanism, Outcome. |
| **Comparator Expectation** | Strict requirement for control/baseline arm ($C$). | Explicitly omits comparators to keep scope open. | Absorbs baseline comparisons into contextual constraints. |
| **Explanatory Depth** | Black-box effect size ($\Delta O = \text{Treated} - \text{Control}$). | Conceptual map (what concepts exist in what contexts). | Generative causality ($I \xrightarrow{M} O$ within context $C$). |
| **Fitness for AI/Engineering** | Poor: AI systems rarely have clinical "patients" or inert placebos. | Moderate: useful for preliminary landscape mapping. | **Optimal**: explicitly captures algorithmic interventions and underlying theoretical mechanisms. |

In engineering, applied AI, and computational systems, research questions naturally conform to generative propositions: *How does an algorithmic intervention ($I$) operate through computational/mathematical mechanisms ($M$) to achieve performance or architectural outcomes ($O$) within specific execution contexts ($C$)?*

---

## 2. Query Sensitivity & Recall Strategy

### 2.1 The Sensitivity (Recall) vs. Specificity (Precision) Trade-off

In knowledge synthesis methodology (Arksey & O'Malley 2005; Tricco et al. 2011; PRISMA-S 2021), a fundamental asymmetry governs the retrieval stage:
- **Sensitivity (Recall)**: The proportion of all existing relevant literature that is captured by the query string.
- **Specificity (Precision)**: The proportion of retrieved records that are truly relevant to the research topic.

In scoping reviews and exploratory literature scouting, **Recall is paramount**. A missed seminal paper at the database retrieval boundary is irreversibly lost to all downstream stages (Zotero ingestion, full-text checkpoint, NotebookLM synthesis). Conversely, low precision merely results in retrieving non-relevant records that can be filtered out during subsequent ranking and screening.

```
+-------------------------------------------------------------------------+
|                  BIBLIOGRAPHIC RETRIEVAL STAGE                          |
|             Goal: Maximize Sensitivity (Recall >= 95%)                  |
|                                                                         |
|   Query String = (Context Terms) AND (Intervention Terms)               |
|                                                                         |
|   [!] Mechanisms (M) and Outcomes (O) EXCLUDED from search query        |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                      COMPOSITE RANKING STAGE                            |
|             (research-toolkit Ranker & VenueRegistry)                   |
|                                                                         |
|   Composite Score: 0.40 Rel + 0.35 Cite + 0.25 Venue + 0.20 ReviewTier  |
|   Guarantees top slots for leading ReviewPapers & high-velocity works   |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                   SCREENING & ELIGIBILITY STAGE                         |
|             Goal: Enforce Specificity (Precision Optimization)          |
|                                                                         |
|   Human / LLM Evaluator filters by Mechanisms (M) and Outcomes (O)     |
|   from retrieved Titles and Abstracts                                   |
+-------------------------------------------------------------------------+
```

### 2.2 The Mandatory $C \land I$ Search Block Principle

Why do **Context ($C$)** and **Intervention ($I$)** form the mandatory search block, while **Mechanisms ($M$)** and **Outcomes ($O$)** are excluded from the boolean search query?

1. **Title, Abstract, and Keyword Representation**:
   Authors universally declare the environment/domain ($C$) and the core technology/artifact ($I$) in their article title and abstract. A paper presenting a novel agent framework will invariably contain words like *"large language model"*, *"autonomous agents"*, or *"multi-agent collaboration"*.
2. **Mechanism Vocabulary Heterogeneity**:
   Mechanisms are frequently latent, implied, or described using disparate theoretical dialects. For example, a mechanism describing "mitigating conflicting decisions between autonomous agents" might be phrased as:
   - *"game-theoretic equilibrium"*
   - *"majority voting with consensus negotiation"*
   - *"conflict resolution protocol"*
   - *"semantic debate and cross-examination"*  
   Injecting a boolean clause `AND ("conflict resolution" OR "consensus")` immediately eliminates papers that implemented the mechanism using "debate", "negotiation", or "consistency verification".
3. **Outcome Sparsity and Survivorship Bias**:
   Outcomes in computer science and engineering are often expressed solely as raw numeric tables or niche benchmark names (e.g., *"HumanEval"*, *"MMLU"*, *"throughput increased by 23%"*). Furthermore, scoping reviews aim to discover *what outcomes exist*. Demanding specific expected outcomes in the query guarantees confirmation bias and filters out unanticipated negative, mixed, or emergent results.

### 2.3 Staged Protocol: Separation of Search and Screening (OSF Template Invariant)

The **OSF Generalized Systematic Review Registration Template** (Van den Akker et al., lines 306–310) establishes this exact procedural principle:
> *"Note that inclusion criteria are typically used to inform the search strategy; during screening, as soon as an exclusion criterion is met, an entry is excluded, and so, inclusion criteria are reformulated into exclusion criteria where applicable."*

In accordance with PRISMA-S and the OSF specification:
- **Search Strategy Stage**: Query strings use high-recall boolean unions across Context and Intervention:
  $$\text{Query}_{\text{Scoping}} = \left( C_1 \lor C_2 \lor \dots \lor C_n \right) \land \left( I_1 \lor I_2 \lor \dots \lor I_m \right)$$
- **Screening Stage**: Reviewers evaluate retrieved titles and abstracts against formal exclusion criteria based on $M$ and $O$:
  - *Exclude if study does not address causal mechanism $M$ (e.g., black-box non-collaborative workflows).*
  - *Exclude if study does not evaluate outcome $O$ (e.g., purely speculative position papers without empirical validation or benchmark assessment).*

### 2.4 The Dual-Tier Query Strategy

To balance automated high-recall harvesting with focused interactive research, the system implements a **Dual-Tier Query Strategy**:

- **Tier 1: Primary High-Recall Query ($C \land I$)**
  - Purpose: Default query dispatched directly to the automated retrieval engine (`search` CLI $\to$ Semantic Scholar / OpenAlex).
  - Structure: Broad boolean conjunction of Context and Intervention synonym clusters.
  - Objective: Maximum recall; retrieves 10–50 candidate papers into the candidate pool.
- **Tier 2: Refined Diagnostic Query ($C \land I \land M$)**
  - Purpose: Presented to the user for human-in-the-loop inspection, precision spot-checking, or manual execution when Tier 1 produces too many diffuse hits.
  - Structure: Adds selective Mechanism synonyms to narrow results to specific causal dynamics.

---

## 3. Systematic Vocabulary Expansion & Syntactic Hygiene

### 3.1 Multilingual Concept Transduction

User inquiries are frequently submitted in natural conversational prose or non-English languages (e.g., Chinese, Japanese, German). Direct literal machine translation of informal phrasing produces non-standard terminology that yields zero hits in international bibliographic databases.

The query expansion pipeline must perform **Conceptual Transduction** into canonical academic English:

```
[Raw User Input] 
"如何利用多智能体大模型协同解决软件工程里的复杂代码重构问题，减少幻觉？"
       |
       v  Conceptual Transduction (Academic Taxonomy Mapping)
+--------------------------------------------------------------------------+
| Context (C)      : Software Engineering, Code Refactoring, Legacy Systems |
| Intervention (I) : Multi-Agent Systems, LLM Agent Collaboration          |
| Mechanism (M)    : Role Specialization, Debate Protocol, Consensus       |
| Outcome (O)      : Hallucination Reduction, Refactoring Accuracy         |
+--------------------------------------------------------------------------+
```

Key translation rules:
1. **Taxonomy Anchoring**: Map terms to standard ontological vocabularies (e.g., ACM Computing Classification System, IEEE Computer Society keywords, MeSH, arXiv cs.SE / cs.AI / cs.MA subject categories).
2. **De-colloquialization**: Transform conversational phrases into established technical jargon (e.g., translate "让多个AI吵架" $\to$ *"multi-agent debate"*, *"adversarial collaboration"*).
3. **Disciplinary Translation**: Recognize when a technical concept has different nomenclature across subfields.

### 3.2 Disciplinary Jargon Bridging

Cross-disciplinary topics suffer from vocabulary fragmentation. The same underlying architectural concept is often described using completely different terms across distinct scholarly communities:

| Phenomenon | Artificial Intelligence / NLP | Software Engineering / Distributed Systems | Organizational / Management Science |
| :--- | :--- | :--- | :--- |
| **Coordinated Agents** | *"multi-agent systems"*, *"LLM agents"*, *"agentic workflows"* | *"distributed actors"*, *"cooperative processes"*, *"service choreography"* | *"autonomous teams"*, *"distributed cognition"*, *"coordination mechanisms"* |
| **Iterative Verification** | *"self-reflection"*, *"chain-of-thought verification"*, *"critic agent"* | *"continuous validation"*, *"automated regression testing"*, *"peer review"* | *"double-loop learning"*, *"sensemaking"*, *"audit trails"* |
| **Efficient Adaptation** | *"parameter-efficient fine-tuning"*, *"PEFT"*, *"low-rank adaptation (LoRA)"* | *"modular patching"*, *"runtime adaptation"*, *"incremental compilation"* | *"contingency adaptation"*, *"dynamic capabilities"* |

The vocabulary expansion phase must explicitly synthesize **Bridge Keywords** so that relevant literature from adjacent disciplines is not excluded.

### 3.3 Synonym Generation Hierarchy

For each CIMO block, synonyms must be structured across four orthogonal tiers:
1. **Canonical Hypernyms (Broader concepts)**: e.g., *"autonomous agents"*, *"artificial intelligence"*.
2. **Targeted Hyponyms (Narrower implementations / state-of-the-art tools)**: e.g., *"LLM-based agents"*, *"AutoGPT"*, *"MetaGPT"*, *"LangGraph"*.
3. **Orthographic & Spelling Variants**: Systematically bridge American and British spellings (e.g., *"optimization"* vs. *"optimisation"*, *"behavior"* vs. *"behaviour"*).
4. **Acronyms and Spelled-Out Expansions**: Always pair acronyms with their full formal terminology using `OR` (e.g., `("large language models" OR "LLMs")`, `("retrieval-augmented generation" OR "RAG")`, `("multi-agent system" OR "MAS")`).

### 3.4 Syntactic Hygiene for Search Platforms

1. **Exact Quoting (`"..."`)**: Multi-word compounds must be enclosed in double quotes (e.g., `"parameter-efficient fine-tuning"`). Unquoted compounds allow search engines to treat words as independent tokens, causing severe semantic drift.
2. **Wildcard & Truncation Elimination**: While classical databases (Ovid, Web of Science) support truncation operators (e.g., `agent*`), modern REST APIs (Semantic Scholar, OpenAlex) **do not reliably support regex or trailing wildcards**. The expansion step must explicitly enumerate singular and plural forms:
   - *Prohibited*: `agent*`, `retriev*`
   - *Mandatory*: `("agent" OR "agents")`, `("retrieval" OR "retrieving")`
3. **Boolean Nesting and Precedence**: All intra-concept synonyms must be enclosed in parentheses with uppercase `OR`, and blocks conjoined with uppercase `AND`:
   $$\left( \text{"term1"} \lor \text{"term2"} \right) \land \left( \text{"term3"} \lor \text{"term4"} \right)$$

---

## 4. Adaptation for Semantic Scholar and OpenAlex APIs

### 4.1 Platform Architecture & Retrieval Constraints

The `research-toolkit` discovery subsystem queries two distinct bibliographic endpoints with radically different query processing engines:

#### Semantic Scholar (S2) Graph API
- **Endpoint**: `GET https://api.semanticscholar.org/graph/v1/paper/search`
- **Retrieval Engine**: Hybrid lexical (BM25) and dense neural embedding search.
- **Syntax Limitations**: **Semantic Scholar does not support boolean operators (`AND`, `OR`, `NOT`) or parentheses (`()`)**. If boolean strings like `(A OR B) AND C` are submitted to S2:
  - The S2 parser treats `AND`, `OR`, `NOT` as literal search tokens or stopwords.
  - Large clusters of 20+ synonym tokens cause severe **token dilution**, degrading dense neural matching and pushing core relevant papers below the retrieval threshold.
- **Quoted Phrases**: S2 natively supports exact phrase matching via double quotes `"..."`.

#### OpenAlex Works API
- **Endpoint**: `GET https://api.openalex.org/works`
- **Retrieval Engine**: Elasticsearch cluster over inverted full-text and bibliographic fields.
- **Syntax Limitations**: OpenAlex `search` parameter performs space-delimited AND matching. It supports double-quoted phrases `"..."`. Boolean connectors (`AND`, `OR`) are not processed as boolean logic operators and must be removed to avoid unintended literal string matching.
- **Structured Filters**: OpenAlex excels at metadata filtering via explicit query parameters (e.g., `filter=type:review,publication_year:2020-2026`), which the `research-toolkit` client already leverages.

### 4.2 Alignment with `research-toolkit`'s `QueryTranslator`

The [`QueryTranslator`](file:///home/ling/projects/research-toolkit-query/src/research_toolkit/discovery/query.py) class in `research-toolkit` operationalizes these adaptation principles:

```python
# From src/research_toolkit/discovery/query.py

class QueryTranslator:
    @staticmethod
    def to_semantic_scholar(query: str) -> str:
        # 1. Strips NOT clauses
        # 2. Strips parentheses ()
        # 3. Strips boolean operators (AND, OR)
        # 4. Extracts preserved quoted phrases and cleaned keywords
        ...

    @staticmethod
    def to_openalex(query: str) -> str:
        # 1. Strips NOT clauses
        # 2. Cleans parentheses
        # 3. Strips AND/OR keywords
        # 4. Collapses whitespace while preserving quotes
        ...

    @staticmethod
    def to_topic_slug(query: str) -> str:
        # Extracts 6-term clean kebab-cased slug for ZoteroCollection naming
        ...
```

#### Implications for Query Formulation:
1. **Preserve Quoted Phrases**: The input query must wrap compound terms in double quotes (e.g., `"multi-agent systems"`). `QueryTranslator` strictly preserves quoted tokens while stripping boolean noise.
2. **Salient Concept Selection over Exhaustive Token Dumps**: Because `to_semantic_scholar` transforms `(A OR B OR C) AND (D OR E)` into a flat token list `A B C D E`, generating 40 synonyms will overwhelm S2. The upstream query builder should supply **2 to 4 high-value quoted phrases** per block for the search query, saving broader vocabulary for screening.
3. **Zotero Namespace Integration**: Using `to_collection_name(query, topic="cimo-<slug>")` automatically ensures target collections conform to `CONTEXT.md` standards: `research/cimo-<slug>`.

### 4.3 Search Validation via Benchmark Seed Set (PRESS Standard)

Following the PRESS (Peer Review of Electronic Search Strategies; McGowan et al. 2016) and OSF search validation guidelines (lines 250–254), every generated query strategy should include a **Search Validation Benchmark**:
- Identify 2 to 3 known foundational papers ("gold standard seeds") that *must* be retrieved.
- Verify that the adapted query returns these seed papers in the top 10 results.
- If a seed paper is absent, inspect its abstract and author keywords to discover missing synonym variants.

---

## 5. Recommended Prompt Guidelines and Few-Shot Templates for `lit-scout`

The following prompt structure and few-shot templates are designed for direct inclusion into the upcoming `skills/lit-scout/SKILL.md`.

### 5.1 Step-by-Step Agent Workflow

When invoked with arbitrary user input (text, topic, or file path), the `lit-scout` agent executes a four-phase workflow:

```
Step 1: Ingest & Deconstruct
  ├── Analyze input intent across Context (C), Intervention (I), Mechanism (M), Outcome (O).
  └── Map non-English or informal expressions to canonical academic English.

Step 2: Expand Vocabulary & Synthesize Synonyms
  ├── Generate 2-4 authoritative quoted phrases per component.
  ├── Bridge disciplinary jargon and expand acronyms.
  └── Enforce syntactic hygiene (no wildcards, valid quotes).

Step 3: Construct Dual-Tier Queries & CLI Ingestion String
  ├── Tier 1 (Mandatory Search Block): (C_synonyms) AND (I_synonyms)
  ├── Tier 2 (Refined Diagnostic Block): (C_synonyms) AND (I_synonyms) AND (M_synonyms)
  ├── Derive canonical topic slug: cimo-<kebab-case-slug>
  └── Format executable CLI command: search "<Tier 1 Query>" -k 10 --topic cimo-<slug>

Step 4: Formulate Screening Protocol
  └── Define explicit inclusion/exclusion rules using M and O for title/abstract screening.
```

### 5.2 Complete Few-Shot Exemplars

#### Exemplar 1: Multi-Agent Software Engineering & Consensus
- **User Prompt**: *"我想了解用多个大模型智能体协同做软件工程和复杂代码生成的机制，特别是它们怎么通过辩论或投票达成共识减少错误，想收集一些顶级论文。"*

**1. CIMO Structural Decomposition**
- **Context ($C$)**: Software engineering, automated program synthesis, complex code generation.
- **Intervention ($I$)**: Multi-agent systems, collaborative LLM agents, agentic workflows.
- **Mechanisms ($M$)**: Adversarial debate, voting consensus, peer review, self-reflection.
- **Outcomes ($O$)**: Error reduction, hallucination mitigation, code syntax validity, benchmark performance.

**2. Academic Vocabulary & Synonym Clusters**
- $C$ (Context): `"software engineering"`, `"code generation"`, `"program synthesis"`
- $I$ (Intervention): `"multi-agent systems"`, `"LLM agents"`, `"collaborative agents"`
- $M$ (Mechanisms): `"multi-agent debate"`, `"consensus mechanism"`, `"peer review"`, `"self-reflection"`
- $O$ (Outcomes): `"error reduction"`, `"code correctness"`, `"pass@k"`

**3. Dual-Tier Query Construction**
- **Tier 1 (High Recall / Broad Scoping Search Block - $C \land I$)**:
  ```text
  ("software engineering" OR "code generation" OR "program synthesis") AND ("multi-agent systems" OR "LLM agents" OR "collaborative agents")
  ```
- **Tier 2 (Refined Diagnostic Query - $C \land I \land M$)**:
  ```text
  ("software engineering" OR "code generation") AND ("multi-agent systems" OR "LLM agents") AND ("multi-agent debate" OR "consensus" OR "peer review")
  ```

**4. Platform Adaptation & Execution Command**
- **Semantic Scholar Translated Stream**:
  `"software engineering" "code generation" "program synthesis" "multi-agent systems" "LLM agents" "collaborative agents"`
- **OpenAlex Translated Stream**:
  `"software engineering" "code generation" "program synthesis" "multi-agent systems" "LLM agents" "collaborative agents"`
- **Topic Collection**: `research/cimo-multi-agent-code-generation`
- **CLI Command**:
  ```bash
  search '("software engineering" OR "code generation" OR "program synthesis") AND ("multi-agent systems" OR "LLM agents" OR "collaborative agents")' -k 10 --topic cimo-multi-agent-code-generation
  ```

**5. Screening Eligibility Protocol (Stage 2)**
- *Include*: Papers evaluating multi-agent interactions with explicit consensus, debate, or review protocols ($M$).
- *Exclude*: Single-agent prompting techniques (e.g., standard zero-shot CoT); studies lacking empirical code execution benchmarks ($O$).

---

#### Exemplar 2: Parameter-Efficient Fine-Tuning in Clinical NLP
- **User Prompt**: *"How to fine-tune medical foundation models with PEFT/LoRA without forgetting general clinical knowledge under low compute?"*

**1. CIMO Structural Decomposition**
- **Context ($C$)**: Clinical medicine, healthcare informatics, medical NLP, edge/resource-constrained computing.
- **Intervention ($I$)**: Parameter-efficient fine-tuning (PEFT), low-rank adaptation (LoRA), adapter modules.
- **Mechanisms ($M$)**: Low-rank matrix decomposition, weight freezing, catastrophic forgetting mitigation.
- **Outcomes ($O$)**: Clinical diagnostic accuracy, general knowledge retention, memory footprint reduction.

**2. Academic Vocabulary & Synonym Clusters**
- $C$ (Context): `"clinical NLP"`, `"medical language models"`, `"healthcare informatics"`
- $I$ (Intervention): `"parameter-efficient fine-tuning"`, `"PEFT"`, `"LoRA"`, `"low-rank adaptation"`
- $M$ (Mechanisms): `"catastrophic forgetting"`, `"weight freezing"`, `"representation stability"`
- $O$ (Outcomes): `"retention"`, `"diagnostic accuracy"`, `"memory efficiency"`

**3. Dual-Tier Query Construction**
- **Tier 1 (High Recall Scoping Block - $C \land I$)**:
  ```text
  ("clinical NLP" OR "medical language models" OR "healthcare") AND ("parameter-efficient fine-tuning" OR "PEFT" OR "LoRA" OR "low-rank adaptation")
  ```
- **Tier 2 (Refined Diagnostic Query - $C \land I \land M$)**:
  ```text
  ("clinical NLP" OR "medical language models") AND ("parameter-efficient fine-tuning" OR "LoRA") AND ("catastrophic forgetting" OR "weight freezing")
  ```

**4. Platform Adaptation & Execution Command**
- **Semantic Scholar Translated Stream**:
  `"clinical NLP" "medical language models" "healthcare" "parameter-efficient fine-tuning" PEFT LoRA "low-rank adaptation"`
- **OpenAlex Translated Stream**:
  `"clinical NLP" "medical language models" "healthcare" "parameter-efficient fine-tuning" PEFT LoRA "low-rank adaptation"`
- **Topic Collection**: `research/cimo-peft-clinical-nlp`
- **CLI Command**:
  ```bash
  search '("clinical NLP" OR "medical language models" OR "healthcare") AND ("parameter-efficient fine-tuning" OR "PEFT" OR "LoRA" OR "low-rank adaptation")' -k 10 --topic cimo-peft-clinical-nlp
  ```

**5. Screening Eligibility Protocol (Stage 2)**
- *Include*: Empirical evaluations of parameter-efficient methods applied to clinical tasks reporting knowledge retention ($O$).
- *Exclude*: Full parameter fine-tuning; non-medical benchmarks; theoretical papers without empirical validation.

---

## 6. Implementation Summary & Checkpoint Verification

| Component | Standard Implemented | Verification Method |
| :--- | :--- | :--- |
| **Framework Decomposition** | CIMO (Denyer et al. 2008) replacing PICO for engineering reviews. | Verified structural alignment against Tricco et al. (2011). |
| **Recall / Sensitivity Strategy** | Mandatory $C \land I$ search block; $M \land O$ reserved for screening. | Conforms to OSF Registration Template & PRISMA-S guidelines. |
| **Vocabulary Expansion** | Academic English mapping, acronym pairing, wildcard prohibition. | Validated against PRESS search formulation rules. |
| **Platform Translation** | Quoted phrase preservation, operator stripping, slug generation. | Verified against `src/research_toolkit/discovery/query.py` unit test suite. |
| **Skill Portability** | Dual-tier query output and automated CLI command dispatch. | Formatted for direct integration into `skills/lit-scout/SKILL.md`. |

All codebase integrity checks (`./scripts/check.sh`: ruff, mypy, pytest) remain fully passing.
