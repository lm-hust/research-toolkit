# Coding Standards

Review standards for research-toolkit changes. Enforced during code review.

## Architecture & Seams

- **Deep API Clients**: Client classes (e.g., `ZoteroClient`) must be deep modules with narrow, expressive interfaces. They must accept domain models or complete entity dictionaries directly rather than forcing higher-level managers (`ZoteroManager`) to unpack wire payload fields (eliminates Feature Envy).
- **Private Member Encapsulation**: Strictly prohibit external access to private methods or attributes (leading `_`) across modules. Enforced mechanically via Ruff rule `SLF001`.
- **Unified Request Channel**: All outbound HTTP requests within a client must route through its unified request method (`_request`), ensuring centralized authentication, user agent tagging, header construction, and structured error handling.
- **Aggregator Resilience**: Public search engines (Semantic Scholar, OpenAlex) are prone to rate limits (HTTP 429) and bursts. Calls to external sources must degrade gracefully (warn and continue with available providers) rather than terminating the entire pipeline.
- **Mathematical Specification Precision**: Algorithmic rules for composite ranking, recency decay, and diversity penalties must specify exact piecewise mathematical definitions to prevent interpretation drift.

## External Writes & Recovery

- **Partial-success contracts**: Review failure reporting and restart behavior across every external write stage, including post-write verification. An error response is not proof that nothing was written; recovery must distinguish confirmed, uncertain and completed effects before retrying or deleting.
- **Capacity under eventual consistency**: Review capacity, ownership and cleanup together. Account for uncertain writes and stale reads; a successful delete and a failed delete must not be conflated. Test new mechanical regressions at the public seam rather than adding reminder-only steering rules.

## Zotero Domain Invariants

- **Personal Library Scope**: Endpoints must strictly target `/users/<user_id>/`. Group libraries are prohibited (see ADR-0002).
- **Non-destructive Collection Attachment**: Associating an existing library item with a target collection must use `PATCH /items/<key>` with `If-Unmodified-Since-Version` to append only `collections`. Never mutate or overwrite existing titles, abstracts, notes, user tags, or attachment links.
- **Deduplication Matching Hierarchy**: Match by canonical DOI first. Only fall back to normalized title when the candidate paper has no DOI. When a candidate has a DOI that is not found in the library, return `None` to prevent false positive title collisions.
- **Domain Vocabulary**: Strictly adhere to `CONTEXT.md` terms. Use "collection", never "folder".

## Skills & Agent Interface

- **Skill & Agent Capability Synchronization**: When CLI commands, options, or domain interfaces evolve (e.g., new ranking flags, export formats), associated agent skills under `skills/` (such as `lit-scout`) must be updated in tandem to map natural language intents to the new capabilities.

## Remote Gateway & Ingress Invariants

- **Perimeter Authentication**: All external gateway endpoints under `/api/v1/*` and `/mcp/*` must mandate Bearer Token authorization when `RESEARCH_TOOLKIT_API_KEY` is configured.
- **Headless Attachment Resolution**: On environments lacking local storage, full-text attachments must resolve non-destructively through `ZoteroClient.download_item_file` to local cache before blocking synthesis pipelines.

