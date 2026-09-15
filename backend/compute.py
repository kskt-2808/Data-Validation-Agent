"""Calculation core for Newton.

Pure functions: readings in, numbers out, no I/O. Every figure in a report can
be recomputed by hand from the ledger fields these functions return.

Conventions (validated against platform data, see README "Validation log"):
  * Points are (epoch_ms, raw_value) with calibration NOT applied. Callers pass
    m and c explicitly so the factor used is visible in the ledger.
  * A shift window is half-open [start, end). A reading stamped exactly at the
    end belongs to the next shift; otherwise adjacent shifts share a reading.
  * A reading holds until the next reading, for at most max_gap_ms. Time beyond
    that is "unknown": it counts as neither running nor stopped.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

HOUR_MS = 3_600_000

Point = tuple[int, float]


def shift_windows(first_day: date, last_day: date, shift_start: time,
                  shift_end: time, tz: ZoneInfo) -> list[tuple[date, int, int]]:
    """One (shift_date, start_ms, end_ms) per calendar day, both days inclusive.

    A shift_end at or before shift_start ends on the next day, so 07:00 to 07:00
    is a 24 h shift.
    """
    windows = []
    day = first_day
    while day <= last_day:
        start = datetime.combine(day, shift_start, tzinfo=tz)
        end_day = day if shift_end > shift_start else day + timedelta(days=1)
        end = datetime.combine(end_day, shift_end, tzinfo=tz)
        windows.append((day, int(start.timestamp() * 1000), int(end.timestamp() * 1000)))
        day += timedelta(days=1)
    return windows


def clean(points) -> list[Point]:
    """Numeric readings only, sorted by time, one reading per timestamp."""
    by_time = {}
    for t, v in points:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        by_time[int(t)] = float(v)
    return sorted(by_time.items())


def held_segments(points: list[Point], start_ms: int, end_ms: int,
                  max_gap_ms: int) -> list[tuple[int, int, float]]:
    """(seg_start, seg_end, raw_value) for each span of the window whose value is known.

    Pass the reading just before start_ms too (fetch with a max_gap lookback) so
    the value at the start of the window is known.
    """
    segments = []
    for i, (t, v) in enumerate(points):
        next_t = points[i + 1][0] if i + 1 < len(points) else end_ms
        seg_start = max(t, start_ms)
        seg_end = min(next_t, t + max_gap_ms, end_ms)
        if seg_end > seg_start:
            segments.append((seg_start, seg_end, v))
    return segments


def coverage(points: list[Point], start_ms: int, end_ms: int, max_gap_ms: int) -> float:
    """Fraction of the window whose value is known."""
    known = sum(b - a for a, b, _ in held_segments(points, start_ms, end_ms, max_gap_ms))
    return known / (end_ms - start_ms)


def consumption_delta(points: list[Point], start_ms: int, end_ms: int,
                      factor: float) -> dict | None:
    """Last valid reading in the window minus the first, times factor.

    Negative readings are the meter's no-reading sentinel (-1) and are dropped.
    c cancels in a difference, so only the multiplier applies. Returns None
    (no data, never zero) when fewer than two valid readings exist.
    """
    inside = [(t, v) for t, v in points if start_ms <= t < end_ms and v >= 0]
    if len(inside) < 2:
        return None
    (t1, v1), (t2, v2) = inside[0], inside[-1]
    raw = v2 - v1
    return {
        "first_time": t1, "first_value": v1,
        "last_time": t2, "last_value": v2,
        "raw_delta": raw, "value": raw * factor,
        "samples": len(inside),
        "decreases": sum(1 for (_, a), (_, b) in zip(inside, inside[1:]) if b < a),
    }


def run_hours(points: list[Point], start_ms: int, end_ms: int, threshold: float,
              m: float = 1.0, c: float = 0.0, max_gap_ms: int = 15 * 60_000) -> dict | None:
    """Time in the window where the calibrated reading is at or above threshold.

    Returns running, known and unknown milliseconds (running + stopped + unknown
    = window length), or None when no reading covers any of the window.
    """
    segments = held_segments(points, start_ms, end_ms, max_gap_ms)
    if not segments:
        return None
    known = sum(b - a for a, b, _ in segments)
    return {
        "running_ms": sum(b - a for a, b, v in segments if v * m + c >= threshold),
        "known_ms": known,
        "unknown_ms": (end_ms - start_ms) - known,
        "samples": sum(1 for t, _ in points if start_ms <= t < end_ms),
    }


def time_weighted_average(points: list[Point], start_ms: int, end_ms: int,
                          m: float = 1.0, c: float = 0.0,
                          max_gap_ms: int = 15 * 60_000) -> dict | None:
    """Calibrated readings weighted by how long each held; unknown time is excluded."""
    segments = held_segments(points, start_ms, end_ms, max_gap_ms)
    if not segments:
        return None
    known = sum(b - a for a, b, _ in segments)
    calibrated = [v * m + c for _, _, v in segments]
    return {
        "average": sum(cv * (b - a) for cv, (a, b, _) in zip(calibrated, segments)) / known,
        "min": min(calibrated),
        "max": max(calibrated),
        "known_ms": known,
        "unknown_ms": (end_ms - start_ms) - known,
        "samples": sum(1 for t, _ in points if start_ms <= t < end_ms),
    }
