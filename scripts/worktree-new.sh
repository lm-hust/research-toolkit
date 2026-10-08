#!/usr/bin/env bash
# scripts/worktree-new.sh
# Safely provisions a new Git worktree from the integration branch, copying .env and configuring pre-commit hooks.
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <branch-name> <worktree-path> [base-ref]"
  exit 1
fi

BRANCH="$1"
TARGET_PATH="$2"
BASE_REF="${3:-HEAD}"

REPO_ROOT="$(git rev-parse --show-toplevel)"

echo "==> Creating worktree at ${TARGET_PATH} on branch ${BRANCH} (base: ${BASE_REF})..."
git worktree add -b "${BRANCH}" "${TARGET_PATH}" "${BASE_REF}"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  echo "==> Copying .env from ${REPO_ROOT} to ${TARGET_PATH}/.env..."
  cp "${REPO_ROOT}/.env" "${TARGET_PATH}/.env"
fi

echo "==> Configuring git hooks path in ${TARGET_PATH}..."
git -C "${TARGET_PATH}" config core.hooksPath .githooks

echo "✅ Worktree provisioned successfully at ${TARGET_PATH}."
