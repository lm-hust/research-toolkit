# Evidence and scope recovery

Use this reference when identity/access fails, references are unusable, a source contradicts an answer, CIMO has a consequential gap, or the user changes scope, including through [feedback revision](revision.md#revise-version-and-redeliver). It owns only pause, repair and resume. Notebook commands, identity matching, source lookup and write permissions stay with [gemini-notebook](../../gemini-notebook/SKILL.md); provenance classes, gates, block logic and rendering stay with [fact2query](../SKILL.md).

## Pause, repair, resume

For each interruption, report **what is blocked, what remains usable, what input/access is needed, and which step resumes afterward**. Log it in the artifact's recovery record ([output template](output-template.md#2-confirmed-scope-and-evidence-ledger)). Preserve earlier attempts rather than converting a failed check to a pass. Resume only after observing the required repair and completing affected evidence checks/gates; a promised repair is not verified evidence.

### Identity and access

- **Same name / no exact match:** apply the dependency's candidate-selection rule and wait for a selection or a corrected accessible name/link. Do not adopt a lone near-match or the default. Empty inventory means no accessible candidates. Do not infer deletion from a read failure. No Notebook is chosen until identity resolves, and none is created as recovery.
- **Dependency file or required capability unavailable:** name the unavailable file/capability and request its restoration in the intended consumer. Stop before construction. Installation changes need an explicitly selected source/target, never an automatic global install. Retry the failed boundary after restoration.
- **Inventory/history/source-list/ask/search read failure:** relay the relevant error without credentials. Retain any pinned identity, conversation and verified records; explain which required read failed. Ask for restored access/runtime or a corrected accessible identity. Resume with that read, not invented history or an answer from external knowledge. If an ask failed without returning conversation identity, read relevant history before continuing; failure does not prove history was unchanged.
- **Source not yet readable:** its title, upload presence or plausible Gemini answer cannot replace a supporting passage. Identify the source and required readable/access state, then pause affected verification. After the user reports readiness, retry read-only lookup.

### References and interpretation

For empty references, unmapped IDs, ambiguous mappings, missing cited text, or key-only citations:

1. Read/refresh the pinned Notebook's source ID/title mapping. A `[KEY]` in a synced title is a lookup clue, **not a source UUID**. Match it to this Notebook's listed source; unresolved/duplicate mappings require clarification or additional source lookup, not guessed IDs.
2. Use the dependency's source search for the claimed concept/supporting passage; narrow to a listed source only when its identity is established. A different source may independently support the claim, but does not repair the original citation identity: record that citation as unresolved.
3. Compare the claim with the actual passage. Classify it as **verified** (passage supports the bounded meaning), **unverified** (no usable support accessible), or **unsupported** (the proposed meaning is not established or conflicts with the passage).
4. Label any correction separately from the relayed proposal. For example, a **fixed evaluation constant** is not evidence of **dynamic control**: correct to the supported evaluation meaning or mark dynamic control unsupported **before** scope/block confirmation. A verified passage does not verify every interpretation attached to it.

Keep unresolved references and non-core claims as visible pending items; never put unsupported meaning into blocks or present unverified wording as a quotation. If a core block depends on an unverified/unsupported claim, stop for readable Notebook evidence or a user-confirmed, evidence-supported scope revision. User confirmation alone cannot verify a source claim.

### CIMO gaps

| Status | Meaning | Consequential next step |
| --- | --- | --- |
| Unclear | Intended meaning or scope role is ambiguous. | Ask a targeted scope question and use Notebook dialogue to distinguish plausible meanings if it changes scope/core blocks. |
| Evidence-insufficient | Meaning is understood, but available passages do not establish it. | Request supporting Notebook evidence; pause if core. A non-core gap remains visible rather than being fabricated. |
| Not applicable | The dimension/criterion does not apply to the chosen scope, not merely an unsuccessful lookup. | Explain why it is irrelevant; confirm if that decision changes scope/core blocks. Otherwise record it without an extra gate. |

An empty cell alone establishes none of these states. Never invent a common mechanism or outcome to complete CIMO. Ask only when the gap changes scope or core-block selection; harmless unknown detail can stay documented.

### Scope changes

When the user changes the main direction or introduces a scope-expanding concept (at any step, including translation):

1. Retain the pinned Notebook UUID and relevant conversation; keep verified source records and prior decisions as history.
2. Record the scope delta. Mark **affected prior scope/block approvals obsolete**, affected rendered queries superseded, and old evidence-to-scope/block links needing re-evaluation. A source passage can remain verified while no longer supporting the new core. Unaffected records can survive, but they do not authorize changed-scope output.
3. Return to Notebook evidence dialogue with the same conversation identity. Verify new/reinterpreted claims; pause if the new core lacks support. Then pass the main scope gate afresh.
4. Re-enter [main step 3](../SKILL.md#3-ask-gemini-for-search-blocks-and-confirm-roles) for revised block roles and a fresh block gate before rendering. Its block-logic, screening-only and NOT rules apply unchanged: neither a scope revision nor a failed lookup relaxes them.
