# AGENTS.md

## Navigation pointers

### Architecture
- `src/research_toolkit/discovery/`: Multi-source literature query translation, API clients, deduplication, and ranking.
- `src/research_toolkit/zotero/`: Personal library sync, collection management, duplicate reconciliation, and full-text PDF resolution.
- `src/research_toolkit/synthesis/`: NotebookLM grounded synthesis and note exports.

### Standards & Review
- Coding standards: see `CODING_STANDARDS.md`.
- Domain docs: single-context (`CONTEXT.md` + `docs/adr/`). See `docs/agents/domain.md`.
- Issue tracker: GitHub issues via `gh` CLI. See `docs/agents/issue-tracker.md`.
- Verification: run `./scripts/check.sh` before commits.
