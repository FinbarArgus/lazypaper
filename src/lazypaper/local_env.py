"""Minimal local .env loader for running Lazypaper outside GitHub Actions."""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return key, value


def load_local_env(env_path: str | Path | None = None) -> Path | None:
    """Load environment variables from .env/.env.local without overriding existing env.

    Intended for local runs only; GitHub Actions already provides real environment variables.
    Returns the path that was loaded, or None if no file was found.
    """
    if env_path is not None:
        candidates = [Path(env_path)]
    else:
        root = Path(__file__).resolve().parent.parent.parent
        candidates = [root / ".env.local", root / ".env"]

    for candidate in candidates:
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(raw_line)
            if not parsed:
                continue
            key, value = parsed
            os.environ.setdefault(key, value)
        return candidate
    return None