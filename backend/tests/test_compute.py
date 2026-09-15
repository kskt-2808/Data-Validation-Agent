import json
import sys
import unittest
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from compute import (HOUR_MS, clean, consumption_delta, run_hours, shift_windows,  # noqa: E402
                     time_weighted_average)

FIXTURES = Path(__file__).parent / "fixtures"
IST = ZoneInfo("Asia/Kolkata")
MIN = 60_000


def load(name):
    fixture = json.loads((FIXTURES / name).read_text())
    return fixture, clean(fixture["points"])


class ShiftWindows(unittest.TestCase):
    def test_overnight_shift_ends_next_day(self):
        [(_, start, end)] = shift_windows(date(2026, 9, 14), date(2026, 9, 14), time(7), time(7), IST)
        self.assertEqual((start, end), (1789349400000, 1789435800000))

    def test_same_day_shift(self):
        [(_, start, end)] = shift_windows(date(2026, 9, 14), date(2026, 9, 14), time(6), time(14), IST)
        self.assertEqual(end - start, 8 * HOUR_MS)

    def test_one_window_per_day_inclusive(self):
        windows = shift_windows(date(2026, 9, 1), date(2026, 9, 14), time(7), time(7), IST)
        self.assertEqual(len(windows), 14)


class Consumption(unittest.TestCase):
    def test_matches_platform_first_last_for_evoem_c1(self):
        # consumption/getOperationDataWithTime for this shift returned
        # first 2668320.25 @ 01:30:31Z and last 2669588.25 @ 01:28:51Z.
        fixture, points = load("evoem_c1_d30_2026-09-14.json")
        r = consumption_delta(points, fixture["start_ms"], fixture["end_ms"], 1.0)
        self.assertEqual(r["first_value"], 2668320.25)
        self.assertEqual(r["last_value"], 2669588.25)
        self.assertAlmostEqual(r["value"], 1268.0)
        self.assertEqual(r["decreases"], 0)

    def test_reading_at_window_end_belongs_to_next_shift(self):
        points = [(0, 10.0), (500, 15.0), (1000, 20.0)]
        self.assertEqual(consumption_delta(points, 0, 1000, 1.0)["raw_delta"], 5.0)

    def test_sentinel_dropped_and_factor_applied(self):
        points = [(0, -1.0), (100, 1000.0), (200, -1.0), (300, 3400.0)]
        r = consumption_delta(points, 0, 1000, 0.001)
        self.assertAlmostEqual(r["value"], 2.4)
        self.assertEqual(r["samples"], 2)

    def test_fewer_than_two_readings_is_no_data_not_zero(self):
        self.assertIsNone(consumption_delta([(100, 5.0)], 0, 1000, 1.0))
        self.assertIsNone(consumption_delta([(100, -1.0), (200, -1.0)], 0, 1000, 1.0))


class RunHours(unittest.TestCase):
    def test_sums_intervals_at_or_above_threshold(self):
        # 0-10 min at 150 A, 10-30 at 100 A, 30-60 at exactly 140 A (inclusive).
        points = [(0, 150.0), (10 * MIN, 100.0), (30 * MIN, 140.0)]
        r = run_hours(points, 0, 60 * MIN, 140, max_gap_ms=60 * MIN)
        self.assertEqual(r["running_ms"], 40 * MIN)
        self.assertEqual(r["unknown_ms"], 0)

    def test_gap_longer_than_max_gap_is_unknown(self):
        points = [(0, 150.0), (40 * MIN, 150.0)]
        r = run_hours(points, 0, 60 * MIN, 140, max_gap_ms=15 * MIN)
        self.assertEqual(r["running_ms"], 30 * MIN)
        self.assertEqual(r["unknown_ms"], 30 * MIN)

    def test_lookback_reading_sets_value_at_window_start(self):
        points = [(-5 * MIN, 150.0), (10 * MIN, 0.0)]
        r = run_hours(points, 0, 60 * MIN, 140, max_gap_ms=15 * MIN)
        self.assertEqual(r["running_ms"], 10 * MIN)

    def test_calibration_applied_before_threshold(self):
        r = run_hours([(0, 150_000.0)], 0, 10 * MIN, 140, m=0.001, max_gap_ms=10 * MIN)
        self.assertEqual(r["running_ms"], 10 * MIN)

    def test_no_readings_is_no_data(self):
        self.assertIsNone(run_hours([], 0, 60 * MIN, 140))

    def test_evoem_c1_hours_partition_the_shift(self):
        fixture, points = load("evoem_c1_d6_2026-09-14.json")
        start, end = fixture["start_ms"], fixture["end_ms"]
        r = run_hours(points, start, end, 3, max_gap_ms=15 * MIN)
        stopped = r["known_ms"] - r["running_ms"]
        self.assertEqual(r["running_ms"] + stopped + r["unknown_ms"], end - start)
        # The fixture has no lookback, so only the 31 s before the first reading are unknown.
        self.assertEqual(r["unknown_ms"], 31_000)


class TimeWeightedAverage(unittest.TestCase):
    def test_weights_by_duration(self):
        points = [(0, 10.0), (45 * MIN, 50.0)]
        r = time_weighted_average(points, 0, 60 * MIN, max_gap_ms=60 * MIN)
        self.assertAlmostEqual(r["average"], 20.0)

    def test_unknown_time_excluded_not_zero(self):
        points = [(0, 10.0)]
        r = time_weighted_average(points, 0, 60 * MIN, max_gap_ms=15 * MIN)
        self.assertAlmostEqual(r["average"], 10.0)
        self.assertEqual(r["unknown_ms"], 45 * MIN)


if __name__ == "__main__":
    unittest.main()
