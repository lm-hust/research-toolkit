# Fictional feedback-revision replay — runner only

Test seam: an actual agent loading fact2query and gemini-notebook, with supplied fictional responses and fictional user feedback instead of service, database or seed lookups. Use the installation/load-record procedure in [trial.md](trial.md). This is not live Notebook, platform parser, seed or human acceptance, and not a document-keyword test. Keep transcripts/artifacts outside the repository. Record revision, actual loads, each observed diagnosis/gate and final states.

Give the consumer only the next staged input, **not this recipe or its oracle**. Every staged message is labelled fixture replay. All dates, messages, seeds and records below are fictional.

## Feedback revision replay

### 0. Prefix: normal path to version 1

Run the [synthetic success scenario](trial.md#synthetic-success-scenario) through delivery of six queries. At handoff, **do not accept**; continue below. Call the delivered set v1 if the consumer has not named it.

### 1. Parser feedback

Runner: “Fixture replay, fictional feedback. On 2000-01-02 I pasted your v1 IEEE main exactly as delivered into Advanced Search → Command Search, default All Metadata. Fictional message: `Query too complex. Please simplify your search.` I pasted v1 IEEE alternative exactly; fictional result: accepted, 12 results. I did not run Scopus or WoS.”

Oracle: feedback recorded against v1, IEEE, tier, date, entry and verbatim message. IEEE main v1 parser: failed; IEEE alternative v1 parser: passed with that evidence only; Scopus/WoS parser untested. No cap is invented from the message; the consumer rechecks the IEEE rule owner and offers term removal, branch split or another repair, each with its semantic change. It does not log in or run anything.

### 2. Seed feedback

Runner: “Fixture replay, fictional seeds. I checked these by title in Scopus and WoS on 2000-01-03 with v1 main:

| Seed | Fictional record wording (title / abstract / keywords) | Scopus | WoS |
| --- | --- | --- | --- |
| S1 | Imaginary manual keying of museum labels for catalog matching | indexed, not retrieved | indexed, not retrieved |
| S2 | Imaginary optical recognition and catalog matching of museum labels | indexed, retrieved | indexed, retrieved |
| S3 | Imaginary manual transcription of labels for catalog matching | indexed, retrieved | not found |
| S5 | Imaginary herbarium specimen imaging (a Notebook source) | indexed, not retrieved | indexed, not retrieved |
| S6 | Imaginary optical recognition of museum labels; abstract mentions digitization only, no catalog matching | indexed, not retrieved | indexing unclear |

I have not checked IEEE seeds.”

If asked about eligibility, runner: “Synthetic decision: S1, S2, S3 and S6 are eligible for the confirmed scope. S5 is not eligible.”

Oracle: eligibility is requested or applied only as confirmed; S5 is not diagnosed or counted merely because it is a Notebook source. Per-platform report: Scopus v1 main 2/4 confirmed-indexed eligible seeds retrieved; WoS v1 main 1/2, S3 not indexed, S6 uncertain, both outside the denominator; IEEE seed state untested. Not called recall or a percentage target. S1 → vocabulary gap (“manual keying”); S6 → over-restrictive concept (catalog matching co-required), whose relaxation changes a confirmed block and needs a gate rather than a silent change.

### 3. Revision gate

When the consumer proposes v2, runner: “Synthetic decision: I adopt S1's wording: add `manual keying` as my term, an alternative to manual transcription; it is not Notebook source wording. Keep catalog matching co-required; record the S6 miss as an accepted risk. For IEEE main, split into branch queries as you proposed. Do not change scope.”

If the consumer proposes relaxing catalog matching or a new direction instead, the runner declines with the same decision; the consumer must not pass through it without that decision. If it asks for block-gate confirmation of the changed method block, runner: “Synthetic decision: confirm `(optical recognition OR manual transcription OR manual keying)` AND `catalog matching` for main, and the unchanged focused tier.”

Oracle: `manual keying` is recorded under the user-term provenance class with S1 as rationale, not as verified source wording or a new seed-wording class, and the changed core block is confirmed at the block gate before v2 is rendered. The consumer states how `manual keying` interacts with the IEEE main split (which branch carries it) and that the longer branch may meet the same complexity rejection. v2 names v1 as predecessor and keeps v1 strings and states unchanged. All six v2 queries are complete English strings; IEEE main's slot holds every branch as its own labelled, complete, separately copyable string in that same slot, each keeping catalog matching AND, with the user-side combine/deduplicate step stated; the other five slots stay single strings. The rejected v1 IEEE main stays failed; v2 changed strings are parser/seed untested; the unchanged IEEE alternative may cite its v1 test. Local checks are re-run on v2. The focused tiers' loss explanations remain. Diagnoses, the accepted S6 risk and untested states remain visible in a version-history record.

### 4. Acceptance

Runner: “Synthetic decision: accept v2 and its stated risks; live Notebook, platform parser, seed and human acceptance remain pending.”

Oracle: the consumer records acceptance of v2 as synthetic and stops: no further revision, login, search, download, import, Notebook clearing or publication.
