---
name: whoami
description: Evidence-backed research identity from the Identity Notebook. Use for 科研标签/研究定位, a grant 研究基础 section, a bio, talk title/abstract, application form fields, the user's paper list/count, or project and award list.
---

# whoami

The **Identity Notebook** holds the user's papers, applications and direction/contribution materials. Choose the research-positioning branch for labels; choose the drafting branch for a formal deliverable. Both follow the evidence rules below.

## Queries and confidentiality

Load `gemini-notebook` first. Pin the exact title `Identity`, retain its full UUID, and use `-n <UUID>` on every command. Source IDs come from that notebook's own list.

- **Read-only sources.** The user curates Identity. Material intended for it goes to the user to add.
- **One conversation.** The first `ask` omits `-c` to continue the existing web conversation; follow-ups use its returned conversation ID. Identity never uses `--new`. Narrow with `-s` instead.
- **Confidential.** Evidence and drafts stay in chat or a user-named private path, never in the repository, issue or PR. Acceptance records contain procedural results only.

## Evidence rules

**Authority is established, not inferred.** Classify source contents as paper original, user-confirmed self-statement, application (status/results versus plan), generated synthesis, or unclassified. A title such as “研究贡献”, a Markdown file, or inclusion in Identity establishes none of these identities. Confirm ambiguous provenance with the user. Generated syntheses are discovery aids: follow their claims to originals, not their internal citation numbers as if verified.

**Achievements need evidence and a role.** Support them with a paper original, a user-confirmed contribution statement, or a project status line marking 在研/结题 and the user as 主持. Check authorship and contribution passages before attributing a paper's result to the user; being in Identity is not proof of authorship, first authorship, leadership or sole contribution. Quantitative results, priority claims, awards and project status require primary evidence; self-statements do not substitute for missing status records. Applications' research plans, expected outcomes and targets remain plans.

**Lists and counts come from titles.** Count the `作者 - 年份 - 标题` paper-source pattern from `source list`, with the year/author filter stated. Call these paper-source counts until publication status and the user's authorship are verified. First-author counts additionally require the author's identity to be established from the original, not inferred from a title's “et al.”. Unmatched titles remain unclassified until checked.

**⚠ marking.** Put the marker before the claim and the reason after it:
- `⚠ … [计划/考核指标: <source title>]`
- `⚠ … [未核实]`
- `⚠ … [状态不明: <source title>]`
- `⚠ … [来源身份/个人角色待确认: <source title>]`

**Inventory economy.** Parse `source list` once; retain its ID/title mapping privately. Show relevant candidates and title-derived counts, rather than dumping the whole library. The checkout provides `scripts/notebook_inventory.py --match '<title regex>'` to filter piped JSON; matching titles identifies candidates, not authoritative self-statements. When classifying a full inventory, assign every source to exactly one category, including unclassified.

## Research positioning: 科研标签 / 研究定位

This branch helps discover a direction; it does not require the user to know or confirm it before receiving candidates.

1. Inventory relevant papers and direction materials. Check provenance; find recurring themes across paper originals with `source search`. Use a source-scoped `ask` only when synthesis is needed, announcing its 1–1.5 minute cost.
2. Give one provisional umbrella label and 3–5 supporting labels. For each, name its scope, paper evidence and whether it reflects existing work or a future agenda. Distinguish published/results material from plans and unverified publication status. Mark your label wording as **agent synthesis**, not a quotation.
3. Explain the boundaries: distinguish methods, application domains and scientific questions. Extend earlier work into a new umbrella only as an interpretation, not proof that all earlier papers studied that umbrella. Ask which labels the user endorses or wants to adjust.

Done when: candidates answer the question, each has original evidence or ⚠, and future agenda is separate from established work. A label discussion is not acceptance of a formal research-foundation draft.

## Formal drafting

### 1. Inventory and establish authority

Classify the inventory using the evidence rules, retain the title-derived paper count by year and inspect relevant ambiguous sources.

Done when: every source in scope has a category; authoritative self-statements and the user's relevant roles are verified or explicitly pending.

### 2. Confirm direction and format

Read a user-confirmed direction statement with `source search`; propose one direction sentence and 3–5 themes. If none exists, use research positioning first. Ask for the target length and headings.

Done when: the user confirms the direction, themes and format. Formal drafting waits for this confirmation.

### 3. Gather evidence

One `ask` per confirmed theme, continuing the conversation. Announce each 1–1.5 minute query. Ask for source-grounded results, status (published / 在研 / 结题 / planned), the user's role, and “来源中未找到” for missing evidence. Map every reference to its source title.

Done when: every theme has mapped evidence; claims from generated material remain leads, not facts.

### 4. Verify and draft

For each factual claim, use `source search` to retain the original passage and check the user's role. Apply ⚠ to unresolved claims. Write the requested format with provenance on each factual sentence and a separate list of ⚠ items. See `references/deliverables.md` for research-foundation sections, talks, forms and project/award lists.

Done when: every factual sentence has verifying provenance or ⚠, and the user can distinguish their established results from plans and agent interpretation.
