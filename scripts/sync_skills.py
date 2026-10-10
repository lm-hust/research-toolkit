#!/usr/bin/env python3
"""Explicit, conflict-checked skill trials (links) and publications (snapshots)."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path


def inventory(directory: Path) -> dict[str, str]:
    """Compare complete trees, including empty directories; reject nested symlinks."""
    if not directory.is_dir():
        raise ValueError(f"Not a skill directory: {directory}")
    files: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Nested symlink is not publishable: {path}")
        relative = path.relative_to(directory).as_posix()
        files[relative] = "directory" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "skills")
    parser.add_argument("--target", type=Path, required=True, help="Explicit installation root")
    parser.add_argument("--skill", action="append", required=True, help="Selected name; repeatable")
    parser.add_argument("--mode", choices=("trial", "publish"), required=True,
                        help="trial links this checkout; publish copies a snapshot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true", help="Approve differences; retain directory backups")
    args = parser.parse_args()
    source = args.source.resolve()
    target = args.target.expanduser().absolute()
    try:
        if target.is_symlink():
            raise ValueError(f"Installation root must not be a symlink: {target}")
        if target.resolve().is_relative_to(source):
            raise ValueError("Installation root must be outside the source skills tree")
        plans: list[tuple[Path, Path, bool]] = []
        conflicts: list[str] = []
        for name in dict.fromkeys(args.skill):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
                raise ValueError(f"Invalid skill name: {name}")
            src, dst = source / name, target / name
            if src.is_symlink() or not (src / "SKILL.md").is_file():
                raise ValueError(f"Missing real skill directory with SKILL.md: {src}")
            wanted = inventory(src)
            exists = os.path.lexists(dst)
            same = False
            if exists:
                try:
                    current = inventory(dst)
                except ValueError:
                    current = {"<invalid target>": ""}
                changed = sorted(k for k in wanted.keys() | current.keys() if wanted.get(k) != current.get(k))
                if changed:
                    print(f"Differences for {name}: {', '.join(changed)}", file=sys.stderr)
                    if not args.replace:
                        conflicts.append(name)
                same = not changed and (
                    (args.mode == "trial" and dst.is_symlink() and dst.resolve() == src)
                    or (args.mode == "publish" and not dst.is_symlink())
                )
            plans.append((src, dst, same))
            print(f"{args.mode}: {src} -> {dst}{' (unchanged)' if same else ''}")
        if conflicts:
            raise ValueError(f"Refusing differences in {', '.join(conflicts)}; inspect then explicitly --replace")
        if args.dry_run:
            print("Dry run: no files or links changed")
            return 0
        target.mkdir(parents=True, exist_ok=True)
        for src, dst, same in plans:
            if same:
                continue
            staging = Path(tempfile.mkdtemp(prefix=f".sync-{src.name}-", dir=target))
            staged = staging / src.name
            try:
                if args.mode == "trial":
                    staged.symlink_to(src, target_is_directory=True)
                else:
                    shutil.copytree(src, staged)
                if dst.exists() and not dst.is_symlink():
                    backup = target / f".{src.name}.backup-{uuid.uuid4().hex}"
                    dst.rename(backup)
                    try:
                        os.replace(staged, dst)
                    except OSError:
                        backup.rename(dst)
                        raise
                    print(f"Preserved previous target: {backup}")
                else:
                    # Replace the link itself, never the directory it points to.
                    os.replace(staged, dst)
            finally:
                shutil.rmtree(staging)
        return 0
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
