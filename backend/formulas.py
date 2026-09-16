"""Compute-logic registry.

Formulas are declared in formulas.json: label, formula, ledger columns and the
parameters the UI renders. Each names a `compute` kind implemented here, so
adding a calculation that reuses an existing kind is a JSON edit only — the UI
renders whatever the registry declares.
"""
from __future__ import annotations

import json
from pathlib import Path

from compute import (HOUR_MS, average_value, consumption_delta, coverage, integrate,
                     run_hours, time_weighted_average)

_REGISTRY = json.loads((Path(__file__).parent / "formulas.json").read_text())
UNIT_CONVERSIONS = _REGISTRY["unitConversions"]

COVERAGE_WARN = 0.90
STATUSES = ("PASS", "WARN", "NO_DATA", "ERROR")
# Kinds whose answer depends on how long a single reading is trusted.
GAP_KINDS = ("delta", "threshold_time", "time_weighted_mean", "availability", "integrate")

_HEAD = [
    {"key": "date", "label": "Shift Date", "type": "text"},
    {"key": "devID", "label": "Device ID", "type": "text"},
    {"key": "sensor", "label": "Sensor", "type": "text"},
    {"key": "shift", "label": "Window", "type": "text"},
]
_STATUS = [{"key": "status", "label": "Status", "type": "status"}]

_OUTPUT_UNIT_PARAM = {
    "key": "outputUnit", "scope": "run", "type": "unit", "label": "Output unit",
    "help": "Show the result in another unit of the same kind — Wh in kWh, A in mA, "
            "hours in minutes. Native keeps the sensor's own unit. Thresholds stay in "
            "the sensor's unit either way.",
}
_GAP_PARAM = {
    "key": "maxGapMinutes", "scope": "run", "type": "number", "label": "Gap tolerance (minutes)",
    "default": 15, "min": 1, "max": 1440,
    "help": "If a device stops sending readings, Newton trusts its last reading for this "
            "long. Time beyond that is counted as Unknown — neither running nor stopped — "
            "instead of being guessed, and the shift is flagged.",
}


def _publish(formula: dict) -> dict:
    """Registry entry plus the standard columns and parameters every formula gets."""
    published = dict(formula)
    published["columns"] = _HEAD + list(formula.get("columns") or []) + _STATUS
    standard = []
    if (formula.get("unit") or {}).get("convertible"):
        standard.append(_OUTPUT_UNIT_PARAM)
    if formula.get("compute") in GAP_KINDS:
        standard.append(_GAP_PARAM)
    published["params"] = standard + list(formula.get("params") or [])
    return published


FORMULAS = [_publish(r) for r in _REGISTRY["formulas"]]
FORMULAS_BY_ID = {r["id"]: r for r in FORMULAS}


def base_unit(formula: dict, target: dict, params: dict | None = None) -> str:
    params = params or {}
    source = (formula.get("unit") or {}).get("source")
    if source == "hours":
        return "h"
    if source == "percent":
        return "%"
    if source == "label":
        # The sensor reads a rate; the total is in whatever the operator names.
        return params.get("outputUnitLabel") or target["unit"]
    return target["unit"]


def resolve_unit(formula: dict, target: dict, params: dict) -> tuple[str, float]:
    """(unit the report shows, divisor that converts the native value into it)."""
    base = base_unit(formula, target, params)
    chosen = params.get("outputUnit")
    if not chosen or chosen == base:
        return base, 1.0
    factor = (UNIT_CONVERSIONS.get(base) or {}).get(chosen)
    if not factor:
        raise ValueError(f"{target['devID']} / {target['sensor']} reports in "
                         f"{base or 'no unit'}, which cannot be shown as {chosen}")
    return chosen, float(factor)


def _status(notes: list[str]) -> dict:
    return {"status": "WARN" if notes else "PASS", "notes": notes}


def _coverage_note(points, start_ms, end_ms, params, unknown_ms) -> list[str]:
    if (end_ms - start_ms - unknown_ms) / (end_ms - start_ms) >= COVERAGE_WARN:
        return []
    return [f"{unknown_ms / HOUR_MS:.2f} h of the shift has no reading within the gap "
            f"tolerance; not counted either way"]


def _delta(points, start_ms, end_ms, target, params):
    factor = target["m"] / target["unitDivisor"]
    result = consumption_delta(points, start_ms, end_ms, factor)
    if result is None:
        return {"status": "NO_DATA", "factor": factor,
                "notes": ["Fewer than two valid readings in the shift"]}
    notes = []
    if result["raw_delta"] < 0 or result["decreases"]:
        notes.append(f"Reading went down {result['decreases']} time(s) inside the shift "
                     "(meter reset or rollover?)")
    edge_gap = max(result["first_time"] - start_ms, end_ms - result["last_time"])
    if edge_gap > params["maxGapMs"]:
        notes.append(f"Readings start or stop {edge_gap / 60_000:.0f} min from a shift "
                     "edge; consumption in that time is missing")
    return {**result, "factor": factor, **_status(notes)}


def _threshold_time(points, start_ms, end_ms, target, params):
    result = run_hours(points, start_ms, end_ms, target["threshold"], target["m"],
                       target["c"], params["maxGapMs"])
    if result is None:
        return {"status": "NO_DATA", "notes": ["No readings in the shift"]}
    divisor = target["unitDivisor"]
    notes = _coverage_note(points, start_ms, end_ms, params, result["unknown_ms"])
    stopped_ms = result["known_ms"] - result["running_ms"]
    return {
        "value": result["running_ms"] / HOUR_MS / divisor,
        "stopped_hours": stopped_ms / HOUR_MS / divisor,
        "unknown_hours": result["unknown_ms"] / HOUR_MS / divisor,
        "samples": result["samples"],
        **_status(notes),
    }


def _mean(points, start_ms, end_ms, target, params):
    result = average_value(points, start_ms, end_ms, target["m"], target["c"])
    if result is None:
        return {"status": "NO_DATA", "notes": ["No readings in the shift"]}
    divisor = target["unitDivisor"]
    return {
        "value": result["average"] / divisor,
        "min": result["min"] / divisor,
        "max": result["max"] / divisor,
        "samples": result["samples"],
        **_status([]),
    }


def _time_weighted_mean(points, start_ms, end_ms, target, params):
    result = time_weighted_average(points, start_ms, end_ms, target["m"], target["c"],
                                   params["maxGapMs"])
    if result is None:
        return {"status": "NO_DATA", "notes": ["No readings in the shift"]}
    divisor = target["unitDivisor"]
    notes = _coverage_note(points, start_ms, end_ms, params, result["unknown_ms"])
    return {
        "value": result["average"] / divisor,
        "min": result["min"] / divisor,
        "max": result["max"] / divisor,
        "known_hours": result["known_ms"] / HOUR_MS,
        "samples": result["samples"],
        **_status(notes),
    }


def _availability(points, start_ms, end_ms, target, params):
    result = run_hours(points, start_ms, end_ms, target["threshold"], target["m"],
                       target["c"], params["maxGapMs"])
    if result is None:
        return {"status": "NO_DATA", "notes": ["No readings in the shift"]}
    planned = params.get("plannedHours") or (end_ms - start_ms) / HOUR_MS
    running = result["running_ms"] / HOUR_MS
    notes = _coverage_note(points, start_ms, end_ms, params, result["unknown_ms"])
    if running > planned:
        notes.append(f"Ran {running:.2f} h, longer than the {planned:g} h planned")
    return {
        "value": running / planned * 100,
        "run_hours": running,
        "planned_hours": planned,
        "unknown_hours": result["unknown_ms"] / HOUR_MS,
        **_status(notes),
    }


def _load_factor(points, start_ms, end_ms, target, params):
    result = average_value(points, start_ms, end_ms, target["m"], target["c"])
    if result is None:
        return {"status": "NO_DATA", "notes": ["No readings in the shift"]}
    if result["max"] <= 0:
        return {"average": result["average"], "peak": result["max"],
                "samples": result["samples"], "status": "NO_DATA",
                "notes": ["Peak reading is 0, so a load factor cannot be computed"]}
    return {
        "value": result["average"] / result["max"] * 100,
        "average": result["average"],
        "peak": result["max"],
        "samples": result["samples"],
        **_status([]),
    }


def _integrate(points, start_ms, end_ms, target, params):
    result = integrate(points, start_ms, end_ms, target["m"], target["c"],
                       params["maxGapMs"], params.get("rateBasisSeconds") or 3600)
    if result is None:
        return {"status": "NO_DATA", "notes": ["No readings in the shift"]}
    notes = _coverage_note(points, start_ms, end_ms, params, result["unknown_ms"])
    return {
        "value": result["total"],
        "min": result["min"], "max": result["max"],
        "known_hours": result["known_ms"] / HOUR_MS,
        "unknown_hours": result["unknown_ms"] / HOUR_MS,
        "samples": result["samples"],
        **_status(notes),
    }


EVALUATORS = {
    "integrate": _integrate,
    "delta": _delta,
    "threshold_time": _threshold_time,
    "mean": _mean,
    "time_weighted_mean": _time_weighted_mean,
    "availability": _availability,
    "load_factor": _load_factor,
}


def evaluate(formula: dict, points, start_ms: int, end_ms: int, target: dict, params: dict) -> dict:
    return EVALUATORS[formula["compute"]](points, start_ms, end_ms, target, params)


def summarize(rows: list[dict], formula: dict) -> list[dict]:
    """Audit-card figures, one group per output unit (units are never added together)."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row.get("unit") or "", []).append(row)
    summary = []
    for unit, group in groups.items():
        counted = [r for r in group if r.get("value") is not None and r["status"] in ("PASS", "WARN")]
        values = [r["value"] for r in counted]
        peak = max(counted, key=lambda r: r["value"], default=None)
        summary.append({
            "unit": unit,
            "total": sum(values) if formula["aggregate"] == "sum" and values else None,
            "mean": sum(values) / len(values) if values else None,
            "valueCount": len(values),
            "peak": peak and {k: peak[k] for k in ("value", "date", "devID", "sensor")},
            "counts": {s: sum(1 for r in group if r["status"] == s) for s in STATUSES},
            "shifts": len(group),
        })
    return summary
