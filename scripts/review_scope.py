#!/usr/bin/env python3
"""Pin a review's refs and produce a portable ledger; follow-ups use only the repair diff."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base", help="Required for the initial review")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--spec", help="Issue URL or specification path; no confidential content")
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Output exists; use a new round file to preserve review history")
        head = git(args.repo, "rev-parse", "--verify", f"{args.head}^{{commit}}")
        previous: dict[str, Any] = {}
        if args.previous:
            previous = json.loads(args.previous.read_text(encoding="utf-8"))
            base = previous["base"]
            if args.base and git(args.repo, "rev-parse", f"{args.base}^{{commit}}") != base:
                raise ValueError("Follow-up base differs from the original review")
            compare = previous["head"]
            git(args.repo, "merge-base", "--is-ancestor", compare, head)
            diff_args = [compare, head]
        else:
            if not args.base:
                raise ValueError("Initial review requires --base")
            base = git(args.repo, "rev-parse", "--verify", f"{args.base}^{{commit}}")
            compare = base
            diff_args = [f"{base}...{head}"]
        files = git(args.repo, "diff", "--name-only", *diff_args).splitlines()
        if not files:
            raise ValueError("Empty review diff")
        record = {
            "base": base, "head": head, "comparison_base": compare,
            "mode": "repair" if args.previous else "full",
            "diff_command": ["git", "diff", *diff_args],
            "commits": git(args.repo, "log", "--oneline", f"{compare}..{head}").splitlines(),
            "changed_files": files,
            "spec": args.spec or previous.get("spec"),
            "standards": previous.get("standards", ["CODING_STANDARDS.md", "CONTEXT.md"]),
            "findings": previous.get("findings", []),
            "reviewed_head": None,
        }
        if not record["spec"]:
            raise ValueError("Specify --spec (or explicitly 'none' when no spec exists)")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(record, indent=2) + "\n")
        print(f"{record['mode']} review: {len(files)} files; ledger: {args.output}")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
