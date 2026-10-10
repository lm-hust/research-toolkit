## Summary

<Smallest diagram, diff sketch or tree showing the change. Link the spec/tickets.>

## Evidence

- **Before:** <Observed failure or prior behavior.>
- **After:** <Exact verification command and result for the final commit.>

| Gate | Status (pending / passed / waived) | Applicable commit | Evidence link | Scope / remaining work |
|---|---|---|---|---|
| Automated verification | pending | — | — | — |
| Live service checks | pending | — | — | — |
| Human acceptance | pending | — | — | — |

Waivers require explicit user approval, reason and an evidence link. Keep Draft until gates are passed or explicitly waived. Evidence links must exist and support the claim; linking a smoke test is not full workflow acceptance. Publish procedural results only, never private sources or drafts.

### Review

Base SHA: <full SHA>
Final head SHA: <full SHA>
Standards: <report link, blockers resolved, remaining non-blocking heuristics>
Spec: <report link, blockers resolved, pending acceptance>
Review ledger: <private/local path or non-confidential artifact link>

## Merge Danger

**Door:** <one-way / two-way; distinguish code rollback from live-data rollback>

**Blast Radius:** <scope and irreversible effects>

Closes #<ticket>

Delivery workflow: `docs/agents/delivery.md`.
