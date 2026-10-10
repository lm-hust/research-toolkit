#!/usr/bin/env python3
"""Reduce source-list JSON to title-derived counts and explicitly selected candidates."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match", required=True, help="Regex over titles; never establishes source authority")
    args = parser.parse_args()
    try:
        pattern = re.compile(args.match, re.IGNORECASE)
        data = json.load(sys.stdin)
        if not isinstance(data, dict) or data.get("error") or not isinstance(data.get("sources"), list):
            raise ValueError("Expected successful source list JSON")
        years: Counter[str] = Counter()
        candidates = []
        for source in data["sources"]:
            title = source["title"]
            paper = re.fullmatch(r".+? - (\d{4}) - .+", title)
            if paper:
                years[paper.group(1)] += 1
            if pattern.search(title):
                candidates.append({"id": source["id"], "title": title,
                                   "title_kind": "paper_candidate" if paper else "unclassified"})
        print(json.dumps({"notebook_id": data.get("notebook_id"), "source_count": len(data["sources"]),
                          "paper_source_counts_by_year": dict(sorted(years.items())),
                          "candidates": candidates}, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
