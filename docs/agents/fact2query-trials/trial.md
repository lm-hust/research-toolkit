# fact2query isolated consumer trial — runner only

These runner recipes live outside `skills/` so the consumer under test never installs or reads them. This file and its siblings ([recovery](recovery-trial.md), [revision](revision-trial.md)) are small manual behavioral recipes at the agent-loading seam, not text-assertion tests or an automated LLM harness. Every scenario is **fictional synthetic fixture replay**: no actual Notebook lookup, platform search, real research topic or live human approval. Report those categories separately as pending. Give the consumer only the next staged input, never a recipe or its oracle.

## Installation and actual loading

Install with [trial in an isolated destination](../skill-publication.md#trial-in-an-isolated-destination), selecting exactly `fact2query` and `gemini-notebook` and a new disposable target outside the source tree. Point the intended consumer at that target, or have it explicitly read the linked SKILL.md files and the references it reaches. Record the checkout path/revision, both link targets, the actual consumer identity, invocation, cwd and read/load evidence in a private outside-repo trial record. Do not spawn a substitute consumer when orchestration authority belongs to the parent.

## Non-trigger scenario: ordinary Notebook summary

Run a fresh consumer in a disposable outside-repo cwd with both trial skills available. Tell it to read each available SKILL.md's frontmatter description, load only the skills that apply, and replay supplied fictional responses instead of executing Notebook calls. Do not name fact2query.

Request: “Fixture replay, not live service access. Summarize what Gemini Notebook `Fictional Label Study` says about how museum labels are transcribed. A short paragraph is enough.”

On requested reads, supply the inventory, history and source list from the success scenario below. After the consumer announces the ask, supply this fictional answer, conversation `fictional-conversation-80`, references `[fictional-source-a]`:

> The notes describe optical recognition and manual transcription as alternative ways to transcribe labels; the optical method uses character recognition.

Oracle:

- The consumer loads gemini-notebook and does not start fact2query: no CIMO proposal, scope or block gate, search blocks, Boolean strings or platform queries.
- It pins the full UUID ending `080` and relays the answer as a Notebook summary attributed to its source.
- A one-line optional mention that query generation is available is acceptable; beginning that workflow is a fail.

This checks description-based routing by an instructed consumer, not the host's automatic skill selection.

## Synthetic success scenario

Run the actual consumer in a disposable outside-repo cwd. Explicitly instruct it to use checkout-backed fact2query plus gemini-notebook, and to **replay supplied fictional responses instead of executing Notebook/database calls**. Use a private output path in that cwd. The runner supplies fixture responses/decisions at the indicated stage; the consumer must still show its intended pinned calls, boundaries and gate prompts. Reading this fixture does not constitute obtaining a live confirmation.

### 1. Request and inventory

Request: “Use fact2query with Gemini Notebook `Fictional Label Study` to generate the three-platform English main and focused alternative queries. Continue the existing discussion; save the full artifact locally. This is fixture replay, not live service access.”

Fixture inventory (titles and full IDs; created date 2000-01-01 is fictional):

- Fictional Label Study — `00000000-0000-4000-8000-000000000080`
- Other Fictional Study — `00000000-0000-4000-8000-000000000079`

History fixture: conversation `fictional-conversation-80`, prior discussion asked whether method names should be alternatives rather than jointly required.

Source-list fixture for the pinned Notebook:

- `fictional-source-a`: **Imaginary label transcription bench notes**
- `fictional-source-b`: **Imaginary catalog matching protocol**

### 2. Evidence and Gemini CIMO

After the consumer announces ask effects/cost, supply this fictional Gemini response (conversation ID `fictional-conversation-80`):

> The scope is digitizing museum labels for catalog matching. Optical recognition and manual transcription are alternative methods. Character recognition is a mechanism for the optical method; no shared mechanism is established for both. Identification accuracy is an evaluation outcome, not evidence of a demonstrated accuracy improvement. The curator-review criterion may need screening rather than a metadata restriction.

Fixture structured references are **empty**. The response alone is not sufficient provenance. When the consumer requests source lookup, supply passages:

- `fictional-source-a`: “In this imaginary museum-label exercise, optical recognition and manual transcription are alternative ways to transcribe labels. The optical method uses character recognition. Identification accuracy is evaluated; these notes make no claim that one method improves accuracy.”
- `fictional-source-b`: “Catalog matching links transcribed label text to a catalog record. Each included exercise must have been reviewed by two curators. That review detail is not consistently present in titles or abstracts.”

No page numbers are supplied. These are fictional English source passages, not research findings.

At the scope gate, runner replies: **“Synthetic fixture decision: confirm both alternative methods and catalog matching; do not claim accuracy improvement or a shared mechanism. Keep the two-curator requirement in scope.”**

### 3. Gemini block proposal and second gate

Supply a fictional Gemini block proposal only after the scope gate:

- Main: `(optical recognition OR manual transcription)` AND `catalog matching`.
- Focused alternative: optical recognition AND catalog matching, losing manual-only studies.
- Two-curator review: screening-only, because metadata representation is inconsistent.
- Source wording above supports the core blocks; any added synonyms/translations must be labeled model expansions, not quotations.

At the block gate, runner replies: **“Synthetic fixture decision: confirm those OR/AND roles, optical-only alternative and screening-only review. Use the source English terms without additional expansions.”**

### 4. Delivery and stopping

Consumer renders six complete English queries and the local ledger, reports local checks, historical IEEE basis, platform differences and independent validation states. At handoff, runner replies: **“Synthetic fixture decision: accept this draft version and stated risks; live Notebook, platform and human acceptance stay pending.”**

## Independent observable oracle

Inspect the transcript and saved artifact, not keyword presence in implementation files:

- Consumer actually read the two trial SKILL.md files; dependency and reference paths resolve to the recorded checkout/revision.
- The selected full UUID stays pinned; intended follow-ups retain the conversation ID, with ask effect notice before questions. No destructive/source/note/sync operations or real calls occur in replay.
- Empty references cause source lookup before accepting core provenance; original titles/passages are traceable and no page numbers/accuracy-improvement claim appears.
- Scope and block prompts occur before formal queries; fixture decisions are labeled synthetic, not invented live confirmations.
- Main has alternative methods joined OR and catalog matching co-required via AND; focused tier excludes manual-only studies with an explicit loss explanation; two-curator review is screening-only, not an added hard filter.
- Artifact has six fully rendered English strings at correct entries, Scopus/WoS field syntax from their references, and no IEEE prefixes/caps. Quotes/parentheses are locally inspected. Coverage and phrase differences are explained.
- Source-rule/local/parser/seed states are separate. IEEE remains historical/current untested; no live search results, parser or seed passes are invented. Live Notebook and human gates remain pending.

Record pass/fail observations with transcript/artifact locations and applicable revision. A synthetic success does not prove host-level automatic routing, live authentication, real service responses or human acceptance; the non-trigger scenario above and the [access guards](recovery-trial.md#access-guards-separate-fresh-fixture-runs) are separate runs. Do not claim any of these from this replay.
