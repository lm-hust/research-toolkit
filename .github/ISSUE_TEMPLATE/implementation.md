---
name: Implementation and acceptance ticket
about: A scoped behavior with dependencies, test seams and explicit acceptance gates
---

## Spec and dependencies

Spec: <issue URL or path>
Blocked by: <issue numbers, or none>

## Behavior and boundaries

<Observable behavior, non-goals, protected data, and effects allowed on external services.>

## Test seams

<Pre-agreed public interfaces, observable outputs and fault/restart scenarios.>

## Acceptance gates

| Gate | Status (pending / passed / waived) | Applicable commit | Evidence link | What it proves / what remains |
|---|---|---|---|---|
| Automated verification | pending | — | — | — |
| Live service checks | pending | — | — | — |
| Human acceptance | pending | — | — | — |

A passed gate links actual evidence. A waiver records the user's explicit approval, reason and evidence link; agents cannot grant themselves waivers. Mark non-applicable gates as explicitly waived, not silently passed. Inventory/query smoke tests do not prove a complete draft workflow.

Keep private source titles, content and drafts out of the issue. Report procedural outcomes only.

Workflow and optional machine validation: `docs/agents/delivery.md`.
