#!/usr/bin/env bash
set -euo pipefail

# Maintained agent tooling; the archived CLI prototype is not a production check target.
AGENT_SCRIPTS=(scripts/sync_skills.py scripts/check_acceptance.py scripts/review_scope.py scripts/notebook_inventory.py)

echo "==> [1/3] Running ruff check..."
uv run --with ruff ruff check src/ tests/ "${AGENT_SCRIPTS[@]}"

echo "==> [2/3] Running mypy..."
uv run --with mypy --with pytest mypy src/ tests/ "${AGENT_SCRIPTS[@]}"

echo "==> [3/3] Running pytest..."
uv run --with pytest pytest

echo "✅ All checks passed successfully!"
