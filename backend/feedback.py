"""Feedback capture: an append-only file, plus an optional chat webhook.

The file lives outside the repository by default, because a redeploy replaces
the checkout and would otherwise erase what people wrote.

Environment:
  FEEDBACK_FILE         where to append (default ~/newton-feedback/feedback.jsonl)
  FEEDBACK_WEBHOOK_URL  Teams or Slack incoming webhook; both accept {"text": ...}
  FEEDBACK_ADMIN_KEY    enables the CSV export, which requires ?key=<this>
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import threading
from datetime import datetime
from pathlib import Path

import requests

from validation import SITE_TZ

STORE = Path(os.environ.get("FEEDBACK_FILE", Path.home() / "newton-feedback" / "feedback.jsonl"))
WEBHOOK_URL = os.environ.get("FEEDBACK_WEBHOOK_URL", "").strip()
ADMIN_KEY = os.environ.get("FEEDBACK_ADMIN_KEY", "").strip()
MAX_COMMENT = 2000
FACES = {1: "😞 unhappy", 2: "🙁 poor", 3: "😐 neutral", 4: "🙂 good", 5: "😀 great"}
COLUMNS = ("time", "rating", "comment", "formula", "from", "to", "shift", "targets",
           "shifts", "pass", "warn", "noData", "error", "submitter")

_lock = threading.Lock()


def record(body: dict, token: str = "") -> dict:
    """Validate one submission, append it, and announce it. Returns the stored entry."""
    rating = body.get("rating")
    if rating not in (None, ""):
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            raise ValueError("rating must be a whole number from 1 to 5") from None
        if not 1 <= rating <= 5:
            raise ValueError("rating must be a whole number from 1 to 5")
    else:
        rating = None
    comment = str(body.get("comment") or "").strip()[:MAX_COMMENT]
    if rating is None and not comment:
        raise ValueError("Add a rating or a note before sending")

    context = body.get("context") or {}
    counts = context.get("counts") or {}
    entry = {
        "time": datetime.now(SITE_TZ).isoformat(timespec="seconds"),
        "rating": rating,
        "comment": comment,
        "formula": context.get("formula"),
        "from": context.get("from"),
        "to": context.get("to"),
        "shift": context.get("shift"),
        "targets": context.get("targets"),
        "shifts": context.get("shifts"),
        "pass": counts.get("PASS"),
        "warn": counts.get("WARN"),
        "noData": counts.get("NO_DATA"),
        "error": counts.get("ERROR"),
        # One-way id: enough to see one person filing ten notes, never the token itself.
        "submitter": hashlib.sha256(token.encode()).hexdigest()[:8] if token else None,
    }
    _append(entry)
    _notify(entry)
    return entry


def _append(entry: dict) -> None:
    with _lock:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        with STORE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _notify(entry: dict) -> None:
    """Post to Teams/Slack. Never fails the submission: the file is the record."""
    if not WEBHOOK_URL:
        return
    rating = FACES.get(entry["rating"], "no rating")
    run = " · ".join(str(x) for x in [entry.get("formula"), entry.get("from") and
                    f"{entry['from']} to {entry['to']}", entry.get("targets") and
                    f"{entry['targets']} device-sensor pairs"] if x)
    lines = [f"**Newton feedback — {rating}**"]
    if run:
        lines.append(run)
    if entry["comment"]:
        lines.append(f"> {entry['comment']}")
    try:
        requests.post(WEBHOOK_URL, json={"text": "\n\n".join(lines)}, timeout=10)
    except requests.RequestException as err:
        print(f"Feedback webhook failed (entry is still saved): {err}")


def export_csv() -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    if STORE.exists():
        for line in STORE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                writer.writerow(json.loads(line))
    return buffer.getvalue()
