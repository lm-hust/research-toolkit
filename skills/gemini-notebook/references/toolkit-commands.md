# sync-notebook and skim-notebook

Both run from the research-toolkit checkout as `uv run research-toolkit <command>`. stdout is one JSON report; progress goes to stderr. A run-level failure exits 1 with `Error: ...` on stderr and no report; relay that message. Failures of single papers do not stop a run: they land in the report's `failed[]`, each with an `error`.

## sync-notebook: Zotero collections into a notebook

Each Zotero item becomes one source titled `[KEY] Title`, from its first PDF, else an EPUB, else its HTML snapshot converted to markdown. A source counts as already synced by its `[KEY]` prefix alone, so re-running uploads only what is new and resumes an interrupted run.

| Option | Use |
|---|---|
| `-c, --collection` | collection name or key; repeat for several collections (then `--notebook` is required) |
| `--notebook` | UUID or exact title. Omitted: the notebook titled like the collection, created if missing. A title matching several notebooks is an error that lists their UUIDs |
| `--recursive` | include subcollections |
| `--replace KEY` | delete that key's source and upload it again (e.g. a new PDF version); repeatable |
| `--dry-run` | plan only, write nothing |
| `--force` | sync into a notebook whose sources mostly lack `[KEY]` titles |
| `--allow-url` | items with no PDF/EPUB/snapshot let Gemini fetch the DOI/URL, which may only get a paywall page |

**Plan first.** Run `--dry-run`, show the user the plan (counts of `added`, `skipped_existing`, `missing_fulltext`, `orphaned`, and `projected_source_count`), and run for real after they agree. Uploads take about 10 s per paper.

**Hand-maintained notebooks.** The Identity Notebook is maintained by hand and is never synced. `--force` is for a notebook the user confirms is meant to receive Zotero papers.

Report fields:

- `notebook_id`, `notebook_title`, `created` (the run created the notebook), `dry_run`.
- `aborted_reason`: non-null means nothing was uploaded: the notebook looks hand-maintained, or it would exceed 300 sources. Relay the reason.
- `added[]` (`key`, `title`, `kind`: `pdf|epub|html|url`); in a dry run, what would be uploaded.
- `replaced[]`, `skipped_existing[]`, `renamed[]` (titles the server reset to the filename and the run renamed back).
- `missing_fulltext[]`: items with nothing to upload; the user needs to add a full text in Zotero (or rerun with `--allow-url`).
- `orphaned[]` (`key`, `title`, `source_id`): sources in the notebook that are not in the given collections. Reported only, never deleted.
- `failed[]` (`key`, `title`, `error`): rerun to retry them.
- `extra_attachments[]` (`key`, `title`, `count`): items with more attachments than the one uploaded (supplements were not synced).
- `source_count`, `projected_source_count`: sources now, and after this run.

## skim-notebook: batch first read into Zotero notes

For each `[KEY]` source: one structured question restricted to that source, in a fresh conversation, written as a Zotero child note "Gemini 初读：<title>" tagged `gemini-skim/ai-note`. Before the first paper it saves the notebook's existing conversation as a notebook note ("Chat History (saved <date>)"), then clears it; tell the user that their web conversation will be moved into that note. About 1 minute per paper. No Obsidian writes. Skim is for screening; papers worth replicating go to `zotero-deep-read`.

| Option | Use |
|---|---|
| `--notebook` | UUID or exact title (required) |
| `--key` | only these Zotero keys; repeatable. Default: every `[KEY]` source |
| `--focus "<question>"` | also rate relevance high/medium/low and tag the Zotero item `gemini-skim/relevance:<level>` |
| `--refresh` | re-read papers that already have a skim note (rewrites the same note) |
| `--yes` | go on even when the quota looks too small |

**Quota.** Without a terminal the run stops before skimming when the quota looks short, with `Error: Stopped before skimming...` and the shortfall on stderr. Relay the numbers; rerun with `--yes` only after the user agrees. An interrupted run resumes on rerun (skimmed papers are skipped).

Report fields:

- `notebook_id`, `notebook_title`, `saved_history_note` (the existing conversation was saved as a notebook note).
- `written[]`, `updated[]` (`key`, `title`, `source_id`, `note_key`, plus `relevance` with `--focus`).
- `skipped[]` (already had a skim note; `note_key`), `failed[]` (`error`).
- `relevance`: counts for `high`, `medium`, `low`, `unparsed` (level not readable; no tag set).
- `quota_before` (`window`, `remaining_percent`, `resets_at`, `needed_percent`), `quota_after`; null when the usage meter is unavailable.

With `--focus`, lead the summary with the `high` papers; they are the deep-read candidates.
