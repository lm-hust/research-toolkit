# 2. Obsidian PKM Memory Distillation & Zotero Personal Library Routing

We integrate research discovery and NotebookLM grounded synthesis with the user's Obsidian PKM vault (`/home/ling/vault/PKM`) following `conversation-memory-protocol.md`.

## Context
Research literature and AI-assisted analysis must become durable long-term memory rather than transient chat logs. The user maintains an Obsidian vault synced via `obsidian-sync.service` (`ob sync --continuous`) with structured schemas:
- `10-wiki/References/papers/`: Canonical literature cards (`YYYY-FirstAuthor-ShortTitle.md`).
- `90-staging/`: L2 candidate knowledge packets (`memory-candidate.md`).
- `30-projects/<slug>/`: Domain project synthesis.
- `20-journal/`: Daily notes stream.
- `/home/ling/vault/PKM/log.md`: Append-only sync audit trail.

Historically, some references were placed in a group library (`cyber9`, group `5343279`). All AI-driven Zotero operations must be isolated exclusively within the user's **personal library** (`users/<user_id>`).

## Decision
1. **Zotero Target**: All AI toolkit items and URI links target the user's personal library (`zotero://select/users/<user_id>/items/<key>` and `zotero://open-pdf/users/<user_id>/items/<pdf_key>`).
2. **Staged Note Lifecycle**:
   - **Discovery Stage**: Generates `paper-screen.md` cards (`read_depth: screen`) in `10-wiki/References/papers/`.
   - **Grounded Q&A Stage**: Synthesized takeaways with verbatim quotes (`DistilledEvidence`) from NotebookLM are routed as candidate packets (`90-staging/<slug>.md`) using `memory-candidate.md`, with optional promotion to `paper-deep.md`.
3. **Project Linking**: CLI accepts an optional `--project <slug>` parameter, automatically injecting bi-directional links (`[[30-projects/<slug>/project-overview|Project]]`).
4. **Safety & Audit Guard**: Supports `--dry-run`, and automatically appends a timestamped audit entry to `/home/ling/vault/PKM/log.md` upon file writes.

## Consequences
- Preserves vault boundary integrity: raw chat transcripts are never dumped directly into PKM.
- Prevents cross-contamination with shared Zotero group libraries by strictly scoping to personal library.
- Enables seamless bi-directional desktop navigation between Obsidian notes and Zotero PDF annotations.
