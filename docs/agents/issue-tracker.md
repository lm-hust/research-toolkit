# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`
- **Read an issue**: `gh issue view <number> --comments`
- **List issues**: `gh issue list --state open`
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

## Acceptance records

Use `.github/ISSUE_TEMPLATE/implementation.md` and the PR template to distinguish automated verification, live service checks, and human acceptance. Passed gates link actual evidence for the applicable commit; pending gates remain pending until completed or explicitly waived by the user. See [delivery.md](delivery.md) for readiness validation and review ledgers. Keep confidential source content out of tracker records.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`.
- **Child ticket**: an issue linked to the map with `Part of #<map>` in body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
- **Blocking**: recorded as `Blocked by: #<n>` at top of child body.
- **Frontier query**: open child issues with no open blockers and no assignees.
- **Claim**: `gh issue edit <n> --add-assignee @me`.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append to map's Decisions so far.
