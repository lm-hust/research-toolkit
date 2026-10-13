# Query-first reply and complete local artifact

Use this structure after both confirmation gates. Render every query slot as a **complete English string** from the confirmed blocks and its platform reference; leave no tokens, ellipses, named-block substitutions or instructions for the user to expand. This file is a generation template, not a pre-confirmed strategy.

The default reply begins with section 1, then briefly summarizes alternative restrictions, coverage differences, evidence/risk and validation states. Save the full record only at a user-approved private local destination; keep actual topics, passages and queries out of public repository/tracker records.

## 1. Six copyable queries — version [actual version]

Status: **copyable draft**, unless actual platform/seed evidence supports a narrower validation claim. Record draft date, not a fictitious search execution date.

### Scopus — main

Entry: [Scopus](https://www.scopus.com/) → Advanced Search.

```text
[Render complete main query using references/scopus.md]
```

### Scopus — focused alternative

Entry: Scopus → Advanced Search.

```text
[Render complete alternative using references/scopus.md]
```

Restriction/change, why it helps the intended focus, possible losses: [specific explanation, not measured precision].

### Web of Science Core Collection — main

Entry: [Web of Science](https://www.webofscience.com/) → Core Collection → Advanced Search → Query Builder.

```text
[Render complete main query using references/web-of-science.md]
```

### Web of Science Core Collection — focused alternative

Entry: Core Collection → Advanced Search → Query Builder.

```text
[Render complete alternative using references/web-of-science.md]
```

Restriction/change and possible losses: [specific explanation].

### IEEE Xplore — main

Entry: [IEEE Xplore](https://ieeexplore.ieee.org/) → Advanced Search → Command Search, default All Metadata.

**Historical official basis; current platform untested** unless current evidence was actually obtained and recorded.

```text
[Render complete main query using references/ieee-xplore.md]
```

### IEEE Xplore — focused alternative

Entry: Advanced Search → Command Search, default All Metadata.

```text
[Render complete alternative using references/ieee-xplore.md]
```

Restriction/change and possible losses: [specific explanation]. Retain the historical label for this tier too. Do not claim a strict result-set subset if changed terms/fields/semantics do not warrant it.

### Branch queries in a slot

The six platform × tier slots stay fixed. When a [branch split](revision.md#length-and-rule-rejection) replaces one slot's query, that slot holds every branch, in order, each as its own labelled code block (`Branch 1 of n: [alternatives it carries]`) containing a complete, separately copyable string with the same entry. Never join branches with an instruction to combine strings, and never move a branch into another tier's slot. Below the branches, state which alternatives each carries and that the user runs every branch and combines and deduplicates the result sets. The other slots are unchanged. Validation states are recorded per branch.

## 2. Confirmed scope and evidence ledger

- Notebook: actual title, full pinned UUID; relevant conversation ID/history context. Never include tokens/credentials.
- Evidence rounds: questions, faithful answers, source mapping and verification results retained locally; record unavailable evidence honestly.
- Recovery record, when interrupted: condition, affected claim/scope/block, observed error/lookup, claim state (verified/unverified/unsupported), still-usable records, needed repair and resumed step. Keep unresolved original citations distinct from independently verified supporting passages.
- Scope confirmation: actual user decision/revision and when observed. If replayed, label **synthetic fixture decision**, not live human approval. For changed scope, record what [scope recovery](recovery.md#scope-changes) invalidated and the fresh decisions.

| CIMO dimension | Confirmed meaning/status | Notebook source title and ID | Supporting passage / evidence gap |
| --- | --- | --- | --- |
| Context | | | |
| Intervention | | | |
| Mechanism | | | |
| Outcome | | | |

Use evidenced / unclear / evidence-insufficient / not applicable as appropriate. Cite passages, not unsupported pages. Separate proposals from verified source wording and user intent.

| Block | Confirmed CIMO link and supporting passage | English terms by class: user / verified source / model translation or expansion | Confirmed role and Boolean relationship | Metadata representation, rationale, potential losses |
| --- | --- | --- | --- | --- |

Record every core block and each restriction. List screening-only criteria and their user confirmation separately. Include block-gate decision/revisions; never turn an unobserved confirmation into a completed gate.

## 3. Coverage, rule provenance and risks

Consult the rule owners for details; record which exact primary rules/locators and reviewed dates support the rendered syntax. Preserve historical status and any actual recheck date/results separately. The default rule owners are [Scopus](scopus.md), [WoS](web-of-science.md) and [IEEE](ieee-xplore.md).

Explain the actual broad-field differences: Scopus's indexed/expanded keyword coverage; WoS Topic's Keywords Plus; IEEE's non-exhaustive All Metadata coverage and its distinction from Full Text & Metadata. Phrase behavior differs; similar field names are not equivalence guarantees.

Record alternative losses, model-expanded vocabulary, evidence gaps, screening-only criteria, coverage uncertainty and unsupported optional syntax avoided. Carry the WoS All Fields 49/100 conflict and IEEE current limits/field-prefix unknowns forward. Do not claim population recall, guaranteed precision, PRESS review or web/API parity.

Methodological basis and limits (reviewed 2026-10-12 in the [methodology report](https://github.com/lm-hust/research-toolkit/blob/e6dafc111a1fb6b2d1a7fd91b69eea7ec7ac541a/docs/research/cimo-search-methodology.md)):
- Denyer et al., [institutional abstract](https://research.tue.nl/en/publications/developing-design-propositions-through-research-synthesis/), [DOI](https://doi.org/10.1177/0170840607088020): CIMO describes design propositions, not a Boolean formula. Original full text was not recovered.
- [Cochrane chapter 4, §4.4.2](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04): choose concepts question-by-question; searching every aspect may be undesirable. Clinical guidance is not an empirical engineering recall claim or proof of optimal CIMO translation.
- [PRISMA-S, items 8, 13, 14](https://link.springer.com/article/10.1186/s13643-020-01542-z): reporting exact strategies as run, actual search dates and actual peer review; reporting guidance, not mandated concept selection.
- [PRISMA 2020 expanded checklist, item 7](https://www.prisma-statement.org/s/PRISMA_2020_expanded_checklist-yc78.pdf): if validated with clearly eligible studies, report the process and set; not an unconditional live-validation requirement.
- [PRESS guideline DOI](https://doi.org/10.1016/j.jclinepi.2016.01.021) and [original checklist candidate](https://www.cda-amc.ca/sites/default/files/PRESS_Peer_Review_Electronic_Search_Strate/Table_9-PRESS.pdf): original bodies were not recovered; do not claim their checklist was applied or verified. No measured recall, CIMO superiority or three-platform completeness was established by these inputs.

## 4. Independent validation states

State rules are owned by [revision](revision.md#independent-validation-states). Fill one table per version; every passed or failed cell names its version, date, entry and evidence.

| Platform / tier | Source rule (owner, locator, date, bounded/historical) | Local check (version, date, per-check results) | Platform parser (version, date, entry, verbatim result) | Seed diagnostic (version, date, x/y, uncertain, not indexed) |
| --- | --- | --- | --- | --- |
| Scopus main / alternative | | | Untested unless run | Untested unless run |
| WoS Core Collection main / alternative | | | Untested unless run | Untested unless run |
| IEEE Xplore main / alternative | Historical official basis; current platform untested | | Untested unless run | Untested unless run |

Local results enumerate English terms, quotes, parentheses, confirmed Boolean relationships, entry/field syntax and applicable phrase/wildcard rules **for each of six queries**. Draft completion needs no invented live execution.

## 5. Version and handoff

Record the current version, private artifact path and actual user acceptance or **pending**. Keep earlier versions' exact strings and states; never overwrite them. Retain the recovery record as pause/repair history.

| Version | Preceding | Drafted | Feedback (verbatim or location) | Diagnosis | Change, reason, semantic effect | Gates re-run | Open risks | Acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Follow [revision](revision.md#revise-version-and-redeliver) for what each row requires.
