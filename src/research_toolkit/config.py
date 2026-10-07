"""
src/research_toolkit/config.py
Configuration and automatic .env loading with Git worktree fallback.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def find_env_file(path: Optional[Path] = None) -> Optional[Path]:
    """Locates .env file across current directory, repo root, or git worktree parent."""
    if path and path.is_file():
        return path

    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for c in candidates:
        if c.is_file():
            return c

    # Check for git worktree linkage in repo root
    repo_root = Path(__file__).resolve().parent.parent.parent
    git_file = repo_root / ".git"
    if git_file.is_file():
        try:
            content = git_file.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                gitdir = Path(content.split(":", 1)[1].strip()).resolve()
                # gitdir points to <main_repo>/.git/worktrees/<name>
                main_repo_root = gitdir.parent.parent.parent
                main_env = main_repo_root / ".env"
                if main_env.is_file():
                    return main_env
        except Exception:
            pass

    return None


def load_env_file(path: Optional[Path] = None) -> None:
    """Loads environment variables from .env file into os.environ if present."""
    env_file = find_env_file(path)
    if not env_file or not env_file.is_file():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if len(v) >= 2 and ((v[0] == "'" and v[-1] == "'") or (v[0] == '"' and v[-1] == '"')):
                v = v[1:-1]
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


# Automatically load on import
load_env_file()
