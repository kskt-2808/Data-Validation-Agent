"""Load the repository's .env before anything reads os.environ.

AI Studio Manager stores the environment variables you set in its UI as a .env
file at the repository root; its pm2 config only passes PORT and NODE_ENV, so
without this the settings would be silently ignored. Real environment variables
always win, so a shell export still overrides the file.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(os.environ.get("ENV_FILE", Path(__file__).resolve().parent.parent / ".env"))


def load(path: Path = ENV_FILE) -> dict[str, str]:
    """Apply KEY=value lines from `path`. Returns what was applied."""
    applied: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return applied
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].replace('\\"', '"')
        if key and key not in os.environ:
            os.environ[key] = value
            applied[key] = value
    return applied


load()
