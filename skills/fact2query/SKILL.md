---
name: fact2query
description: Generate or revise English Scopus, Web of Science Core Collection and IEEE Xplore queries from a specified Gemini Notebook's evidence. Use for Notebook-grounded three-platform search strategies, or when invoked by name; ordinary Notebook summaries stay with gemini-notebook.
---

# fact2query

Facts → confirmed scope → confirmed search blocks → six English queries. The result is a **copyable draft**, not a live-tested search strategy.

## 1. Load the dependency and pin identity

Load [`gemini-notebook`](../gemini-notebook/SKILL.md) before any Notebook operation. It owns CLI/backend/auth, identity resolution, source lookup, conversation continuation and write permissions. For ambiguous/no-match identity, unavailable dependency/capability, failed reads or unreadable sources, follow [`references/recovery.md`](references/recovery.md#identity-and-access) before proceeding. Never replace Notebook evidence with a topic-only query or another service.

Resolve the user's name or link to one full Notebook UUID and title through that contract; present ambiguous candidates for user selection. For a link, verify its UUID against the Notebook inventory rather than silently using the current default. Retain the selected title, full UUID, source ID/title mapping and relevant conversation identity privately. Every Notebook call uses explicit `-n <full UUID>`.

Continue existing dialogue: read relevant history; the first ask continues the current conversation, follow-ups carry its returned `conversation_id`. Before sending an ask, explain the dependency's time cost and that it may append conversation history. Preserve sources and history: this workflow never clears conversations, modifies sources, saves Notebook notes, syncs or skims. It neither logs into databases nor searches, downloads, screens or ingests papers.

Done when: identity is uniquely pinned and the dependency and relevant evidence are accessible. Otherwise pause without queries.

## 2. Gather facts and ask Gemini for CIMO

Use the topic as a guide to multi-round Notebook dialogue, not as evidence. Relay Gemini faithfully; label agent additions. Ask Gemini to propose source-grounded **Context, Intervention, Mechanism, Outcome** with supporting passages, source identities and uncertainties. Separate plausible scopes only when they affect scope or core concepts.

Map references to this Notebook's source titles and passages. An answer is a proposal, not automatically a fact or verified quotation. For empty/unmapped/key-only references or conflicting/unsupported interpretations, follow [`references/recovery.md`](references/recovery.md#references-and-interpretation): verify passages and correct or mark unsupported meaning before it reaches blocks.

For every concept distinguish **user intent/terms**, **verified source wording**, and **model translation/expansion/synthesis**. Record dimensions as evidenced, unclear, evidence-insufficient or not applicable; use the [CIMO gap definitions and consequential follow-ups](references/recovery.md#cimo-gaps) when a dimension is missing or uncertain.

**Scope gate:** show CIMO, evidence, gaps and proposed scope; obtain the user's explicit confirmation or revision. On a changed direction or scope-expanding concept at any step, apply [scope recovery](references/recovery.md#scope-changes) to invalidate affected old approvals/evidence links and re-ground before fresh confirmations. No formal queries yet.

## 3. Ask Gemini for search blocks and confirm roles

After scope confirmation, ask Gemini to recommend searchable concepts and their roles. For each block explain its confirmed CIMO link, Notebook passage, English terms and provenance classes, scope necessity, expected metadata representation, role (**main**, **alternative**, **screening-only**) and possible exclusions.

Choose logic from meaning: aliases and alternative approaches use OR; only genuinely co-required concepts use AND. CIMO cells do not prescribe Boolean structure. There is no mandatory C AND I, four-cell AND, blanket M/O exclusion or alternative-plus-M rule. A mechanism or outcome can be the subject; context can be background. Avoid making a coined topic label a mandatory phrase.

A scope-essential but poorly searchable criterion may be screening-only after explaining and confirming it; that is not authorization to execute screening. Main aims to reduce misses, without measured-recall claims. The focused alternative may add a justified block, narrow vocabulary or use a verified field/phrase restriction. Explain each change and possible losses; do not promise improved precision or a strict subset when vocabulary or semantics differ.

Translate terms into English, labeling translations and expansions rather than attributing them verbatim to sources. Scope-expanding terms trigger scope recovery, not just vocabulary substitution. No unrequested NOT exclusion.

**Block gate:** present the proposed OR/AND relationships, both tiers, restrictions and screening criteria. Obtain explicit user confirmation or revision before rendering any formal query. Silence and a fixture's existence are not live confirmation.

## 4. Render and check each platform

Before rendering, read all three rule owners:
- Scopus Advanced Search: [`references/scopus.md`](references/scopus.md).
- WoS Core Collection Advanced Search → Query Builder: [`references/web-of-science.md`](references/web-of-science.md).
- IEEE Xplore Advanced Search → Command Search: [`references/ieee-xplore.md`](references/ieee-xplore.md), conservative historical subset only.

Use those reviewed subsets by default. When adding syntax, seeing changed official guidance or receiving parser errors, recheck the relevant primary rule; do not silently promote historical guidance, unsupported operators or unknown limits. Field coverage and phrase semantics differ; web syntax is not an API contract.

Locally inspect **each of six fully expanded queries**: English terms/variants; straight paired quotes; balanced parentheses; explicit grouped OR/AND matching confirmed roles; correct entry, field tags and permitted syntax from its rule owner. Inspect applicable wildcard/phrase rules if used. Record failures and repair/recheck before handoff. These checks prove neither platform parsing nor retrieval quality.

Done when: all six queries pass these local checks without unsupported syntax or unconfirmed restrictions. If a tier cannot be justified, return to the block gate rather than invent one.

## 5. Deliver locally and stop at acceptance

Use [`references/output-template.md`](references/output-template.md) for the query-first reply and full local artifact. Fill it completely: six copyable English strings, actual web entries, confirmed CIMO/blocks, passage-level provenance, vocabulary classes, restrictions/losses, platform differences and distinct **source-rule / local-check / parser / seed** states. Unknown or unrun checks remain pending/untested; no invented dates, counts or results.

Ask for a private local destination if none is specified. Keep actual topics, evidence passages, queries and confirmation/version records in chat or a user-approved private path outside the public repository/tracker; never upload private source material as part of this workflow. Preserve the exact version and reasons for changes locally, including any recovery record.

Default draft completion requires evidence, both confirmations, six queries, local checks and an honest risk handoff. Platform execution and seed diagnostics require separate authorization and are optional; they may remain untested. Stop when the user accepts the version and remaining risks, not at an arbitrary result count or a zero-miss promise.

For an isolated checkout-backed development trial, use [`references/trial.md`](references/trial.md); for access guards and same-consumer evidence/scope pause-and-resume replay, use [`references/recovery-trial.md`](references/recovery-trial.md). Both fixtures are synthetic, not Notebook-service or human-acceptance results.
