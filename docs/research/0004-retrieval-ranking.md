# Research Report: Multi-Source Literature Retrieval, Deduplication & Composite Ranking (Issue #4)

**Context**: `lm-hust/research-toolkit#4` | Glossary conforming to `CONTEXT.md` (`PaperCandidate`, `ReviewPaper`, `Ranker`)

---

## 1. Semantic Scholar (S2) & OpenAlex Integration Insights

### 1.1 Semantic Scholar Graph API
- **Endpoint**: `GET https://api.semanticscholar.org/graph/v1/paper/search` (supports `query`, `publicationTypes=Review`, `openAccessPdf`, `minCitationCount`).
- **Fields**: `fields=paperId,title,abstract,year,citationCount,influentialCitationCount,publicationTypes,openAccessPdf,externalIds,venue,authors`.
- **Rate limits**: 1 RPS with free API key (`x-api-key: ...`). Unauthenticated is rate-limited heavily.

### 1.2 OpenAlex API
- **Endpoint**: `GET https://api.openalex.org/works` (supports `search`, `filter=type:review,publication_year:...`, `sort=relevance_score:desc`).
- **Abstract reconstruction**: OpenAlex returns `abstract_inverted_index`, which requires sorting token position integers to reconstruct plain text.
- **Journal metric**: `primary_location.source.summary_stats.2yr_mean_citedness` is mathematically identical to Clarivate JCR Impact Factor.

---

## 2. Metric Normalization & Composite Ranking Formula

1. **Age-adjusted Citation Velocity**:
   $$\text{Age}(p) = \max(Y_{\text{current}} - Y_{\text{pub}}(p), 1), \quad C_{\text{vel}}(p) = \frac{\text{citationCount}(p)}{\text{Age}(p)}$$
   $$S_{\text{cite\_raw}}(p) = \min\left(1.0, \frac{\ln(1 + C_{\text{vel}}(p))}{\ln(1 + 50.0)}\right)$$
   With `influentialCitationCount` bonus: $S_{\text{cite}} = 0.65 S_{\text{cite\_raw}} + 0.35 S_{\text{inf}}$.
2. **Venue Impact Factor Normalization**:
   $$S_{\text{venue}}(p) = \min\left(1.0, \frac{\ln(1 + \text{Metric}_{\text{venue}})}{\ln(1 + 20.0)}\right)$$
3. **Review Paper Bonus with Age Decay**:
   $$B_{\text{review}}(p) = 0.20 \cdot e^{-0.15 \cdot \max(0, \text{Age}(p) - 1)}$$
4. **Composite Score & Tiered Selection**:
   $$Score(p) = 0.40 S_{\text{rel}} + 0.35 S_{\text{cite}} + 0.25 S_{\text{venue}} + B_{\text{review}}$$
   **Two-tier selection**: Guarantees top 20-30% slots for leading ReviewPapers, followed by top composite breakthrough research papers.

---

## 3. Deduplication Pipeline
- 3-tier cascade: (1) Canonical DOI $\to$ (2) ArXiv ID $\to$ (3) Fuzzy Title (Levenshtein $\ge 0.90$ with $|Year_1 - Year_2| \le 1$).
- Merge rules: Keep max citations, longer abstract, union external IDs, and mark `is_review` if tagged by either platform.
