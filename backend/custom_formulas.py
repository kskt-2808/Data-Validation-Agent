"""Formulas written by users in the app.

Stored outside the repository, like feedback, because a deploy replaces the
checkout. These are evaluated by the sandboxed expression language and are
marked as custom wherever they appear, so a number nobody reviewed never looks
like one of the verified built-ins.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import expressions

SITE_TZ = ZoneInfo(os.environ.get("SITE_TIMEZONE", "Asia/Kolkata"))
STORE = Path(os.environ.get("CUSTOM_FORMULAS_FILE",
                            Path.home() / "newton-formulas" / "custom.json"))
MAX_FORMULAS = 200
MAX_LABEL = 60
_lock = threading.Lock()

COLUMNS = [
    {"key": "value", "label": "Result", "type": "output"},
    {"key": "samples", "label": "Samples", "type": "integer"},
    {"key": "known_hours", "label": "Known Hours", "type": "number"},
    {"key": "unknown_hours", "label": "Unknown Hours", "type": "number"},
]


def author_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:8] if token else "unknown"


def load() -> list[dict]:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _write(entries: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def create(body: dict, token: str = "") -> dict:
    label = str(body.get("label") or "").strip()
    if not label:
        raise ValueError("Give the formula a name")
    if len(label) > MAX_LABEL:
        raise ValueError(f"Keep the name under {MAX_LABEL} characters")
    expression = str(body.get("expression") or "").strip()
    expressions.parse(expression)                      # raises ExpressionError if unusable
    aggregate = body.get("aggregate") or "sum"
    if aggregate not in ("sum", "mean"):
        raise ValueError("Totals can be added up (sum) or averaged (mean)")

    entry = {
        "id": _new_id(label),
        "label": label,
        "expression": expression,
        "unit": str(body.get("unit") or "").strip()[:16],
        "aggregate": aggregate,
        "notes": str(body.get("notes") or "").strip()[:500],
        "author": author_id(token),
        "created": datetime.now(SITE_TZ).isoformat(timespec="seconds"),
    }
    with _lock:
        entries = load()
        if len(entries) >= MAX_FORMULAS:
            raise ValueError(f"There are already {MAX_FORMULAS} custom formulas; delete one first")
        if any(e["label"].lower() == label.lower() for e in entries):
            raise ValueError(f"A custom formula called {label!r} already exists")
        entries.append(entry)
        _write(entries)
    return entry


def delete(formula_id: str, token: str = "") -> dict:
    with _lock:
        entries = load()
        entry = next((e for e in entries if e["id"] == formula_id), None)
        if not entry:
            raise ValueError("That formula no longer exists")
        if entry["author"] != author_id(token):
            raise ValueError("Only whoever wrote a formula can delete it")
        _write([e for e in entries if e["id"] != formula_id])
    return entry


def _new_id(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40] or "formula"
    return f"custom_{slug}_{hashlib.sha256(label.encode()).hexdigest()[:6]}"


def registry_entries(token: str = "") -> list[dict]:
    """Stored formulas in the shape the registry and the UI expect."""
    mine = author_id(token)
    entries = []
    for entry in load():
        entries.append({
            "id": entry["id"],
            "group": "Custom",
            "label": entry["label"],
            "compute": "expression",
            "available": True,
            "custom": True,
            "mine": entry["author"] == mine,
            "author": entry["author"],
            "created": entry["created"],
            "expression": entry["expression"],
            "method": (f"Custom formula, written in the app by {entry['author']} on "
                       f"{entry['created'][:10]}. Newton evaluates the expression above "
                       f"against each shift's readings. It has not been reviewed or tested "
                       f"like the built-in formulas."
                       + (f" Author's note: {entry['notes']}" if entry["notes"] else "")),
            "aggregate": entry["aggregate"],
            "unit": {"source": "fixed", "value": entry["unit"], "convertible": False},
            "labels": {"total": f"Total {entry['label'].lower()}",
                       "avg": "Average per shift", "peak": "Peak shift"},
            "columns": COLUMNS,
        })
    return entries
