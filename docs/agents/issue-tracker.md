# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`
- **Read an issue**: `gh issue view <number> --comments`
- **List issues**: `gh issue list --state open`
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`.
- **Child ticket**: an issue linked to the map with `Part of #<map>` in body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
- **Blocking**: recorded as `Blocked by: #<n>` at top of child body.
- **Frontier query**: open child issues with no open blockers and no assignees.
- **Claim**: `gh issue edit <n> --add-assignee @me`.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append to map's Decisions so far.
