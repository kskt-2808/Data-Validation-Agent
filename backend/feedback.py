"""Feedback capture: an append-only file, plus an optional chat webhook.

The file lives outside the repository by default, because a redeploy replaces
the checkout and would otherwise erase what people wrote.

Environment:
  FEEDBACK_FILE         where to append (default ~/newton-feedback/feedback.jsonl)
  FEEDBACK_WEBHOOK_URL  Teams Workflow, Slack, or a classic Teams connector URL
  FEEDBACK_WEBHOOK_FORMAT  "card" or "text"; by default the URL decides
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

def setting(name: str, default: str = "") -> str:
    """Read a setting, forgiving the case of the key.

    Settings are typed by hand into AI Studio Manager's Env Config, and a key
    like Feedback_webhook_URL would otherwise be ignored in silence, because
    environment variables are case-sensitive.
    """
    if name in os.environ:
        return os.environ[name]
    for key, value in os.environ.items():
        if key.lower() == name.lower():
            print(f"Using {key} for {name}: the name is read case-insensitively, "
                  f"but rename it to {name} to be explicit.")
            return value
    return default


STORE = Path(setting("FEEDBACK_FILE") or Path.home() / "newton-feedback" / "feedback.jsonl")
WEBHOOK_URL = setting("FEEDBACK_WEBHOOK_URL").strip()
ADMIN_KEY = setting("FEEDBACK_ADMIN_KEY").strip()
WEBHOOK_FORMAT = setting("FEEDBACK_WEBHOOK_FORMAT").strip().lower()
# Teams Workflows (Power Automate) replaced the retired Office 365 connectors and
# expects an Adaptive Card. Slack and the old connectors take {"text": ...}.
CARD_HOSTS = ("logic.azure.com", "logic.azure.us", "powerautomate.com", "powerplatform.com")
MAX_COMMENT = 2000
FACES = {1: "😞 unhappy", 2: "🙁 poor", 3: "😐 neutral", 4: "🙂 good", 5: "😀 great"}
COLUMNS = ("time", "rating", "comment", "formula", "from", "to", "shift", "targets",
           "shifts", "pass", "warn", "noData", "error", "submitter")

_lock = threading.Lock()

print(f"Feedback: storing in {STORE}; webhook "
      f"{'configured (' + ('card' if WEBHOOK_URL and any(h in WEBHOOK_URL for h in CARD_HOSTS) else 'text') + ' format)' if WEBHOOK_URL else 'NOT configured — set FEEDBACK_WEBHOOK_URL'}")


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


def wants_card(url: str) -> bool:
    """Teams Workflow URLs need an Adaptive Card; everything else takes plain text."""
    if WEBHOOK_FORMAT in ("card", "text"):
        return WEBHOOK_FORMAT == "card"
    return any(host in url for host in CARD_HOSTS)


def build_payload(entry: dict, url: str) -> dict:
    """The body to POST, in whichever shape the destination understands."""
    heading = f"Newton feedback — {FACES.get(entry['rating'], 'no rating')}"
    run = " · ".join(str(x) for x in [
        entry.get("formula"),
        entry.get("from") and f"{entry['from']} to {entry['to']}",
        entry.get("targets") and f"{entry['targets']} device-sensor pairs",
    ] if x)
    if not wants_card(url):
        lines = [f"**{heading}**"] + ([run] if run else []) + \
                ([f"> {entry['comment']}"] if entry["comment"] else [])
        return {"text": "\n\n".join(lines)}
    body = [{"type": "TextBlock", "text": heading, "weight": "Bolder", "size": "Medium", "wrap": True}]
    if run:
        body.append({"type": "TextBlock", "text": run, "isSubtle": True, "wrap": True, "spacing": "None"})
    if entry["comment"]:
        body.append({"type": "TextBlock", "text": entry["comment"], "wrap": True})
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.4", "body": body,
            },
        }],
    }


def _notify(entry: dict) -> None:
    """Post to Teams/Slack. Never fails the submission: the file is the record."""
    if not WEBHOOK_URL:
        return
    try:
        response = requests.post(WEBHOOK_URL, json=build_payload(entry, WEBHOOK_URL), timeout=10)
        if response.status_code >= 300:
            print(f"Feedback webhook returned {response.status_code} (entry is still saved): "
                  f"{response.text[:200]}")
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
