#!/usr/bin/env python3
"""Validate acceptance gates; optionally check GitHub evidence exists using gh."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def evidence_endpoint(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query:
        raise ValueError(f"Use a canonical GitHub evidence link: {url}")
    match = re.fullmatch(r"/([^/]+)/([^/]+)/(issues|pull)/(\d+)", parsed.path)
    if match:
        owner, repo, kind, number = match.groups()
        if parsed.fragment:
            comment = re.fullmatch(r"issuecomment-(\d+)", parsed.fragment)
            if not comment:
                raise ValueError(f"Unsupported evidence anchor: {url}")
            return f"repos/{owner}/{repo}/issues/comments/{comment.group(1)}"
        return f"repos/{owner}/{repo}/{'pulls' if kind == 'pull' else 'issues'}/{number}"
    match = re.fullmatch(r"/([^/]+)/([^/]+)/actions/runs/(\d+)(?:/job/(\d+))?", parsed.path)
    if match and not parsed.fragment:
        owner, repo, run, job = match.groups()
        return f"repos/{owner}/{repo}/actions/{'jobs/' + job if job else 'runs/' + run}"
    raise ValueError(f"Unsupported GitHub evidence URL: {url}")


def verify_link(url: str, cache: dict[str, dict[str, Any]]) -> None:
    def fetch(endpoint: str) -> dict[str, Any]:
        if endpoint not in cache:
            result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True, check=False, timeout=30)
            if result.returncode:
                raise ValueError(f"Evidence unavailable: {endpoint}; gh exit {result.returncode}")
            payload = json.loads(result.stdout)
            if not isinstance(payload, dict):
                raise ValueError(f"Unexpected evidence response: {endpoint}")
            cache[endpoint] = payload
        return cache[endpoint]

    resource = fetch(evidence_endpoint(url))
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    owner, repo = parts[:2]
    if parts[2] in ("issues", "pull") and parsed.fragment:
        number = parts[3]
        fetch(f"repos/{owner}/{repo}/{'pulls' if parts[2] == 'pull' else 'issues'}/{number}")
        expected = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
        if str(resource.get("issue_url", "")).lower() != expected.lower():
            raise ValueError(f"Comment does not belong to the supplied issue/PR: {url}")
    elif parts[2] == "actions" and len(parts) == 7:
        run = parts[4]
        fetch(f"repos/{owner}/{repo}/actions/runs/{run}")
        if resource.get("run_id") != int(run):
            raise ValueError(f"Job does not belong to the supplied Actions run: {url}")


def validate(data: Any, ready: bool, verify_links: bool, expected_head: str | None) -> None:
    if not isinstance(data, dict) or not re.fullmatch(r"[0-9a-f]{40}", str(data.get("head", ""))):
        raise ValueError("Record must pin a full lowercase head SHA")
    if expected_head and data["head"] != expected_head:
        raise ValueError("Acceptance record head does not match --head; revalidate evidence")
    gates = data.get("gates")
    if not isinstance(gates, dict) or set(gates) != {"automated", "live", "human"}:
        raise ValueError("Record requires exactly automated, live, human gates")
    links: set[str] = set()
    for name, gate in gates.items():
        if not isinstance(gate, dict) or gate.get("status") not in ("passed", "pending", "waived"):
            raise ValueError(f"Invalid status for {name}")
        status = gate["status"]
        evidence = gate.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(link, str) for link in evidence):
            raise ValueError(f"{name}: evidence must be a list of links")
        if status in ("passed", "waived") and not evidence:
            raise ValueError(f"{name}: {status} requires evidence")
        reason = gate.get("reason")
        if status in ("pending", "waived") and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError(f"{name}: {status} requires a reason")
        approver = gate.get("approved_by")
        if status == "waived" and (not isinstance(approver, str) or not approver.strip()):
            raise ValueError(f"{name}: waiver requires an explicit approver")
        if ready and status == "pending":
            raise ValueError(f"{name}: pending acceptance prevents Ready")
        for link in evidence:
            evidence_endpoint(link)  # validate URL shape even for offline checks
            links.add(link)
        print(f"{name}: {status} ({len(evidence)} evidence links)")
    if verify_links:
        cache: dict[str, dict[str, Any]] = {}
        for link in sorted(links):
            verify_link(link, cache)
        print(f"Verified {len(links)} evidence links and their parent resources; reviewers must evaluate contents")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--ready", action="store_true", help="Reject pending gates")
    parser.add_argument("--verify-links", action="store_true", help="Read-only gh API existence checks")
    parser.add_argument("--head", help="Expected current commit SHA")
    args = parser.parse_args()
    try:
        validate(json.loads(args.record.read_text(encoding="utf-8")), args.ready, args.verify_links, args.head)
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
