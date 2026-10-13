"""Dimensional consistency promoted from a benchmark case to a callable check.

`benchmarks/fluids/reynolds_dimensionless.json` asks a cycle to verify by hand
that `rho v L / mu` is dimensionless. Useful as a test of the system, useless
as a capability: nothing else in ASTRA could ask the question. These tests pin
the callable version, and in particular the addition rule, which is the
physical type error the Research IR proposal wanted from a type system --
`m * a` has a dimension, `m + a` is an error.

They also pin the decision *not* to validate `Claim.units`. Measured against
pint 0.25.3 on 2026-08-30, rejection would refuse the legitimate prose
scientists write ('ratio', 'none', 'per second', 'arbitrary units') while
'N/A' silently parses as newton per ampere and 'a.u.' as [time]*[mass]. A
gate whose failures are false and whose passes are unsound is worse than no
gate, so `describe_units` reports and never rejects.
"""
import unittest

from core.dimensional_analysis import (
    DimensionalError,
    check_dimensionless,
    check_same_dimension,
    describe_units,
    dimension_of,
    expression_dimension,
    is_dimensionless,
    same_dimension,
)

REYNOLDS = {"rho": "kg/m**3", "v": "m/s", "L": "m", "mu": "Pa*s"}
NEWTON = {"F": "N", "m": "kg", "a": "m/s**2"}


class SingleUnits(unittest.TestCase):
    def test_dimension_of_common_units(self):
        self.assertEqual(dimension_of("m/s"), "[length] / [time]")
        self.assertEqual(dimension_of("dimensionless"), "dimensionless")

    def test_normalisation_is_pints(self):
        # Pa*s and kg/(m*s) are the same dimension written two ways.
        self.assertTrue(same_dimension("Pa*s", "kg/(m*s)"))
        self.assertFalse(same_dimension("m", "kg"))

    def test_is_dimensionless(self):
        self.assertTrue(is_dimensionless("dimensionless"))
        self.assertFalse(is_dimensionless("m"))

    def test_unrecognised_units_raise(self):
        with self.assertRaises(DimensionalError):
            dimension_of("arbitrary units")


class ReynoldsMadeCallable(unittest.TestCase):
    def test_reynolds_number_is_dimensionless(self):
        self.assertEqual(
            expression_dimension("rho*v*L/mu", REYNOLDS), "dimensionless"
        )
        check_dimensionless("rho*v*L/mu", REYNOLDS)

    def test_the_documented_failure_mode_is_caught(self):
        # The case's own first failure mode: using kinematic viscosity while
        # keeping the dynamic-viscosity formula. It stops being dimensionless.
        kinematic = {**REYNOLDS, "mu": "m**2/s"}
        with self.assertRaises(DimensionalError) as ctx:
            check_dimensionless("rho*v*L/mu", kinematic)
        self.assertIn("not dimensionless", str(ctx.exception))

    def test_a_non_dimensionless_expression_reports_its_dimension(self):
        self.assertEqual(expression_dimension("rho*v", REYNOLDS), "[mass] / [length] ** 2 / [time]")


class AdditionIsTheTypeError(unittest.TestCase):
    """`Force = Mass + Acceleration` must not compile."""

    def test_product_is_fine(self):
        self.assertEqual(
            expression_dimension("m*a", NEWTON),
            "[mass] * [length] / [time] ** 2",
        )

    def test_sum_of_incompatible_dimensions_raises(self):
        with self.assertRaises(DimensionalError):
            expression_dimension("m + a", NEWTON)

    def test_difference_of_incompatible_dimensions_raises(self):
        with self.assertRaises(DimensionalError):
            expression_dimension("m - a", NEWTON)

    def test_the_two_sides_of_an_equation_must_agree(self):
        check_same_dimension("F", "m*a", NEWTON)
        with self.assertRaises(DimensionalError) as ctx:
            check_same_dimension("F", "m*a**2", NEWTON)
        self.assertIn("Dimensional mismatch", str(ctx.exception))

    def test_adding_compatible_dimensions_is_allowed(self):
        self.assertEqual(expression_dimension("F + m*a", NEWTON), "[mass] * [length] / [time] ** 2")

    def test_a_dimensional_exponent_is_rejected(self):
        with self.assertRaises(DimensionalError) as ctx:
            expression_dimension("m**a", NEWTON)
        self.assertIn("exponent", str(ctx.exception))


class EvaluatorIsAWhitelist(unittest.TestCase):
    """These expressions are model-written, so `eval` is not an option."""

    def test_calls_are_blocked(self):
        for hostile in (
            '__import__("os").system("echo hi")',
            'open("secrets.txt")',
            "print(1)",
        ):
            with self.subTest(expression=hostile):
                with self.assertRaises(DimensionalError):
                    expression_dimension(hostile, {"v": "m"})

    def test_attribute_access_is_blocked(self):
        with self.assertRaises(DimensionalError):
            expression_dimension("v.__class__", {"v": "m"})

    def test_comprehensions_and_subscripts_are_blocked(self):
        for hostile in ("[x for x in (1,2)]", "v[0]", "{1: 2}"):
            with self.subTest(expression=hostile):
                with self.assertRaises(DimensionalError):
                    expression_dimension(hostile, {"v": "m"})

    def test_strings_are_not_constants_we_accept(self):
        with self.assertRaises(DimensionalError):
            expression_dimension("'m'", {"v": "m"})

    def test_an_undeclared_symbol_is_an_error_not_a_zero(self):
        with self.assertRaises(DimensionalError) as ctx:
            expression_dimension("rho*w", REYNOLDS)
        self.assertIn("no declared units", str(ctx.exception))

    def test_unparseable_expression_raises(self):
        with self.assertRaises(DimensionalError):
            expression_dimension("rho*", REYNOLDS)

    def test_unrecognised_symbol_units_raise(self):
        with self.assertRaises(DimensionalError) as ctx:
            expression_dimension("x", {"x": "bananas"})
        self.assertIn("Unrecognised units", str(ctx.exception))


class DescribeReportsRatherThanRejects(unittest.TestCase):
    def test_recognised_units_report_their_dimension(self):
        result = describe_units("m/s")
        self.assertTrue(result["recognised"])
        self.assertEqual(result["dimension"], "[length] / [time]")

    def test_legitimate_prose_is_reported_not_condemned(self):
        # 'ratio' and 'none' are things scientists write. Refusing them would
        # be a false failure, which is why Claim.units stays free text.
        for prose in ("ratio", "none", "arbitrary units", "per second"):
            with self.subTest(units=prose):
                result = describe_units(prose)
                self.assertFalse(result["recognised"])
                self.assertIsNone(result["dimension"])

    def test_missing_units_are_reported_plainly(self):
        for empty in (None, "", "   "):
            with self.subTest(units=empty):
                self.assertEqual(
                    describe_units(empty)["detail"], "no units given"
                )

    def test_the_dangerous_placeholders_are_documented_here(self):
        # Not a wish, a measurement: these parse, and into dimensions nobody
        # intended. They are the reason a units gate would give false
        # confidence -- the strings that pass are not necessarily meaningful.
        self.assertTrue(describe_units("N/A")["recognised"])
        self.assertEqual(
            describe_units("N/A")["dimension"],
            "[mass] * [length] / [time] ** 2 / [current]",
        )
        self.assertTrue(describe_units("a.u.")["recognised"])
        self.assertEqual(describe_units("a.u.")["dimension"], "[time] * [mass]")


if __name__ == "__main__":
    unittest.main()
