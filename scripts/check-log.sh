#!/usr/bin/env bash
# Keep the check's exit status while displaying the tail of its complete log.
set -euo pipefail
if [ "$#" -lt 1 ]; then
  echo "Usage: $0 LOG_PATH [COMMAND ARG...] (default: scripts/check.sh)" >&2
  exit 2
fi
LOG="$1"
shift
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$#" -eq 0 ]; then
  set -- "${SCRIPT_DIR}/check.sh"
fi
mkdir -p "$(dirname "$LOG")"
if "$@" >"$LOG" 2>&1; then
  status=0
else
  status=$?
fi
tail -n 80 "$LOG" || true
printf '\nCheck exit status: %s; full log: %s\n' "$status" "$LOG"
exit "$status"
