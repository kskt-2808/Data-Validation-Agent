"""Runs one validation request: resolve targets, fetch each shift, apply the recipe."""
from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from compute import clean, shift_windows
from iosense import UpstreamError
from recipes import RECIPES_BY_ID, evaluate, output_unit, summarize

SITE_TZ = ZoneInfo(os.environ.get("SITE_TIMEZONE", "Asia/Kolkata"))
SOURCE = "GET /api/account/deviceData/getDataCalibration/{devID}/{sensor}/{start}/{end}/false"
MAX_DAYS = 62
MAX_FETCHES = 1000
FETCH_WORKERS = 8
TIME_KEYS = ("first_time", "last_time")


def run_validation(client, devices_by_id: dict, body: dict) -> dict:
    recipe = RECIPES_BY_ID.get(body.get("recipe"))
    if not recipe or not recipe.get("available"):
        raise ValueError(f"Unknown or unavailable recipe: {body.get('recipe')!r}")

    first_day, last_day = _date(body.get("from"), "from"), _date(body.get("to"), "to")
    if last_day < first_day:
        raise ValueError("The end date is before the start date")
    if (last_day - first_day).days + 1 > MAX_DAYS:
        raise ValueError(f"Choose at most {MAX_DAYS} days")
    shift_start = _time(body.get("shiftStart"), "shiftStart")
    shift_end = _time(body.get("shiftEnd"), "shiftEnd")

    unit_scale = body.get("unitScale", 1)
    if unit_scale not in (1, 1000):
        raise ValueError("unitScale must be 1 or 1000")
    max_gap_min = _number(body.get("maxGapMinutes", 15), "maxGapMinutes")
    if not 0 < max_gap_min <= 1440:
        raise ValueError("maxGapMinutes must be between 0 and 1440")

    targets = [_target(t, devices_by_id, recipe) for t in body.get("targets") or []]
    if not targets:
        raise ValueError("Choose at least one device and sensor")
    windows = shift_windows(first_day, last_day, shift_start, shift_end, SITE_TZ)
    if len(targets) * len(windows) > MAX_FETCHES:
        raise ValueError(f"{len(targets)} device-sensor pairs × {len(windows)} days is "
                         f"{len(targets) * len(windows)} fetches; the limit is {MAX_FETCHES}")

    params = {"unitScale": unit_scale, "maxGapMs": int(max_gap_min * 60_000),
              "shift": f"{shift_start:%H:%M} – {shift_end:%H:%M}"}
    jobs = [(t, w) for t in targets for w in windows]
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        rows = list(pool.map(lambda job: _row(client, recipe, params, *job), jobs))
    rows.sort(key=lambda r: (r["date"], r["devID"], r["sensor"]))

    return {
        "recipe": recipe,
        "params": {"from": first_day.isoformat(), "to": last_day.isoformat(),
                   "shift": params["shift"], "unitScale": unit_scale,
                   "maxGapMinutes": max_gap_min},
        "timezone": SITE_TZ.key,
        "generatedAt": datetime.now(SITE_TZ).isoformat(timespec="seconds"),
        "source": SOURCE,
        "rows": rows,
        "summary": summarize(rows, recipe),
    }


def _row(client, recipe: dict, params: dict, target: dict, window) -> dict:
    day, start_ms, end_ms = window
    row = {
        "date": day.isoformat(), "shift": params["shift"],
        "devID": target["devID"], "devName": target["devName"],
        "sensor": target["sensor"], "sensorName": target["sensorName"],
        "unit": output_unit(recipe, target, params),
        "m": target["m"], "c": target["c"], "factorSource": target["factorSource"],
        "threshold": target.get("threshold"),
        "windowStart": _iso(start_ms), "windowEnd": _iso(end_ms),
        "value": None, "notes": [],
    }
    try:
        # Look back one max gap so the value in force at the window start is known.
        raw = client.raw_series(target["devID"], target["sensor"],
                                start_ms - params["maxGapMs"], end_ms)
    except UpstreamError as err:
        row.update(status="ERROR", notes=[f"Platform returned no usable response: {err}"])
        return row
    result = evaluate(recipe, clean(raw), start_ms, end_ms, target, params)
    for key in TIME_KEYS:
        if result.get(key) is not None:
            result[key] = _iso(result[key])
    row.update(result)
    return row


def _target(t: dict, devices_by_id: dict, recipe: dict) -> dict:
    device = devices_by_id.get(t.get("devID"))
    if not device:
        raise ValueError(f"Device {t.get('devID')!r} is not in your account")
    sensor = next((s for s in device["sensors"] if s["id"] == t.get("sensor")), None)
    if not sensor:
        raise ValueError(f"{device['devID']} has no sensor {t.get('sensor')!r}")
    overridden = t.get("m") is not None or t.get("c") is not None
    target = {
        "devID": device["devID"], "devName": device["devName"],
        "sensor": sensor["id"], "sensorName": sensor["name"], "unit": sensor["unit"],
        "m": _number(t["m"], "m") if t.get("m") is not None else sensor["m"],
        "c": _number(t["c"], "c") if t.get("c") is not None else sensor["c"],
        "factorSource": "override" if overridden else "device config",
    }
    if target["m"] == 0:
        raise ValueError(f"Calibration m for {device['devID']} / {sensor['id']} is 0")
    if recipe.get("needsThreshold"):
        if t.get("threshold") in (None, ""):
            raise ValueError(f"Set a run threshold for {device['devID']} / {sensor['id']}")
        target["threshold"] = _number(t["threshold"], "threshold")
    return target


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, SITE_TZ).isoformat(timespec="seconds")


def _date(value, name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"'{name}' must be a date like 2026-09-01") from None


def _time(value, name: str) -> time:
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"'{name}' must be a time like 07:00") from None


def _number(value, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"'{name}' must be a number") from None
    if isinstance(value, bool) or not math.isfinite(number):
        raise ValueError(f"'{name}' must be a number")
    return number
