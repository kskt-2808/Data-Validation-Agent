import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import expressions  # noqa: E402
from expressions import ExpressionError, NoData  # noqa: E402

VALUES = {"delta": 1268.0, "mean": 12.0, "max_reading": 48.0, "m": 0.001, "samples": 1245,
          "shift_hours": 24.0, "coverage": 0.99, "first": None}
FUNCTIONS = {"hours_above": lambda x: 7.15 if x <= 3 else 0.0,
             "integral": lambda basis=3600: 288.0 * (3600 / basis),
             "abs": abs, "round": round}


def run(expression):
    return expressions.evaluate(expression, VALUES, FUNCTIONS)


class RealFormulas(unittest.TestCase):
    def test_the_formulas_people_actually_write(self):
        self.assertAlmostEqual(run("delta"), 1268.0)
        self.assertAlmostEqual(run("hours_above(3)"), 7.15)
        self.assertAlmostEqual(run("integral(3600)"), 288.0)
        self.assertAlmostEqual(run("mean / max_reading * 100"), 25.0)
        self.assertAlmostEqual(run("hours_above(3) / 12 * 100"), 59.5833, places=3)
        self.assertAlmostEqual(run("round(delta * 2, 1)"), 2536.0)


class Refusals(unittest.TestCase):
    def assertRefused(self, expression, message):
        with self.assertRaises(ExpressionError) as caught:
            expressions.parse(expression)
        self.assertIn(message, str(caught.exception))

    def test_nothing_can_escape_the_sandbox(self):
        for expression in ["__import__('os').system('rm -rf /')",
                           "open('/etc/passwd').read()",
                           "delta.__class__.__mro__",
                           "(1).__class__",
                           "[x for x in range(10)]",
                           "lambda: 1",
                           "print('hi')"]:
            with self.assertRaises(ExpressionError, msg=expression):
                expressions.parse(expression)

    def test_unknown_names_say_what_is_available(self):
        self.assertRefused("enrgy * 2", "'enrgy' is not a value Newton knows")

    def test_unknown_functions_are_refused(self):
        self.assertRefused("exec(delta)", "Only these functions can be called")

    def test_empty_and_broken_input(self):
        self.assertRefused("", "Write an expression")
        self.assertRefused("delta *", "not valid arithmetic")
        self.assertRefused("delta * " + "9" * 600, "too long")

    def test_strings_are_not_values(self):
        self.assertRefused("'rm -rf'", "Only numbers")


class Arithmetic(unittest.TestCase):
    def test_divide_by_zero_is_explained_not_crashed(self):
        with self.assertRaisesRegex(ExpressionError, "divides by zero"):
            expressions.evaluate("delta / 0", VALUES, FUNCTIONS)

    def test_a_missing_value_means_no_data(self):
        with self.assertRaises(NoData):
            expressions.evaluate("first * 2", VALUES, FUNCTIONS)

    def test_names_used_reports_the_dependencies(self):
        self.assertEqual(expressions.names_used("mean / max_reading * 100"),
                         {"mean", "max_reading"})


if __name__ == "__main__":
    unittest.main()
