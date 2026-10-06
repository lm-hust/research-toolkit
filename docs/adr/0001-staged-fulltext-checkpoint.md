# 1. Staged CLI Workflow with FulltextCheckpoint

We separate literature discovery (`search`) from NotebookLM ingestion (`sync-notebook`) using an explicit `FulltextCheckpoint`.

## Context
Automated research pipelines typically attempt end-to-end ingestion from keyword search directly to LLM context. However, academic literature is heavily fragmented across open-access repositories and institution-licensed paywalls (such as UCL library subscriptions). Automated scrapers attempting to bypass university SSO fail due to multi-factor authentication (MFA).

## Decision
1. `research-toolkit search` inserts metadata and automatically downloads available Open Access PDFs into a designated `ZoteroCollection`.
2. Execution halts at `FulltextCheckpoint` if paywalled papers lack PDFs. The CLI surfaces clickable UCL EZproxy links (`https://libproxy.ucl.ac.uk/login?url=https://doi.org/{doi}`).
3. The user authenticates in their browser, downloads the full text via Zotero Connector, and the toolkit automatically clusters duplicate entries by canonical DOI, adopting the full-text attachment.
4. `research-toolkit sync-notebook` verifies PDF availability, reconciles duplicates, and uploads local files to Google NotebookLM.

## Consequences
- Guarantees zero failures from institutional MFA blocks.
- Eliminates reliance on Zotero cloud storage quota by probing local storage paths.
- Provides a human-in-the-loop checkpoint where researchers can inspect, prune, or add papers before LLM ingestion.
