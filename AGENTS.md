# AGENTS.md

## Navigation pointers

### Architecture
- `src/research_toolkit/discovery/`: Multi-source literature query translation, API clients, deduplication, and ranking.
- `src/research_toolkit/zotero/`: Personal library sync, collection management, duplicate reconciliation, and full-text PDF resolution.
- `src/research_toolkit/synthesis/`: NotebookLM grounded synthesis and note exports.
- `src/research_toolkit/config.py`: Environment loader with Git worktree fallback to parent `.env`.
- `src/research_toolkit/mcp/`: Dual-stack gateway (MCP and OpenAPI REST). Frozen and undeployed (ADR-0007); do not extend. Agents use the CLI.

### Standards & Review
- Coding standards: see `CODING_STANDARDS.md`.
- Domain docs: single-context (`CONTEXT.md` + `docs/adr/`). See `docs/agents/domain.md`.
- Issue tracker: GitHub issues via `gh` CLI. See `docs/agents/issue-tracker.md`.
- Verification: `./scripts/check.sh` (wired to `.githooks/pre-commit` via `core.hooksPath`).
- Skill sync: run `./scripts/sync-skills.sh` after editing skills under `skills/`.
