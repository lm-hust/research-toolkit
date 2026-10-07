# 5. Citation Snowballing, Graph Topology Ranking, and Interactive Curation Checkpoint

We upgrade the literature discovery engine with bidirectional 1-hop citation snowballing, graph topological ranking, and an interactive terminal CurationCheckpoint.

## Context
Standard keyword literature search retrieves coarse candidate seeds that often miss seminal foundational works (which do not match specific keyword tokens) or latest derivative SOTA advancements. Researchers traditionally rely on external closed-source web tools (such as ResearchRabbit) to manually browse citation graphs, resulting in fragmented workflows and context switching. Furthermore, the existing `FulltextCheckpoint` functioned only as a PDF file-availability gate rather than a scientific relevance curation gate.

## Decision
1. **Bidirectional 1-Hop Citation Snowballing (`CitationSnowballer`)**:
   - Backward Snowballing: Extract `referenced_works` across seed candidates via OpenAlex batch pipe queries (`filter=openalex:W1|W2|...`). Compute co-citation frequencies ($co\_count$). Works co-cited by multiple seeds are promoted to `[Foundational]`.
   - Forward Snowballing: Query citing literature via OpenAlex `filter=cites:seed1|seed2|...`. Compute bibliographic coupling strength based on seed references. Multi-seed citing works are promoted to `[Recent Advancement]`.
   - Crossref Fallback: Use `CrossrefClient` for authoritative DOI verification and reference reconciliation for works with delayed OpenAlex indexing.
2. **Topological Multi-Modal Ranking (`Ranker`)**:
   - Extend `Ranker.score()` with a topological centrality component $s_{\text{topo}}$:
     $$s_{\text{topo}} = \min\left(1.0, \frac{\ln(1 + \text{co\_citation\_count})}{\ln(1 + \text{topo\_cap})}\right)$$
   - Composite score formula:
     $$\text{Composite} = w_{\text{rel}} \cdot S_{\text{rel}} + w_{\text{cite}} \cdot S_{\text{cite}} + w_{\text{venue}} \cdot S_{\text{venue}} + w_{\text{topo}} \cdot S_{\text{topo}} + B_{\text{review}}$$
   - Add `--sort topological` to prioritize papers by graph centrality and co-citation overlap.
3. **Interactive CurationCheckpoint**:
   - Provide a high-density interactive terminal review table displaying topological role tags (`[Foundational]`, `[Recent Advancement]`, `[Seed]`), co-citation counts, and scores before writing to `ZoteroCollection`.

## Consequences
- Transforms raw keyword search into a topological core literature discovery engine.
- Bridges the gap between automated retrieval and human scientific judgment prior to PDF downloading.
- Eliminates dependency on external third-party closed tools like ResearchRabbit for citation graph snowballing.
