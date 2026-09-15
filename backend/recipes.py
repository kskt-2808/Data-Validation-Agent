"""Compute-logic registry ("recipes").

A recipe is metadata the UI renders (label, formula, ledger columns, which
inputs it needs) plus an evaluator that turns one shift's readings into ledger
fields. Registering a calculation means adding an entry to RECIPES and, once it
is available, an evaluator in EVALUATORS.
"""
from __future__ import annotations

from compute import HOUR_MS, consumption_delta, coverage, run_hours, time_weighted_average

COVERAGE_WARN = 0.90
STATUSES = ("PASS", "WARN", "NO_DATA", "ERROR")

_HEAD = [
    {"key": "date", "label": "Shift Date", "type": "text"},
    {"key": "devID", "label": "Device ID", "type": "text"},
    {"key": "sensor", "label": "Sensor", "type": "text"},
    {"key": "shift", "label": "Window", "type": "text"},
]
_STATUS = [{"key": "status", "label": "Status", "type": "status"}]

RECIPES = [
    {
        "id": "consumption_delta", "group": "EMS", "available": True,
        "label": "Energy Consumption Delta (Last DP − First DP)",
        "formula": "Delta = (Last_Reading − First_Reading) × m ÷ unit_scale",
        "method": (
            "Uses raw readings inside the shift window [start, end). Readings below 0 are the "
            "meter's no-reading sentinel and are dropped. Consumption is the last valid reading "
            "minus the first, times m (c cancels in a difference). Fewer than two valid "
            "readings is NO DATA, never zero."
        ),
        "aggregate": "sum", "needsThreshold": False, "usesUnitScale": True,
        "totalLabel": "Total consumption", "avgLabel": "Average per shift", "peakLabel": "Peak shift",
        "columns": _HEAD + [
            {"key": "first_value", "label": "First Point (DP1)", "type": "number", "timeKey": "first_time"},
            {"key": "last_value", "label": "Last Point (DP2)", "type": "number", "timeKey": "last_time"},
            {"key": "raw_delta", "label": "Raw Delta", "type": "number"},
            {"key": "factor", "label": "Factor", "type": "factor"},
            {"key": "value", "label": "Computed Output", "type": "output"},
        ] + _STATUS,
    },
    {
        "id": "run_hours", "group": "OEE", "available": True,
        "label": "Run-Hours Duration (Threshold Time Sum)",
        "formula": "Run-Hours = Σ interval where (reading × m + c) ≥ threshold",
        "method": (
            "Each raw reading holds until the next one, for at most the max gap. Time where the "
            "calibrated reading is at or above the device's threshold counts as running. Time "
            "with no reading inside the max gap is Unknown and counts as neither running nor "
            "stopped, so Run + Stopped + Unknown = shift length. Computed from raw readings, "
            "not the platform's run-time endpoint, whose output has not been validated."
        ),
        "aggregate": "sum", "needsThreshold": True, "usesUnitScale": False,
        "totalLabel": "Total run-hours", "avgLabel": "Average run-hours per shift",
        "peakLabel": "Longest-running shift",
        "columns": _HEAD + [
            {"key": "threshold", "label": "Threshold", "type": "number"},
            {"key": "value", "label": "Run Hours", "type": "output"},
            {"key": "stopped_hours", "label": "Stopped Hours", "type": "number"},
            {"key": "unknown_hours", "label": "Unknown Hours", "type": "number"},
            {"key": "samples", "label": "Samples", "type": "integer"},
        ] + _STATUS,
    },
    {
        "id": "time_weighted_avg", "group": "Telemetry", "available": True,
        "label": "Time-Weighted Average (Avg Current, Avg PF)",
        "formula": "Avg = Σ((reading × m + c) × interval) ÷ Σ interval",
        "method": (
            "Each calibrated reading is weighted by how long it held, capped at the max gap. "
            "Unknown time is excluded from the average rather than treated as zero."
        ),
        "aggregate": "mean", "needsThreshold": False, "usesUnitScale": False,
        "totalLabel": "", "avgLabel": "Mean of shift averages", "peakLabel": "Highest shift average",
        "columns": _HEAD + [
            {"key": "value", "label": "Average", "type": "output"},
            {"key": "min", "label": "Min", "type": "number"},
            {"key": "max", "label": "Max", "type": "number"},
            {"key": "known_hours", "label": "Known Hours", "type": "number"},
            {"key": "samples", "label": "Samples", "type": "integer"},
        ] + _STATUS,
    },
    {
        "id": "availability_ratio", "group": "OEE / Future", "available": False,
        "label": "Availability Ratio (Run-Hours / Planned Hours)",
    },
    {
        "id": "specific_energy", "group": "EMS / Future", "available": False,
        "label": "Specific Energy Consumption (kWh / Output Units)",
    },
]
RECIPES_BY_ID = {r["id"]: r for r in RECIPES}


def scaled_unit(unit: str, scale: float) -> str:
    if scale == 1 or not unit:
        return unit
    if scale == 1000:
        return "M" + unit[1:] if unit.startswith("k") else "k" + unit
    return f"{unit} ÷ {scale:g}"


def output_unit(recipe: dict, target: dict, params: dict) -> str:
    if recipe["id"] == "run_hours":
        return "h"
    if recipe.get("usesUnitScale"):
        return scaled_unit(target["unit"], params["unitScale"])
    return target["unit"]


def _status(notes: list[str]) -> dict:
    return {"status": "WARN" if notes else "PASS", "notes": notes}


def _consumption(points, start_ms, end_ms, target, params):
    factor = target["m"] / params["unitScale"]
    r = consumption_delta(points, start_ms, end_ms, factor)
    if r is None:
        return {"status": "NO_DATA", "factor": factor,
                "notes": ["Fewer than two valid readings in the shift"]}
    notes = []
    if r["raw_delta"] < 0 or r["decreases"]:
        notes.append(f"Reading went down {r['decreases']} time(s) inside the shift "
                     "(meter reset or rollover?)")
    edge_gap = max(r["first_time"] - start_ms, end_ms - r["last_time"])
    if edge_gap > params["maxGapMs"]:
        notes.append(f"Readings start or stop {edge_gap / 60_000:.0f} min from a shift edge; "
                     "consumption in that time is missing")
    return {**r, "factor": factor, **_status(notes)}


def _run_hours(points, start_ms, end_ms, target, params):
    r = run_hours(points, start_ms, end_ms, target["threshold"], target["m"], target["c"],
                  params["maxGapMs"])
    if r is None:
        return {"status": "NO_DATA", "notes": ["No readings in the shift"]}
    notes = []
    if r["known_ms"] / (end_ms - start_ms) < COVERAGE_WARN:
        notes.append(f"{r['unknown_ms'] / HOUR_MS:.2f} h of the shift has no reading; "
                     "not counted as running or stopped")
    return {
        "value": r["running_ms"] / HOUR_MS,
        "stopped_hours": (r["known_ms"] - r["running_ms"]) / HOUR_MS,
        "unknown_hours": r["unknown_ms"] / HOUR_MS,
        "samples": r["samples"],
        **_status(notes),
    }


def _time_weighted_avg(points, start_ms, end_ms, target, params):
    r = time_weighted_average(points, start_ms, end_ms, target["m"], target["c"],
                              params["maxGapMs"])
    if r is None:
        return {"status": "NO_DATA", "notes": ["No readings in the shift"]}
    notes = []
    cov = coverage(points, start_ms, end_ms, params["maxGapMs"])
    if cov < COVERAGE_WARN:
        notes.append(f"Readings cover {cov:.0%} of the shift; the average uses known time only")
    return {
        "value": r["average"], "min": r["min"], "max": r["max"],
        "known_hours": r["known_ms"] / HOUR_MS, "samples": r["samples"],
        **_status(notes),
    }


EVALUATORS = {
    "consumption_delta": _consumption,
    "run_hours": _run_hours,
    "time_weighted_avg": _time_weighted_avg,
}


def evaluate(recipe: dict, points, start_ms: int, end_ms: int, target: dict, params: dict) -> dict:
    return EVALUATORS[recipe["id"]](points, start_ms, end_ms, target, params)


def summarize(rows: list[dict], recipe: dict) -> list[dict]:
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
            "total": sum(values) if recipe["aggregate"] == "sum" and values else None,
            "mean": sum(values) / len(values) if values else None,
            "valueCount": len(values),
            "peak": peak and {k: peak[k] for k in ("value", "date", "devID", "sensor")},
            "counts": {s: sum(1 for r in group if r["status"] == s) for s in STATUSES},
            "shifts": len(group),
        })
    return summary
