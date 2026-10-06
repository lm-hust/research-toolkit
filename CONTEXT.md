# Research Toolkit

A modular Python & CLI toolkit for literature discovery, Zotero library synchronization, NotebookLM gateway interaction, and Obsidian PKM knowledge distillation.

## Language

### Discovery & Ranking

**PaperCandidate**:
A normalized bibliographic record retrieved from Semantic Scholar or OpenAlex, scored for relevance, citation impact, and journal quality.
_Avoid_: Search result, paper item, doc

**ReviewPaper**:
A peer-reviewed survey, systematic review, or meta-analysis, tagged with high-priority ranking tier.
_Avoid_: Survey paper, overview doc

**Ranker**:
The scoring component that computes composite weightings across citation count, journal impact proxy (OpenAlex 2-year citedness / JCR lookup), and review tier.
_Avoid_: Sorter, filter

**VenueRegistry**:
The offline repository of top-tier academic journals (Nature, Science, IEEE Trans) and premier computer science conferences (NeurIPS, CVPR, ICLR), mapping aliases to standardized impact factor metrics.
_Avoid_: Journal list, conference DB


### Literature Management

**ZoteroCollection**:
A designated target collection within the user's Zotero personal library storing PaperCandidates for a specific topic or task.
_Avoid_: Folder, category, tag

**FulltextCheckpoint**:
The workflow boundary between paper insertion and NotebookLM synchronization, allowing automated open-access resolution or manual UCL institutional PDF collection.
_Avoid_: PDF wait, sync pause

### Notebook & Gateway

**NotebookLMGateway**:
The client abstraction managing authentication, notebook lifecycle, PDF source uploading, and grounded Q&A against Google NotebookLM.
_Avoid_: Gemini bot, AI client

**NotebookSource**:
A full-text PDF document successfully attached to a NotebookLM notebook for grounded synthesis.
_Avoid_: Attachment, uploaded file

### PKM & Synthesis

**DistilledEvidence**:
A structured takeaway, claim, or citation extracted from NotebookLM interactions, formatted for ingestion into Obsidian PKM.
_Avoid_: Chat log, summary snippet
