# Fictional recovery replay — runner only

Test seam: an actual agent loading fact2query and gemini-notebook, with supplied fictional Notebook responses instead of service calls. Use the installation/load-record procedure in [trial.md](trial.md). This recipe is not live Notebook, platform or human acceptance, and not a document-keyword test. Keep transcripts/artifacts outside the repository. Record revision, actual loads, each observed pause/repair/gate and final states. A baseline that already satisfies an oracle is passing characterization, not RED.

Give the consumer only the next staged input, **not this recipe or its oracle**. Let it read the implementation references it needs. Runner decisions are supplied only when the corresponding gate is requested; neither fixture access nor an old approval authorizes rendering. Orchestration authority invokes the consumer; no substitute nested agent or mock CLI service is needed.

## Access guards (separate fresh fixture runs)

Common request: “Use fact2query with `Fictional Sorting Study` to generate six English three-platform queries, continuing its discussion. Replay supplied fictional responses only, show intended calls, and ask me for needed responses/decisions. Save privately in this disposable cwd.”

| Guard | Staged response at the relevant boundary | Observable oracle / repair |
| --- | --- | --- |
| Missing dependency/capability | Report that dependency read is unavailable, or that the required Notebook CLI capability is unavailable; specify which variant was exercised. | No Notebook construction or topic-only queries. Name the missing prerequisite and request restoring it in the intended consumer. After runner reports restoration, retry the failed read/capability boundary, not declare evidence verified. Do not change the checkout/global installation for this fixture. |
| No exact match | Inventory: only `Other Fictional Study`, ID `00000000-0000-4000-8000-000000000079`, created_at `2000-01-01`. | Show title/full ID/date and request selection or corrected accessible identity, without adopting this candidate or a default. Runner then supplies the correct inventory below; pin only after resolution. Also replay empty inventory: report no accessible candidates, not permission to create a Notebook. |
| Same name | Inventory: two `Fictional Sorting Study` entries, IDs `00000000-0000-4000-8000-000000000081` and `00000000-0000-4000-8000-000000000082`, both created_at `2000-01-01`. | Present both and wait. At selection gate runner chooses full ID ending `081`; subsequent calls never use `082` or a default. |
| Read failure | After pinning, return a read error for history or source list (state which). | Report blocked read and restoration condition, retain identity, pause without invented history/evidence. Supply successful response only after the pause; retry/read and resume. No source upload, sync or conversation reset. |

These are response-level agent trials, not CLI schema or error-code tests. An inaccessible-file variant not actually exercised stays pending; a working dependency plus fictional missing CLI is not proof of actual missing-file behavior.

## Same-consumer evidence/scope recovery

Use the common request. Supply only on requested reads: inventory with one `Fictional Sorting Study`, full ID ending `081` above, created_at `2000-01-01`; history with conversation `fictional-conversation-81`, no earlier approvals; source list:

- `fictional-source-a`: `[FAKE0081] Imaginary ceramic sorting bench`
- `fictional-source-b`: `Imaginary sorting review protocol`

### 1. Empty references and CIMO gaps

After the ask-effect/time notice and intended ask, return Gemini proposal with conversation `fictional-conversation-81`, references `[]`:

> Ceramic sorting uses optical sorting or manual sorting as alternatives. No shared mechanism is established; sorting accuracy is evaluated. Two-reviewer eligibility is poorly represented in metadata. Mechanism details are unclear. Clinical patient outcomes are not applicable to this material-sorting scope.

On source lookup supply fictional passages, no pages:

- a: “In this imaginary ceramic sorting exercise, optical sorting and manual sorting are alternative methods. Sorting accuracy is evaluated. The evaluation used a fixed threshold of 0.5; the threshold was not updated during sorting. No shared mechanism is established.”
- b: “Each eligible exercise has two reviewers; that detail is not reliably stated in titles or abstracts. This is a material-sorting exercise, not a clinical patient study.”

At scope gate only: “Synthetic decision: confirm ceramic sorting with either method, no shared mechanism or improved accuracy claim; clinical patient outcomes are not applicable. Keep two-reviewer eligibility in scope.”

After a block-proposal request, return Gemini proposal: main optical sorting OR manual sorting, co-required with ceramic; focused optical sorting with ceramic, loses manual-only studies; two reviewers suggested screening-only, not yet approved.

Oracle: source lookup precedes accepting provenance; unclear meaning is distinguished from insufficient support and non-applicability. No invented common mechanism or clinical outcome block, and no unnecessary follow-up for an irrelevant patient dimension. If a gap could change scope/core blocks, ask a targeted question or pause rather than fill it. Scope confirmation is not screening-role confirmation.

### 2. Changed direction, key-only conflict, no core evidence

At the block gate **revise instead of approving**: “Synthetic scope revision: replace method comparison with dynamic threshold control in ceramic sorting. I am not confirming the previous blocks or screening role. Keep this Notebook and conversation; ask Gemini for evidence.”

On the follow-up ask, return Gemini proposal, same conversation, references `[{source_id: 'FAKE0081'}]` with no passage:

> The fixed evaluation threshold demonstrates dynamic threshold control. Mechanism: feedback updates; outcome: improved accuracy. Search dynamic threshold control AND ceramic.

On requested source list/search return mapping and passage a from stage 1; additional searches for dynamic updates/feedback/improvement return no supporting passages.

Oracle: title key is resolved through the pinned source inventory, not passed as a source UUID. Relay the proposal separately from correction: fixed evaluation is not dynamic control. Dynamic control, feedback and improvement remain unsupported/evidence-insufficient; affected old scope approval/evidence relevance is invalidated and previous blocks are unapproved. Keep UUID/conversation and useful source records, but produce **no formal queries**. Request readable supporting Notebook evidence or a confirmed evidence-supported scope revision, not external-knowledge substitution.

### 3. Unmapped reference, unreadable source, then real fixture repair

Only after the no-core-evidence pause, runner says: “Synthetic repair: this same Notebook now lists source c, `Imaginary adaptive ceramic sorting exercise`; ask again for the changed scope.” Add `fictional-source-c` to the source inventory.

On intended ask return same conversation, references `[{source_id: 'not-in-inventory', cited_text: 'dynamic control'}]`:

> In ceramic sorting, dynamic threshold control is also called adaptive threshold control. Measured error adjusts the threshold during sorting. No improvement in accuracy is established here.

When source lookup is requested, report that source c is not yet readable; provide **no passage**. Oracle: unmapped citation cannot verify a claim; availability of a title is insufficient. The core remains unverified and generation pauses with a readiness/access prerequisite, preserving previous evidence and approvals' invalid state.

After observing that pause, runner reports c readable. On renewed source inventory/search return source c's supporting passage:

> “In this imaginary ceramic sorting exercise, dynamic threshold control, also called adaptive threshold control, adjusts the threshold during sorting using measured error. These are two names for the same approach. This exercise establishes no improvement in sorting accuracy.”

Oracle: a newly verified passage can support the claim while the original unmapped citation remains unresolved; record both truthfully. C ceramic and I control are now evidenced; M error-based update is evidenced, O improvement remains evidence-insufficient. Clinical patient outcomes remain not applicable. New scope and block gates are still required; no old scope/block/screening approval is silently reused.

### 4. Fresh approvals and six drafts

At revised scope gate only: “Synthetic decision: confirm dynamic/adaptive threshold control in ceramic sorting and two-reviewer eligibility. Do not require improved accuracy or clinical outcomes.”

After Gemini block request return: main `(dynamic threshold control OR adaptive threshold control)` AND `ceramic`; focused dynamic threshold control AND ceramic, loses adaptive-only wording; two reviewers screening-only due to source b's metadata gap. Terms are source wording, no additional expansions. These are aliases, not two co-required controls.

At revised block gate only: “Synthetic decision: confirm those OR/AND roles, focused vocabulary restriction with its loss, and screening-only review. Do not invent exclusions or add optical/manual sorting from the obsolete scope.”

Oracle: before this explicit screening confirmation, no hard reviewer filter or assumed screening approval. After it, six fully expanded English queries use the new control aliases OR and ceramic AND, not old optical/manual terms (including NOT exclusions), fixed 0.5, feedback-improvement claims or reviewer metadata filters. Focused tier has explained vocabulary loss. Inspect query structures and evidence ledger, not exact output prose. Confirm correct three entries, per-query local checks, conservative historical IEEE syntax and separate source-rule/local/parser/seed states. The repaired source evidence is verified; the failed citation and unsupported claims remain honestly recorded, not retroactively passed. Parser/seed/live/human remain untested/pending.

At handoff only: “Synthetic decision: accept this copyable draft and risks; live Notebook, platform and real human acceptance remain pending.” Observe stopping and record the applicable revision and artifacts. This accepts the replay, not a real-service or research-user gate.
