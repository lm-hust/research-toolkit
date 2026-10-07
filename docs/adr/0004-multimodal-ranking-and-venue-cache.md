# 4. Multimodal Literature Ranking, Dynamic Venue Impact Caching, and Metadata Persistence

We enhance the literature discovery pipeline with flexible multi-mode sorting, dynamic OpenAlex venue impact caching, and rich metadata persistence into Zotero.

## Context
Initial discovery implementations suffered from three structural limitations:
1. `Ranker` enforced a rigid 25% review quota placement that pushed emerging low-impact review papers ahead of seminal highly-cited research, while brand-new papers tied with zero citation velocity.
2. `VenueRegistry` relied strictly on a static 25-venue JSON file because OpenAlex `/works` does not return `summary_stats` in its default search payload, causing >90% of papers to receive a baseline penalty of `0.15`.
3. Ingestion into Zotero discarded citation counts and quality scores, preventing researchers from sorting or filtering papers by impact inside their reference library.

## Decision
1. **Dynamic Venue Impact Hybrid Resolution**:
   - Expand offline `venues.json` to 200+ top-tier venues across CCF A/B, JCR Q1, and premier transactions.
   - For unmapped venues with OpenAlex source IDs, dynamically query OpenAlex `/sources/{id}` for `2yr_mean_citedness` and cache responses in `~/.cache/research-toolkit/venues_cache.json` with a 30-day TTL.
2. **Multi-Mode Ranking & Filtering**:
   - Remove hard review slot lock-in. Reviews receive a composite boost (`beta_review = 0.20`) rather than positional override.
   - Support sorting modes via `--sort [composite|citations|recent]`.
   - Support hard qualification filters: `--min-cites <N>`, `--year <range>`, and `--peer-reviewed` (excluding pure preprints).
3. **Rich Metadata Persistence**:
   - `search` outputs the formatted candidate table by default.
   - Ingest `Citations: <count> | Influential: <count> | Score: <score>` into the Zotero item `extra` field.
   - Attach citation tier tags (`cites:>100`, `cites:>10`) and publication type tags (`type/peer-reviewed`, `type/preprint`).

## Consequences
- Significantly improves discovery relevance for both foundational classics and recent breakthroughs.
- Keeps network latency minimal via local caching of journal impact factors.
- Allows researchers to filter and organize discovered literature directly in the Zotero client by citation volume.
