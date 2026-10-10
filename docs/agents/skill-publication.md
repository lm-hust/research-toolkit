# Skill trial and publication

`skills/` in the current checkout is the source. Trial installation creates links to that checkout; publication copies a snapshot. Neither mode selects other worktrees or global locations automatically.

## Trial in an isolated destination

After editing a skill, preview the selected names, then install to a disposable destination:

```bash
./scripts/sync-skills.sh --mode trial --skill whoami --skill gemini-notebook --target /tmp/research-toolkit-skill-trial --dry-run
./scripts/sync-skills.sh --mode trial --skill whoami --skill gemini-notebook --target /tmp/research-toolkit-skill-trial
```

Configure the intended consumer explicitly if you want it to load this trial. A directory of links is not itself proof that a running agent loaded the edited skill. Global installations are separate, explicit operations. Trial links are live: later source edits become visible through them.

Done when: the selected destination points to this checkout, no unrelated target changed, and the relevant consumer has been deliberately pointed at it when testing actual invocation.

## Publish after merge and acceptance

Run from the accepted, merged checkout, using the actual consumer installation directory:

```bash
./scripts/sync-skills.sh --mode publish --skill whoami --target /explicit/consumer/skills --dry-run
./scripts/sync-skills.sh --mode publish --skill whoami --target /explicit/consumer/skills
```

Publication creates ordinary directories independent of subsequent source edits. The script does not enforce GitHub merge/acceptance itself: verify these gates first using `delivery.md`. Supply `--source /explicit/skills/root` only when intentionally selecting a different source.

## Conflicts and recovery

The script requires explicit mode, target and skill names. It preflights all selected trees before any write. Differences (including stale files and invalid/broken targets) stop installation and list changed paths, without displaying file contents. Inspect them before choosing `--replace`; that flag explicitly approves replacing the selected targets, not everything in the destination.

Real target directories/files are renamed to `.SKILL.backup-<id>` before replacement and the backup is retained. Replacing a symlink changes the link itself, never its referent. Restore a retained backup manually if needed. Preflight is all-or-nothing for detected conflicts; a runtime filesystem failure can leave earlier selected skills installed, so inspect the reported plans before retrying. Avoid concurrent writers to the same target.

Targets inside the source tree, symlink installation roots, invalid skill names, and nested source symlinks are rejected. Nested symlinks in an existing target are a conflict; explicitly replacing that target preserves the original tree as a backup rather than following those links. No main/ship checkout or `~/.agents`/`~/.gemini` destination is hard-coded. Preserve pre-existing worktree files; publication is not permission to clean another worktree.

Done when: inspected changes are installed only at the explicit target and the consumer can read the selected skills. Deterministic installation tests run via `scripts/check.sh`; behavioral skill acceptance remains separate.
