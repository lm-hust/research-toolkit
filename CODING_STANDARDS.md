# Coding Standards

Review standards for research-toolkit changes. Enforced during code review.

## Architecture & Seams

- **Deep API Clients**: Client classes (e.g., `ZoteroClient`) must be deep modules with narrow, expressive interfaces. They must accept domain models or complete entity dictionaries directly rather than forcing higher-level managers (`ZoteroManager`) to unpack wire payload fields (eliminates Feature Envy).
- **Unified Request Channel**: All outbound HTTP requests within a client must route through its unified request method (`_request`), ensuring centralized authentication, user agent tagging, header construction, and structured error handling.
- **Aggregator Resilience**: Public search engines (Semantic Scholar, OpenAlex) are prone to rate limits (HTTP 429) and bursts. Calls to external sources must degrade gracefully (warn and continue with available providers) rather than terminating the entire pipeline.

## Zotero Domain Invariants

- **Personal Library Scope**: Endpoints must strictly target `/users/<user_id>/`. Group libraries are prohibited (see ADR-0002).
- **Non-destructive Collection Attachment**: Associating an existing library item with a target collection must use `PATCH /items/<key>` with `If-Unmodified-Since-Version` to append only `collections`. Never mutate or overwrite existing titles, abstracts, notes, user tags, or attachment links.
- **Deduplication Matching Hierarchy**: Match by canonical DOI first. Only fall back to normalized title when the candidate paper has no DOI. When a candidate has a DOI that is not found in the library, return `None` to prevent false positive title collisions.
- **Domain Vocabulary**: Strictly adhere to `CONTEXT.md` terms. Use "collection", never "folder".
