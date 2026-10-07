#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SOURCE_SKILLS="${REPO_ROOT}/skills"
MAIN_REPO="/home/ling/projects/research-toolkit"
SHIP_REPO="/home/ling/projects/research-toolkit-ship"

echo "==> Synchronizing skills from ${SOURCE_SKILLS}..."

if [ ! -d "${SOURCE_SKILLS}" ]; then
  echo "No skills directory found at ${SOURCE_SKILLS}."
  exit 0
fi

for skill_path in "${SOURCE_SKILLS}"/*; do
  if [ -d "${skill_path}" ]; then
    skill_name="$(basename "${skill_path}")"
    echo "Processing skill: ${skill_name}"

    # Sync to main repo if different
    if [ "${REPO_ROOT}" != "${MAIN_REPO}" ] && [ -d "${MAIN_REPO}/skills" ]; then
      mkdir -p "${MAIN_REPO}/skills/${skill_name}"
      cp -r "${skill_path}"/* "${MAIN_REPO}/skills/${skill_name}/"
      echo "  -> Synced to main repo: ${MAIN_REPO}/skills/${skill_name}"
    fi

    # Sync to ship repo if present
    if [ "${REPO_ROOT}" != "${SHIP_REPO}" ] && [ -d "${SHIP_REPO}/skills" ]; then
      mkdir -p "${SHIP_REPO}/skills/${skill_name}"
      cp -r "${skill_path}"/* "${SHIP_REPO}/skills/${skill_name}/"
      echo "  -> Synced to ship repo: ${SHIP_REPO}/skills/${skill_name}"
    fi

    # Ensure user global symlinks point to main repo
    mkdir -p "${HOME}/.gemini/config/skills" "${HOME}/.agents/skills"
    ln -sfn "${MAIN_REPO}/skills/${skill_name}" "${HOME}/.gemini/config/skills/${skill_name}"
    ln -sfn "${MAIN_REPO}/skills/${skill_name}" "${HOME}/.agents/skills/${skill_name}"
    echo "  -> Verified symlinks in ~/.gemini/config/skills and ~/.agents/skills"
  fi
done

echo "✅ Skills synchronized successfully."
