# 8. Gemini Notebook: Sync in the Toolkit, Queries via the CLI

Status: accepted (2026-10-09, decided in lm-hust/research-toolkit#51, map #47)

Agents work with Gemini Notebook in two ways. Syncing a Zotero collection or local folder into a notebook is one `research-toolkit sync-notebook` command built on the notebooklm-py Python API. Everything interactive (`ask`, `source search`, `list`, `history`) is called by skills directly through the `notebooklm` CLI. The `synthesis/` package and its gateway abstraction are deleted.

## Context
`synthesis/` defined a `NotebookLMGateway` protocol with two adapters, and neither did real work:
- `NotebookLMPyAdapter` never called notebooklm-py. It made up notebook and source IDs and returned a template answer.
- `GeminiGroundingFallbackAdapter` sent the Gemini API only the prompt, never the sources, so its "grounded" answers and citations had nothing to do with the papers.

Live testing of notebooklm-py 0.8.4 (#49, local branch `research/notebooklm-cli-capabilities`) showed that syncing has failure modes that need real handling:
- `--title` reports success, but the server can later reset the title to the filename.
- `UNCONFIRMED_WRITE` can leave a source stuck in `preparing`.
- The per-notebook source cap gives no specific error.
- Each upload takes 7–18 s.

Querying, by contrast, is a single CLI call. Wrapping it would add nothing.

## Decision
1. **Sync lives in the toolkit.** `sync-notebook` keeps its name and gets a real implementation in a new `src/research_toolkit/notebook/` package, on the notebooklm-py **Python API** (typed, raises exceptions, mockable). It does not shell out to the CLI, whose JSON output has no stability guarantee. The parameters and incremental behaviour are specified separately (#52).
2. **Queries go straight to the CLI.** The toolkit's `ask` command is removed. Skills call `notebooklm ask` / `source search` with a full notebook UUID and an explicit `-n`.
3. **`synthesis/` is deleted entirely**: the protocol, both adapters, and the `GroundedAnswer` / `DistilledEvidence` / `NotebookInfo` / `NotebookSource` dataclasses. The Gemini API fallback and `GEMINI_API_KEY` go with it.
4. **The frozen MCP gateway loses its two Gemini Notebook tools.** `sync_notebook` and `query_notebook` and their REST routes are removed, not rewired. Removal is not extension, so this stays within ADR-0007: a frozen feature whose backing module is deleted is removed along with it.
5. **`doctor` checks auth for real** through notebooklm-py, equivalent to `notebooklm auth check`, and warns when `NOTEBOOKLM_AUTH_JSON` is set, since it shadows the profile's master token.
6. Both paths pin `notebooklm-py[headless,android]==0.8.4`.

## Consequences
- There is one backend and no abstraction layer. A second backend would have to be added deliberately, not through a fallback.
- Skills depend on the `notebooklm` CLI surface directly, so a notebooklm-py upgrade means re-checking the skills as well as the sync command.
