# Zotero Integration & Full-text PDF Resolution Architecture Report (Issue #3)

This report investigates the Zotero integration strategy, full-text PDF resolution via UCL institutional access, duplicate reconciliation, and concrete implementation architecture for `research-toolkit`, adhering to the domain model in `CONTEXT.md`.

---

## 1. Web API (`pyzotero`) vs. Local SQLite (`zotero.sqlite`) vs. Local Storage (`~/Zotero/storage/<key>/`)

| Dimension | Zotero Web API (`pyzotero` / REST) | Local SQLite (`zotero.sqlite`) | Local Storage (`~/Zotero/storage/<key>/`) | Proposed Hybrid Model |
| :--- | :--- | :--- | :--- | :--- |
| **Reading `ZoteroCollection`s** | **Pros**: Official, versioned API; works across environments (local desktop, remote server, Docker); respects user vs group permissions; returns structured JSON with full hierarchy and tags.<br>**Cons**: HTTP network latency; rate limits (`Retry-After` headers); requires internet & API key. | **Pros**: 0ms latency; works offline; fast relational SQL queries.<br>**Cons**: Concurrency locks if Zotero Desktop is running (requires `file:...sqlite?immutable=1` or `query_only`); schema instability across major Zotero versions (v6 to v7 changes in annotations/items); bypasses sync state. | **N/A**: Filesystem storage only contains raw attachment directories keyed by 8-character attachment item key; contains no collection metadata. | **Web API (Primary)** for reading collection metadata, with optional read-only SQLite acceleration if running purely offline on local desktop. |
| **Inserting `PaperCandidate`s** | **Pros**: The **only officially supported and safe write path**; automatically generates 8-char keys; validates item schemas; updates Zotero sync engine so records immediately sync down to the user's Zotero Desktop GUI.<br>**Cons**: Requires network & write-enabled API key. | **Cons**: **STRICTLY DISCOURAGED & DANGEROUS**. Writing directly to `zotero.sqlite` corrupts full-text search indices, sync state vectors, and trigger caches, causing catastrophic sync conflicts and database locks in the desktop client. | **N/A**: Cannot write metadata directly to filesystem storage. | **Web API Exclusively** for creating collections and inserting `PaperCandidate` records. Never write directly to `zotero.sqlite`. |
| **Locating PDF Files** | **Pros**: Endpoint `GET /items/<key>/file` allows remote downloads.<br>**Cons**: Strictly gated by Zotero Cloud Storage quota (free tier is capped at **300 MB**); many users do not pay for storage or sync attachments to the cloud, resulting in 404/quota errors. | **Pros**: Relational lookup in `itemAttachments` table (`path LIKE 'storage:%'`).<br>**Cons**: Redundant overhead if the attachment item key is already retrieved via metadata. | **Pros**: Direct local filesystem access (`~/Zotero/storage/<attachment_key>/*.pdf`); instantaneous; completely bypasses cloud storage quota limits.<br>**Cons**: Requires the toolkit to run on the machine hosting the Zotero data directory. | **Hybrid Resolution**: Extract attachment keys via metadata; check local storage directory `~/Zotero/storage/<attachment_key>/` first (0 download cost, unlimited size); fall back to Web API file download if running headless or remotely. |

### Architectural Recommendation: The Hybrid Architecture
1. **Metadata Operations & Paper Insertion**: Use the **Zotero Web API** (via `pyzotero` or standard library HTTP client). This guarantees data integrity, schema validation, and bidirectional synchronization with the Zotero desktop app.
2. **Local Storage Fast-Path for PDFs**: When resolving PDFs for downstream `NotebookLMGateway` ingestion, probe `~/Zotero/storage/<attachment_key>/` directly on disk. This avoids downloading multi-megabyte PDFs over HTTP and avoids hitting Zotero's 300MB cloud quota limit.
3. **Graceful Fallback**: If local storage is absent (e.g. running on a cloud VM or remote worker), fall back to `GET /items/<key>/file` via Web API.

---

## 2. Implementing the `FulltextCheckpoint`

### Conceptual Workflow Boundary
As defined in `CONTEXT.md`, the **`FulltextCheckpoint`** is the workflow boundary between paper insertion and NotebookLM synchronization:
```
[Discovery & Ranker] 
        │ (insert PaperCandidates)
        ▼
[ZoteroCollection] ◄────── Tagged: checkpoint/awaiting-fulltext
        │
   ═════╪═════════════════════════════════════════════════════════════════
        │  FulltextCheckpoint: Manual / Semi-automated Resolution
        │  - Automated OA resolution (Unpaywall / OpenAlex)
        │  - UCL Institutional Access (EZproxy / Zotero Connector)
        │  - Zotero Desktop "Find Available PDFs"
   ═════╪═════════════════════════════════════════════════════════════════
        │
        ▼ (FulltextCheckpoint verify & scan)
[Resolved Local PDFs]
        │
        ▼ (upload as NotebookSource)
[NotebookLMGateway]
```

### Institutional PDF Access Mechanics (UCL EZproxy & Zotero Connector)
1. **UCL EZproxy Direct Link Generation**:
   Paywalled publishers require institutional authentication. UCL operates an EZproxy prefix:
   $$\text{Proxy URL} = \texttt{https://libproxy.ucl.ac.uk/login?url=https://doi.org/\{doi\}}$$
   When `FulltextCheckpoint` scans a `ZoteroCollection` and identifies missing PDFs, it generates these ready-to-click URLs. Opening this URL routes the user through UCL Single Sign-On (Shibboleth/OpenAthens) directly to the licensed PDF.
2. **Zotero Connector Role**:
   Once on the proxied publisher page, the user clicks the **Zotero Connector** extension in their browser. Connector captures the high-resolution publication metadata and downloads the full-text PDF into the target `ZoteroCollection`.
3. **Zotero Desktop "Find Available PDFs" Limitation**:
   The built-in desktop "Find Available PDFs" tool **does not** route through HTTP EZproxy (`libproxy.ucl.ac.uk`). It can only resolve institutional gated content if the user is connected to the **UCL VPN** or physically on the campus network. For off-campus access without VPN, the Zotero Connector + EZproxy link is the reliable method.

### Checkpoint Scanning Algorithm
1. Retrieve all top-level items in the target `ZoteroCollection`.
2. Retrieve all child attachments (`itemType == "attachment"`, `contentType == "application/pdf"`).
3. Associate each item with its PDF attachment key.
4. Verify whether the PDF exists locally in `~/Zotero/storage/<attachment_key>/<filename>.pdf` or is downloadable via Web API.
5. Partition collection into:
   - `ready`: Items with validated local PDF files ready for `NotebookSource` upload.
   - `missing`: Items lacking PDF attachments, formatted with title, authors, DOI, and the UCL EZproxy resolution link.
   - `duplicates`: Reconciled duplicate records.

---

## 3. Duplicate Items Reconciliation

### Why Duplicates Occur
When a user manually resolves a paper by visiting the UCL EZproxy page and clicking Zotero Connector, Zotero Connector typically **creates a new parent item** in the collection rather than modifying the skeleton `PaperCandidate` previously inserted by the toolkit.
- **Item A (Toolkit)**: Has initial normalized metadata, scored relevance tier, tag `checkpoint/awaiting-fulltext`, but **no PDF**.
- **Item B (Connector)**: Has publisher metadata, snapshot HTML, and **full-text PDF attachment**, but lacks toolkit tags.

### Reconciliation Strategy
1. **Canonical Identifier Extraction**:
   - Normalize DOI: Strip `https://doi.org/`, trim, lowercase (`10.1038/s41586-021-03819-2`).
   - Fallback: If no DOI exists, compute normalized Title Key: lowercased, stripped of non-alphanumeric characters + publication year.
2. **Grouping / Clustering**:
   - Group items in the collection by `canonical_doi` (or title key).
3. **Winner Selection & Attachment Propagation**:
   - In each duplicate cluster, select the **Winner Item** (the item holding a valid PDF attachment).
   - If Item B (Connector) has the PDF, the toolkit:
     a. Adopts Item B's PDF attachment as the canonical file for downstream `NotebookSource` upload.
     b. Merges tags (copying `PaperCandidate` tracking tags onto Item B).
     c. Marks Item A with tag `checkpoint/duplicate-superseded` (or removes it from the collection via API if auto-clean is enabled).
