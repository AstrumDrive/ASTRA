"""Dimensional consistency as a callable check, not a benchmark case.

`benchmarks/fluids/reynolds_dimensionless.json` asks a cycle to verify by
hand that `rho v L / mu` is dimensionless. That is a fine test of whether the
system can reason dimensionally, but it leaves the capability locked inside a
case: nothing else in ASTRA can ask the question. This module makes the same
check callable, so a validator, an epistemic test, or a reviewer can run it
against any declared equation.

The addition rule is the point. Under `pint`, adding a mass to an
acceleration raises rather than producing a number, so

    expression_dimension("m + a", {"m": "kg", "a": "m/s**2"})

fails where `m*a` succeeds. That is the physical type error the Research IR
proposal wanted from a type system, obtained at expression level from a
dependency the project already declares (`requirements.txt`, pint>=0.23).

WHY UNIT STRINGS ARE NOT VALIDATED AT THE RECORD LEVEL
------------------------------------------------------
`Claim.units` is deliberately left as free text, and `describe_units` reports
rather than rejects. Measured against pint 0.25.3 on 2026-08-30:

    'dimensionless' 'm/s' 'Pa*s' 'J/(mol*K)' 'eV' 'counts' '%'  -> parse
    'ratio' 'none' 'per second' 'arbitrary units'               -> do not
    'N/A'  -> parses as newton / ampere,  [mass][length]/[time]^2/[current]
    'a.u.' -> parses as [time] * [mass]

The last two are why rejection would be the wrong rule and, worse, a
misleading one: the legitimate prose scientists actually write is refused,
while the dangerous placeholders pass *and silently acquire a physical
dimension nobody intended*. A gate whose failures are false and whose passes
are not sound is not worth having. Ask this module a specific question about
a specific equation instead.
"""
from __future__ import annotations

import ast
from typing import Any, Mapping


class DimensionalError(ValueError):
    """A units expression could not be resolved, or an equation is unsound."""


_REGISTRY: Any = None


def _registry() -> Any:
    """One lazily built pint registry; constructing it is not cheap."""
    global _REGISTRY
    if _REGISTRY is None:
        import pint

        _REGISTRY = pint.UnitRegistry()
    return _REGISTRY


# Only arithmetic. No calls, attributes, subscripts, comprehensions or names
# resolved from any scope: the expressions reaching this module are written by
# a model, so the evaluator has to be a whitelist rather than `eval` with a
# stripped `__builtins__`.
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


def _evaluate(node: ast.AST, values: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, values)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise DimensionalError(
                f"Only numeric constants are allowed, got {node.value!r}"
            )
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise DimensionalError(
                f"Symbol {node.id!r} has no declared units; declare every "
                f"symbol the expression uses"
            )
        return values[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
        operand = _evaluate(node.operand, values)
        return +operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        left = _evaluate(node.left, values)
        right = _evaluate(node.right, values)
        try:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            # A dimensional quantity raised to a dimensional power is
            # meaningless; pint rejects it, and so does the exponent check
            # below for the clearer message.
            if not isinstance(right, (int, float)):
                raise DimensionalError(
                    "An exponent must be a plain number, not a dimensional "
                    "quantity"
                )
            return left**right
        except DimensionalError:
            raise
        except Exception as exc:  # pint raises its own hierarchy
            raise DimensionalError(str(exc)) from exc
    raise DimensionalError(
        f"Unsupported syntax in a units expression: {type(node).__name__}"
    )


def dimension_of(units: str) -> str:
    """Canonical dimensionality of a unit expression, e.g. '[length] / [time]'."""
    if units is None:
        raise DimensionalError("units must be a string")
    try:
        return str(_registry().Unit(str(units)).dimensionality)
    except DimensionalError:
        raise
    except Exception as exc:
        raise DimensionalError(f"Unrecognised unit expression {units!r}") from exc


def describe_units(units: str | None) -> dict[str, Any]:
    """Report what a unit string means, without deciding it is wrong.

    ``recognised`` false is not a verdict that the units are bad -- see this
    module's docstring on 'ratio' and 'none'. It means this check has nothing
    to say, which is different from disapproval and must be reported as such.
    """
    if units is None or not str(units).strip():
        return {"recognised": False, "dimension": None, "detail": "no units given"}
    try:
        dimension = dimension_of(units)
    except DimensionalError as exc:
        return {"recognised": False, "dimension": None, "detail": str(exc)}
    return {
        "recognised": True,
        "dimension": dimension,
        "detail": "dimensionless" if dimension == "dimensionless" else dimension,
    }


def is_dimensionless(units: str) -> bool:
    return dimension_of(units) == "dimensionless"


def same_dimension(left: str, right: str) -> bool:
    """True when two unit expressions describe the same physical dimension.

    Normalisation is pint's, so `Pa*s` and `kg/(m*s)` compare equal.
    """
    return dimension_of(left) == dimension_of(right)


def expression_dimension(
    expression: str, symbol_units: Mapping[str, str]
) -> str:
    """Dimensionality of ``expression`` given each symbol's units.

    This is `reynolds_dimensionless` made callable::

        expression_dimension(
            "rho*v*L/mu",
            {"rho": "kg/m**3", "v": "m/s", "L": "m", "mu": "Pa*s"},
        )  # -> 'dimensionless'

    Raises ``DimensionalError`` when the expression is not dimensionally
    sound -- adding a mass to an acceleration, or raising a quantity to a
    dimensional power -- which is the check the record-level one cannot give.
    """
    registry = _registry()
    values: dict[str, Any] = {}
    for symbol, units in symbol_units.items():
        if not isinstance(symbol, str) or not symbol.isidentifier():
            raise DimensionalError(f"Not a usable symbol name: {symbol!r}")
        try:
            values[symbol] = registry.Quantity(1.0, str(units))
        except Exception as exc:
            raise DimensionalError(
                f"Unrecognised units {units!r} for symbol {symbol!r}"
            ) from exc
    try:
        tree = ast.parse(str(expression), mode="eval")
    except SyntaxError as exc:
        raise DimensionalError(f"Could not parse expression {expression!r}") from exc
    result = _evaluate(tree, values)
    if isinstance(result, (int, float)):
        return "dimensionless"
    return str(result.dimensionality)


def check_dimensionless(expression: str, symbol_units: Mapping[str, str]) -> None:
    """Raise unless ``expression`` is dimensionless under ``symbol_units``."""
    dimension = expression_dimension(expression, symbol_units)
    if dimension != "dimensionless":
        raise DimensionalError(
            f"{expression} is not dimensionless: it has dimension {dimension}"
        )


def check_same_dimension(
    left: str, right: str, symbol_units: Mapping[str, str]
) -> None:
    """Raise unless both expressions carry the same dimension.

    The check an equation deserves before anyone tries to prove it: the two
    sides of `F = m a` must agree before the equality can be either true or
    false.
    """
    left_dimension = expression_dimension(left, symbol_units)
    right_dimension = expression_dimension(right, symbol_units)
    if left_dimension != right_dimension:
        raise DimensionalError(
            f"Dimensional mismatch: {left} has {left_dimension} while "
            f"{right} has {right_dimension}"
        )
