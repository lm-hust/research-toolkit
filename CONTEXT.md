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

**CitationSnowballer**:
The graph expansion engine that traverses 1-hop backward references (co-citation) and forward citations (bibliographic coupling) across OpenAlex and Crossref for a set of seed PaperCandidates.
_Avoid_: Paper crawler, link expander, spider

**VenueRegistry**:
The hybrid repository and caching layer mapping top-tier journals, CS conferences, and dynamic OpenAlex 2-year citedness metrics to standardized impact factors.
_Avoid_: Journal list, conference DB


### Literature Management

**ZoteroCollection**:
A designated target collection within the user's Zotero personal library storing PaperCandidates for a specific topic or task.
_Avoid_: Folder, category, tag

**CurationCheckpoint**:
The human-in-the-loop terminal boundary where expanded candidate papers from CitationSnowballer are presented with topological tags and composite ranks for interactive researcher screening before insertion.
_Avoid_: Paper picker, candidate selector

**FulltextCheckpoint**:
The subsequent workflow boundary between curated paper insertion and NotebookLM synchronization, resolving automated open-access PDFs or manual UCL institutional access.
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

### Remote Gateway & Ingress

**DualStackGateway**:
The unified daemon exposing both Model Context Protocol (MCP) Server-Sent Events (SSE) and OpenAPI 3.0 REST endpoints, protected by bearer token authentication.
_Avoid_: API server, web backend

**CloudStorageResolver**:
The cloud resolution mechanism pulling full-text PDF attachments from Zotero Cloud Storage via Web API on headless environments, eliminating local desktop filesystem prerequisites.
_Avoid_: Cloud sync, attachment puller

