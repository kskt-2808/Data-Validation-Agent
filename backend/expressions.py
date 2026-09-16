"""A small, safe expression language for user-defined formulas.

Users write arithmetic over the values Newton already computes for one shift.
The expression is parsed to a syntax tree and only numbers, arithmetic and the
names below are allowed — attributes, imports, comprehensions, unknown calls and
everything else are refused before anything runs. Nothing here can reach the
filesystem, the network or the interpreter.
"""
from __future__ import annotations

import ast
import math
import operator

VALUES = {
    "first": "first calibrated reading of the shift",
    "last": "last calibrated reading of the shift",
    "delta": "last − first, calibrated (energy or water consumption)",
    "first_raw": "first reading before calibration",
    "last_raw": "last reading before calibration",
    "delta_raw": "last − first before calibration",
    "mean": "average of the readings (Σ readings ÷ N)",
    "twa": "time-weighted average (each reading weighted by how long it held)",
    "min_reading": "lowest calibrated reading",
    "max_reading": "highest calibrated reading",
    "samples": "how many readings the shift holds",
    "coverage": "fraction of the shift covered by readings, 0 to 1",
    "known_hours": "hours covered by readings",
    "unknown_hours": "hours with no reading inside the gap tolerance",
    "shift_hours": "length of the shift in hours",
    "m": "the sensor's calibration multiplier",
    "c": "the sensor's calibration offset",
}
FUNCTIONS = {
    "hours_above": "hours_above(x) — hours the calibrated reading was at or above x",
    "hours_below": "hours_below(x) — hours it was below x",
    "integral": "integral(basis) — Σ(reading × interval), basis 3600 for per-hour rates",
    "abs": "abs(x)",
    "round": "round(x, digits)",
}

BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class ExpressionError(ValueError):
    """The expression cannot be used, with a message meant for the person who wrote it."""


class NoData(Exception):
    """The expression needs a value this shift does not have."""


def parse(expression: str) -> ast.Expression:
    """Parse and check an expression. Raises ExpressionError with a plain message."""
    text = (expression or "").strip()
    if not text:
        raise ExpressionError("Write an expression, for example: delta")
    if len(text) > 500:
        raise ExpressionError("That expression is too long (500 characters maximum)")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as err:
        raise ExpressionError(f"This is not valid arithmetic: {err.msg}") from None
    _check(tree.body)
    return tree


def names_used(expression: str) -> set[str]:
    return {n.id for n in ast.walk(parse(expression)) if isinstance(n, ast.Name)}


def _check(node: ast.AST) -> None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExpressionError("Only numbers can be written directly in an expression")
        return
    if isinstance(node, ast.Name):
        if node.id in VALUES or node.id in FUNCTIONS:
            return
        raise ExpressionError(f"'{node.id}' is not a value Newton knows. "
                              f"Available: {', '.join(sorted(VALUES))}")
    if isinstance(node, ast.BinOp):
        if type(node.op) not in BINARY:
            raise ExpressionError("Only + - * / ** and % can be used")
        _check(node.left)
        _check(node.right)
        return
    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in UNARY:
            raise ExpressionError("Only a leading + or - can be used")
        _check(node.operand)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise ExpressionError(f"Only these functions can be called: {', '.join(sorted(FUNCTIONS))}")
        if node.keywords:
            raise ExpressionError("Write arguments in order, not as name=value")
        for argument in node.args:
            _check(argument)
        return
    raise ExpressionError("Only numbers, the listed values and arithmetic are allowed here")


def evaluate(expression: str | ast.Expression, values: dict, functions: dict) -> float:
    """Run a parsed expression. Raises NoData when a needed value is missing."""
    tree = expression if isinstance(expression, ast.Expression) else parse(expression)
    result = _eval(tree.body, values, functions)
    if not isinstance(result, (int, float)) or isinstance(result, bool):
        raise ExpressionError("The expression did not produce a number")
    if not math.isfinite(result):
        raise ExpressionError("The expression produced an impossible number "
                              "(dividing by zero, or too large)")
    return float(result)


def _eval(node: ast.AST, values: dict, functions: dict):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in functions:
            return functions[node.id]
        value = values.get(node.id)
        if value is None:
            raise NoData(node.id)
        return value
    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left, values, functions), _eval(node.right, values, functions)
        try:
            return BINARY[type(node.op)](left, right)
        except ZeroDivisionError:
            raise ExpressionError("The expression divides by zero for this shift") from None
        except (OverflowError, ValueError):
            raise ExpressionError("The expression produced an impossible number") from None
    if isinstance(node, ast.UnaryOp):
        return UNARY[type(node.op)](_eval(node.operand, values, functions))
    if isinstance(node, ast.Call):
        function = functions.get(node.func.id)
        if function is None:
            raise ExpressionError(f"'{node.func.id}' cannot be called here")
        return function(*[_eval(a, values, functions) for a in node.args])
    raise ExpressionError("Only numbers, the listed values and arithmetic are allowed here")
