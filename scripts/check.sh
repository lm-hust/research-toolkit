#!/usr/bin/env bash
set -euo pipefail

echo "==> [1/3] Running ruff check..."
uv run --with ruff ruff check src/ tests/

echo "==> [2/3] Running mypy..."
uv run --with mypy mypy src/ tests/

echo "==> [3/3] Running pytest..."
uv run --with pytest pytest

echo "✅ All checks passed successfully!"
