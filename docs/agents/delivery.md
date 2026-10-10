# Integration, review and acceptance

Use this workflow when completing tickets, reviewing an integration branch, or making a PR Ready. Keep substantive standards in `CODING_STANDARDS.md`; mechanical properties belong in tests/checks.

## Integration preflight

Before dispatching ticket workers, fetch the base branch and integrate its current commit into the integration branch. Record that SHA. Workers branch from this integrated point. If main moves later, integrate again and review the actual combined diff. Inspect automatic merges too: absence of conflict markers does not prove semantic correctness.

Done when: the integration branch includes the recorded base, its working tree is understood, and `scripts/check.sh` passes.

## Bounded two-axis review

Create a ledger before the initial full Standards + Spec review:

```bash
uv run python scripts/review_scope.py --base origin/main --spec https://github.com/OWNER/REPO/issues/NUMBER --output .scratch/reviews/feature/round-1.json
```

The ledger pins commit SHAs, diff command, commit list, changed files, spec, standards and findings. Send the two axes to separate read-only reviewers. Give each a bounded output and record findings as:

```json
{"id":"S1","axis":"spec","path":"src/example.py","status":"open","evidence":"reproducer or source rule","verified_head":null}
```

Fix each finding with a public-interface regression test. For follow-up review:

```bash
uv run python scripts/review_scope.py --previous .scratch/reviews/feature/round-1.json --output .scratch/reviews/feature/round-2.json
```

This preserves findings and requests only the repair diff. Ask reviewers to verify the named findings and direct regressions. Broaden review only when a repair changes a shared contract or an unreviewed integration lands. Provider failure or quota exhaustion is not a review result: preserve the ledger and retry that axis with an available read-only reviewer. Check provider availability before dispatch rather than repeatedly submitting failing jobs.

After review, update finding status, evidence and `verified_head`; set `reviewed_head` only once both axes have reviewed the applicable scope. Never reuse an old head as evidence for a newer unreviewed patch. Retain separate Standards and Spec reports; a smell heuristic is not an automatic blocker.

Done when: no unresolved blocking findings, both axes accounted for at the final head, and verification passes. Do not repeatedly re-read the entire feature just to verify a localized repair.

## Acceptance evidence

Use the issue and PR templates. Separate automated verification, live service checks and human acceptance. Each passed gate names what actually ran, the applicable commit and an evidence link. A live inventory/query smoke test does not prove a user-confirmed draft workflow.

Store only non-confidential acceptance metadata in the repo/tracker. A local acceptance record has this shape (replace the example SHA/URL):

```json
{
  "head": "0123456789012345678901234567890123456789",
  "gates": {
    "automated": {"status":"passed","evidence":["https://github.com/OWNER/REPO/actions/runs/1"]},
    "live": {"status":"pending","reason":"Not yet run","evidence":[]},
    "human": {"status":"pending","reason":"Awaiting user confirmation","evidence":[]}
  }
}
```

Validate structure without network access, then check referenced GitHub resources exist:

```bash
uv run python scripts/check_acceptance.py .scratch/acceptance.json --head "$(git rev-parse HEAD)"
uv run python scripts/check_acceptance.py .scratch/acceptance.json --head "$(git rev-parse HEAD)" --verify-links --ready
```

`--ready` rejects pending gates. `waived` requires `reason`, `approved_by` and an evidence link to explicit human approval; the agent never grants itself a waiver. Links may be issue/PR pages, issue comments, or Actions runs/jobs. Existence checks do not prove CI passed, ran against that SHA, or that a comment contains sufficient acceptance: reviewers inspect those facts. Never claim evidence exists without reading it. No automatic network check runs during local tests/CI.

Done when: every gate is passed or explicitly waived by the user, evidence exists and supports the claim, and PR metadata reflects the real status. Keep Draft when a required gate remains pending, or ask the user whether they explicitly accept deferral. Merge and ticket closure follow that decision.

## Reliable check logs

```bash
./scripts/check-log.sh /tmp/research-toolkit-check.log
# Also accepts an explicit command for a targeted check:
./scripts/check-log.sh /tmp/targeted-check.log uv run --with pytest pytest tests/test_sync_notebook_cli.py -q
```

The wrapper prints the last 80 lines, keeps the complete log, and exits with the command's original status. Use `uv run python` and `uv run --with pytest pytest` rather than assuming bare `python`/`pytest` are installed. `scripts/check.sh` remains the single verification command for pre-commit and CI.

## External-service test scenarios

`tests/notebook_fakes.py` exposes file-upload commit/response loss, deletion failures/commit loss, delayed upload visibility, stale deleted-source listings and peak source counts. `tests/test_notebook_fault_matrix.py` exercises bounded fault combinations and input permutations through the CLI.

Reviewers check partial-success reporting, actual capacity, ownership before cleanup, and restart behavior together. When a new race is found, add an executable scenario at the existing seam; avoid substituting a steering-file warning for a reproducible check.
