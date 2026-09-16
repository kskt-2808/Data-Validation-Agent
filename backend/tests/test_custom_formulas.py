import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import custom_formulas  # noqa: E402
import formulas  # noqa: E402
from expressions import ExpressionError  # noqa: E402
from test_validation import DEVICES, FakeClient, request  # noqa: E402
from validation import run_validation  # noqa: E402

AUTHOR = "Bearer someone"
OTHER = "Bearer someone-else"


class CustomFormulas(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        original = custom_formulas.STORE
        custom_formulas.STORE = Path(tmp.name) / "nested" / "custom.json"
        self.addCleanup(lambda: setattr(custom_formulas, "STORE", original))
        self.client = FakeClient()

    def make(self, **overrides):
        body = {"label": "Night flow", "expression": "hours_above(3)", "unit": "h",
                "aggregate": "sum"}
        body.update(overrides)
        return custom_formulas.create(body, AUTHOR)

    def test_a_saved_formula_joins_the_registry_and_runs(self):
        entry = self.make(label="Pump hours", expression="hours_above(3)", unit="h")
        listed = {f["id"]: f for f in formulas.all_formulas(AUTHOR)}
        self.assertIn(entry["id"], listed)
        self.assertTrue(listed[entry["id"]]["custom"])
        self.assertTrue(listed[entry["id"]]["mine"])
        self.assertIn("has not been reviewed", listed[entry["id"]]["method"])

        body = request(formula=entry["id"], to="2026-09-14",
                       targets=[{"devID": "EVOEM_C1", "sensor": "D6"}])
        row = next(r for r in run_validation(self.client, DEVICES, body, AUTHOR)["rows"]
                   if r["date"] == "2026-09-14")
        self.assertEqual(row["status"], "PASS")
        self.assertEqual(row["unit"], "h")

        built_in = request(formula="run_hours", to="2026-09-14",
                           targets=[{"devID": "EVOEM_C1", "sensor": "D6", "threshold": 3}])
        same = next(r for r in run_validation(self.client, DEVICES, built_in)["rows"]
                    if r["date"] == "2026-09-14")
        self.assertAlmostEqual(row["value"], same["value"])   # agrees with the built-in

    def test_energy_expression_matches_the_built_in_formula(self):
        entry = self.make(label="My consumption", expression="delta", unit="kWh")
        body = request(formula=entry["id"], to="2026-09-14",
                       targets=[{"devID": "EVOEM_C1", "sensor": "D30"}])
        mine = next(r for r in run_validation(self.client, DEVICES, body, AUTHOR)["rows"]
                    if r["date"] == "2026-09-14")
        self.assertAlmostEqual(mine["value"], 1268.0)

    def test_a_shift_without_data_says_so_rather_than_zero(self):
        entry = self.make(label="Delta only", expression="delta", unit="kWh")
        body = request(formula=entry["id"], to="2026-09-13",
                       targets=[{"devID": "EVOEM_C1", "sensor": "D30"}])
        row = next(r for r in run_validation(self.client, DEVICES, body, AUTHOR)["rows"]
                   if r["date"] == "2026-09-13")
        self.assertEqual(row["status"], "NO_DATA")
        self.assertIsNone(row["value"])

    def test_bad_expressions_are_refused_at_save_time(self):
        with self.assertRaises(ExpressionError):
            self.make(expression="__import__('os').system('ls')")
        with self.assertRaises(ExpressionError):
            self.make(expression="enrgy * 2")
        with self.assertRaisesRegex(ValueError, "name"):
            self.make(label="  ")
        self.assertEqual(custom_formulas.load(), [])

    def test_names_are_unique_and_only_the_author_can_delete(self):
        entry = self.make(label="Night flow")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.make(label="night flow")
        with self.assertRaisesRegex(ValueError, "whoever wrote"):
            custom_formulas.delete(entry["id"], OTHER)
        self.assertFalse(formulas.all_formulas(OTHER)[-1]["mine"])
        custom_formulas.delete(entry["id"], AUTHOR)
        self.assertEqual(custom_formulas.load(), [])

    def test_the_store_survives_being_absent(self):
        self.assertEqual(custom_formulas.load(), [])
        self.assertEqual(formulas.all_formulas(), formulas.FORMULAS)


if __name__ == "__main__":
    unittest.main()
