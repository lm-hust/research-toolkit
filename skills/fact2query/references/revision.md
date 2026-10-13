# Feedback revision

Use this reference when the user reports what happened after running a delivered query: a parser message, a rule/length rejection, a result profile, or missed seed papers. It owns validation-state rules, feedback diagnosis, seed diagnosis, revision explanation and version history; stopping at acceptance stays with [main step 5](../SKILL.md#5-deliver-locally-and-stop-at-acceptance). Platform syntax stays with the [Scopus](scopus.md), [WoS](web-of-science.md) and [IEEE](ieee-xplore.md) rule owners; scope pauses and re-confirmation stay with [recovery](recovery.md); artifact layout stays with the [output template](output-template.md).

The [main write and execution boundary](../SKILL.md#1-load-the-dependency-and-pin-identity) still applies: fact2query does not run queries or seed lookups here. It records what the user, or another separately authorized actor, actually ran and reported.

## Record feedback against a version

Tie every feedback item to: query **version**, platform and tier, **entry point** and any UI settings, the **date** it was run, the **exact submitted string**, and the verbatim message or reported result profile. If the submitted string differs from the delivered version, record it as its own variant; feedback about it does not apply to the delivered version. Ask for missing details rather than inventing them. Record reported counts as reported, never as yours.

## Independent validation states

Keep four states per platform and tier, for each version:

| State | Passed or failed only when | Evidence to attach |
| --- | --- | --- |
| Source rule | The syntax used is within the rule owner's reviewed subset, or a primary rule was actually rechecked. | Rule owner, primary locator, reviewed/recheck date, bounded or historical status. |
| Local check | Main step 4 inspection ran on this exact version's string. | Version, date, each check's result. |
| Platform parser | That exact string was submitted at that entry and the platform's acceptance or error was reported. | Version, date, entry/settings, who ran it, verbatim message. |
| Seed diagnostic | [Seed diagnosis](#seed-diagnosis) ran on that exact version for that platform. | Version, date, entry, seed list location, x/y report. |

Anything else is **untested**. States are independent: local checks do not imply parsing, parsing does not imply seed coverage, and one platform or tier does not stand in for another. In a new version, a changed string starts with parser and seed states **untested**; an unchanged string may cite its earlier test by original version and date. Source-rule state carries over only if no new syntax is added. A failed state stays recorded against its version; repairing the query creates a new version rather than turning the old failure into a pass.

## Diagnose before changing

Diagnose each parser message and each missed seed separately, then propose a change. One miss can have more than one cause.

| Diagnosis | Signal | Needed evidence | Revision direction |
| --- | --- | --- | --- |
| Parser error | Platform rejects or misreads the string. | Verbatim message, exact string, entry. | Recheck that platform's primary rule, locate the construct, repair syntax without changing meaning. Length or complexity rejections follow [length and rule rejection](#length-and-rule-rejection). |
| Not indexed | The seed is absent from that platform's database. | User-reported lookup by DOI/title at that platform, with date. | No query change. Exclude it from that platform's denominator. |
| Field mismatch | Indexed, but the concept appears only outside the searched field, for example only in full text. | The seed's searched-field metadata compared with block terms. | Explain the coverage difference. A different field needs the rule owner's verified subset or a recheck, and a stated scope/noise trade-off. |
| Vocabulary gap | Indexed and in a searched field, but worded with a variant/synonym the block lacks. | The seed's actual wording. | Add the English variant under one of the [three provenance classes](#seed-derived-terms). A term that broadens meaning is a scope change. |
| Over-restrictive concept | In scope, but fails an AND block or a focused-tier restriction. | Which block or restriction excluded it. | Options: make the block screening-only, add an OR alternative, or relax it in main only. Changing a co-required concept or role needs the block gate; changing scope needs [scope recovery](recovery.md#scope-changes). |
| Unexplained | None of the above is established. | — | Keep it as an open risk. Do not change the query to chase it. |

A result profile alone ("too many", "too few") is not a diagnosis. Ask for example records that are irrelevant or missing, and do not tune toward a count target. Never relax without limit and never promise zero misses.

### Seed-derived terms

Seed-record wording is evidence for a diagnosis, not a fourth provenance class. Classify each proposed term under the existing three:

- **User intent/terms:** the user explicitly adopts wording from a seed record they reported. Record the seed ID as the rationale.
- **Verified source wording:** only if the same wording is verified in a passage of the pinned Notebook, as in [references and interpretation](recovery.md#references-and-interpretation). Seed membership in the Notebook does not verify it.
- **Model translation/expansion:** variants or synonyms the agent proposes beyond the reported wording.

Adding, removing or reclassifying a term in a core block, including a seed-derived term, needs the block gate before rendering.

## Length and rule rejection

When a platform rejects a query for length, term count or complexity, record the verbatim message and recheck the rule owner. Do not adopt an unverified or conflicting cap as fact; the rule owners list the known conflicts. Present the options with their semantic change:

- **Remove terms:** list each removed term, its provenance class, and which records it may lose. Removing a user or verified-source term changes a confirmed block and needs the block gate.
- **Split into branch queries:** each branch is a complete string with the same co-required blocks, alternatives divided across branches. Lay the branches out in their slot as the [output template](output-template.md#branch-queries-in-a-slot) defines. State that the user must combine and deduplicate the result sets, and only claim platform-side combination if the rule owner verifies it.
- **Other repair** (a verified wildcard in place of listed variants, a narrower verified field): state what it adds or loses.

If the same revision also adds terms to the rejected query (for example a vocabulary-gap fix), say how each added term interacts with the repair: which branch receives it, or what was removed to make room, and that the added length may trigger the same rejection again. Do not add terms to a rejected string without accounting for its rejection.

The altered query is a new version. The rejected version keeps its failed parser state; never label the shortened query as the original passing.

## Seed diagnosis

Run only for seeds the user confirms as eligible for the **current confirmed scope**. Notebook membership is not eligibility, and an obsolete scope's seeds need re-confirmation. Ask for seeds that vary terminology and method, and for independently known eligible studies (not only Notebook sources) when the user has them.

For each platform, record each seed as **confirmed indexed**, **not indexed**, or **indexing uncertain**, and how that was established. Report per platform and version:

> Scopus v2 main: 3/4 confirmed-indexed eligible seeds retrieved. Not indexed: 1. Indexing uncertain: 1 (outside the denominator).

Uncertain and not-indexed seeds are listed separately, never counted as misses. Do not call x/y recall, sensitivity, or a percentage meeting a target. It is a diagnostic sample of the confirmed seeds. Each confirmed-indexed miss goes to [diagnosis](#diagnose-before-changing).

## Revise, version and redeliver

1. Assign a new version, naming its predecessor. Keep the old version's exact strings and states unchanged.
2. Show the proposed diff: each change, the feedback and diagnosis it answers, its provenance class and its semantic effect, including any [interaction with a length repair](#length-and-rule-rejection). A syntax-only repair that leaves terms and roles unchanged needs only the user's go-ahead on the diff. A change to core-block terms or block roles needs the block gate. A scope change, a new direction or reliance on a newly needed platform capability follows [scope recovery](recovery.md#scope-changes): pause, re-ground, then pass the gates afresh.
3. Re-run main step 4 local checks on the new version and redeliver **all six** complete English queries with field differences and restrictions, through the [output template](output-template.md#5-version-and-handoff).
4. Keep unexplained issues, untested states and residual risks visible, then hand off under [main step 5](../SKILL.md#5-deliver-locally-and-stop-at-acceptance).
