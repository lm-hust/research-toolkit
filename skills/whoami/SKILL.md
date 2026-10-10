---
name: whoami
description: Drafts from the user's own track record in the Identity Notebook. Use when the user asks for a grant "研究基础" section, a bio or 个人简介, a talk title and abstract (报告选题/摘要), application form fields (代表性成果, 项目清单), a paper list or count of their own work, or a project and award list.
---

# whoami

The **Identity Notebook** is the Gemini Notebook titled `Identity`: the user's own papers, grant proposals and handwritten statements, curated by hand. Every draft here is built from it, and every claim in a draft is either backed by a source in it or marked ⚠.

## Queries

Every command follows the `gemini-notebook` skill: its "Running commands" prefix, step 1 to pin the notebook (exact title `Identity`, full UUID, `-n <UUID>` on every command) and step 5 to map `[n]` to source titles. Load it first if it is not already loaded.

On Identity the agent is a reader:

- **Sources are read-only.** Identity changes only by the user's hand. Anything meant for Identity (such as the project and award list) goes to the user, who adds it.
- **One conversation.** Every `ask` continues Identity's current conversation, the one the user keeps on the web: the first `ask` goes without `-c`, then every later one passes `-c <conversation_id>` from that first answer. `--new` deletes that conversation, so it never appears on Identity, even when a fresh start would help; narrow with `-s <source_id>` instead.
- **Confidential.** Identity holds unpublished application material. Drafts and evidence go to the chat or to a path the user names, never into a git repository, issue or PR.

## Evidence rules

**Lists and counts come from titles.** Any paper list or count ("近五年论文", "how many first-author papers") is a count over `source list` titles, never an `ask` answer: `ask` drops items from lists. Paper sources are titled `作者 - 年份 - 标题`; filter by the year and author fields, and report the count with the filter used. A title that does not fit the pattern is listed for the user to classify, not guessed.

**Achievements need a state.** A claim counts as an achievement only when it appears in one of:

1. a paper source;
2. a contribution statement the user wrote by hand;
3. a status line of an application that marks the project 在研 or 结题 with the user as 主持.

`ask` presents plans as results. A claim whose only support is an application's research plan, expected outcomes or performance targets (研究计划, 预期成果, 考核指标) is a plan, not an achievement, and carries ⚠.

**⚠ marking.** Put `⚠` before the claim and the reason in brackets after it, so the user can check each one:

- `⚠ … [计划/考核指标: <source title>]`: support is a plan or target only.
- `⚠ … [未核实]`: `ask` said it, `source search` found no passage.
- `⚠ … [状态不明: <source title>]`: found, but no line gives its status or the user's role.

## Steps

### 1. Inventory the sources

Pin Identity, then run `source list`. Sort every title into papers (by the `作者 - 年份 - 标题` pattern), applications, handwritten statements, and other.

Done when: every source sits in exactly one group, and you have the paper count by year.

### 2. Confirm the research direction

Find the user's handwritten direction statement in the inventory and read it with `source search` on its key terms (`-s <source_id>`). From it, write the direction in one sentence and split it into the 3–5 themes the draft will be organised around. Show both to the user.

Done when: the user has said yes to the direction and the theme list, or given their own. Nothing is drafted before that.

### 3. Gather evidence with ask

One `ask` per theme, in the conversation from the Queries section. Tell the user each takes 1–1.5 minutes before sending. Open each question with the confirmed direction and this grounding: answer only from the notebook's sources, write "来源中未找到" where there is none, and give each item's status (published / 在研 / 结题 / planned) and the user's role. Keep each answer's `references[]`.

Done when: every theme has an answer and its references mapped to source titles.

### 4. Verify with source search

For every claim that will reach the draft, run `source search` on its key terms (the ~5 s search writes nothing). Keep the matching source title and `cited_text`. Apply the evidence rules: a claim with a passage from a paper, a handwritten statement or a 在研/结题 status line stands; every other claim takes its ⚠.

Done when: every claim has either a verifying passage or a ⚠.

### 5. Draft

Claude writes the deliverable in its target format (see [`references/deliverables.md`](references/deliverables.md)). Each claim ends with its provenance: the source title, plus the `cited_text` when the wording matters. Paper lists and counts come from step 1 alone. Below the draft, list every ⚠ claim for the user to resolve.

Done when: every sentence that states a fact has a source title or a ⚠.

## Deliverables

| The user wants | Shape |
|---|---|
| 研究基础 section | all five steps |
| 报告选题与摘要 | steps 1–4 on the talk's topic, then candidate titles and an abstract |
| form fields (个人简介, 代表性成果, 项目清单) | steps 1–4 per field, filled in the form's order |
| project and award list | the list workflow in the reference |

Formats, and the project and award list workflow: [`references/deliverables.md`](references/deliverables.md).
