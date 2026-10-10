---
name: gemini-notebook
description: Gemini Notebook (NotebookLM) queries and syncs. Use when the user names a Gemini Notebook or NotebookLM notebook (e.g. "问一下 Identity", "ask intelligence-per-kwh") to ask, search, list or summarise its sources; to sync Zotero collections into a notebook; or to batch-skim a notebook's papers into Zotero notes.
---

# Gemini Notebook

Queries go straight to the `notebooklm` CLI (notebooklm-py 0.8.4). Syncing and batch skimming are `research-toolkit` commands; see [`references/toolkit-commands.md`](references/toolkit-commands.md) when the user asks to sync a collection or skim papers.

## Running commands

Run every command from the research-toolkit checkout, with this prefix:

```bash
uv run notebooklm --backend android <command> ...
```

- `--backend android` is the measured setup; the CLI does not read the repo's `.env`, and its own default backend is `web`.
- Auth is the profile master token (`~/.notebooklm/profiles/default/master_token.json`). If `NOTEBOOKLM_AUTH_JSON` is set it shadows that token: run with `env -u NOTEBOOKLM_AUTH_JSON`. Never write it into any `.env`.
- Add `--json` to every query and parse stdout. Errors come back as `{"error": true, "code": ..., "message": ...}` with a non-zero exit.

## Query steps

### 1. Pin the notebook

```bash
uv run notebooklm --backend android list --json
```

Match the user's name against `notebooks[].title` **exactly**. One match: take its full `id` as `<UUID>`. No match, or several notebooks with that title: show the candidates (title, id, created_at) and let the user pick.

From here on every command carries `-n <UUID>` with the full UUID. `-n` accepts unique prefixes and matches them silently (`-n 7` lands on Identity), and without `-n` the CLI falls back to the `notebooklm use` context or `NOTEBOOKLM_NOTEBOOK`; the full UUID is what pins the right notebook.

Done when: you hold one full UUID that the user's name matched exactly, or the user chose it.

### 2. Choose the command

| The user wants | Command | Cost |
|---|---|---|
| where something is said, a quote, a claim verified | `source search` | ~5 s, writes nothing |
| a summary, explanation, comparison | `ask` | 1–1.5 min; tell the user before sending |
| a list or a count ("which papers", "how many") | `source list`, then count titles | seconds |
| what the notebook is about | `summary` (`--topics` for suggested topics) | seconds |
| ideas for what to ask | `suggest-prompts` (`--query` to steer) | seconds |
| the conversation so far | `history --json` | seconds |

Unsure between search and ask: search first. `ask` misses items in lists and can present plans as results, so lists and counts always come from source titles.

```bash
uv run notebooklm --backend android source search "<query>" -n <UUID> --limit 8 --json
uv run notebooklm --backend android source list -n <UUID> --json
uv run notebooklm --backend android ask "<question>" -n <UUID> --json
uv run notebooklm --backend android summary -n <UUID> --json
uv run notebooklm --backend android suggest-prompts -n <UUID> --json
uv run notebooklm --backend android history -n <UUID> --json
```

`source search` returns passages with `source_id`, `text` and `rank`. Map `source_id` to a title through `source list`.

### 3. Keep the conversation

Each notebook has one server-side current conversation, the one the user sees on the web. `ask` without `-c` continues it; that is the default.

- After the first `ask`, record `conversation_id` from its JSON. Every follow-up in this session passes `-c <conversation_id>`.
- `--new` **deletes** the current conversation before asking, irreversibly, and `--json` skips its confirmation prompt. Use it only when the user explicitly asks for a fresh conversation, and only after telling them their existing conversation (including what they see on the web) will be deleted, and getting a yes.

### 4. Narrow to one paper

When the user names a paper, find it in `source list` by title. One match: `ask ... -s <source_id>`. Several: let the user pick. `-s` accepts any id without checking it belongs to the notebook, so take the id from this notebook's list. `source search` takes the same `-s`.

### 5. Relay the answer

`ask --json` returns `answer` with inline `[n]` markers and `references[]` (`source_id`, `citation_number`, `cited_text`).

- Relay Gemini **faithfully**: compress, never change the meaning. Mark anything you add yourself as **Claude 补充**.
- Replace each `[n]` (and each range such as `[1-3]`) with the titles of the sources whose `citation_number` falls in it, looked up through `source list`. Zotero-synced titles read `[KEY] Title`; keep the `[KEY]`.
- Give `cited_text` when the user asks for the original wording.
- Leave out page numbers; Gemini's page numbers are unreliable. Provenance is the source title plus `cited_text`.

## Write boundary

Querying writes only the conversation history that `ask` itself creates. Sources and notebooks change only through `research-toolkit sync-notebook` (see the reference), never through `notebooklm source add/delete/rename`, `create`, `delete` or `rename`. Saving to the notebook (`ask --save-as-note`, `history --save`) happens only when the user explicitly asks for it.

## Toolkit commands

- "Put collection X into a notebook", "sync X to NotebookLM": `research-toolkit sync-notebook`.
- "Skim these papers", "初读一下这个笔记本", "which of these are relevant to Q": `research-toolkit skim-notebook`. Skim saves the notebook's existing conversation as a notebook note before clearing it, then reads each paper in its own fresh conversation.

Options, the plan-first flow, and how to read their JSON reports: [`references/toolkit-commands.md`](references/toolkit-commands.md).
