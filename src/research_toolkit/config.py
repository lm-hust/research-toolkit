"""
src/research_toolkit/config.py
Configuration and automatic .env loading.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def load_env_file(path: Optional[Path] = None) -> None:
    """Loads environment variables from .env file into os.environ if present."""
    env_file = path or (Path.cwd() / ".env")
    if not env_file.is_file():
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        if not env_file.is_file():
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
