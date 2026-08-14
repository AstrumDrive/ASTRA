"""The translator must be told how to keep symbolic work affordable.

Measured 2026-08-14 (`docs/evidence/ASTRA2_WARP_NEC_TEST_20260814.md`): a
research-grade GR validator could not be written inside 480 s plus a 360 s
retry, and a hand-written attempt that carried full symbolic Christoffels was
killed twice for memory, while the pointwise assembly of the same quantity
finished in 13 s. More time with the wrong method would not have helped, so
the method belongs in the prompt.
"""
import unittest

from agents.translator import (
    FORMAL_TRANSLATOR_PROMPT,
    FORMAL_TRANSLATOR_VNEXT_ADDENDUM,
)


class SymbolicCostControlTests(unittest.TestCase):
    def test_the_pointwise_rule_is_stated(self):
        self.assertIn("SYMBOLIC COST CONTROL", FORMAL_TRANSLATOR_PROMPT)
        self.assertIn("Curvature AT A POINT", FORMAL_TRANSLATOR_PROMPT)
        self.assertIn("substitute the point immediately", FORMAL_TRANSLATOR_PROMPT)

    def test_the_ordering_guard_survives_the_optimisation(self):
        # The cheap route is only correct if differentiation still comes first;
        # an optimisation that quietly reverses the order computes something
        # else entirely.
        self.assertIn("PRECEDE substitution", FORMAL_TRANSLATOR_PROMPT)
        self.assertIn(
            "Substituting\n     first and differentiating after is a different",
            FORMAL_TRANSLATOR_PROMPT,
        )

    def test_it_forbids_simplifying_inside_the_loops(self):
        self.assertIn(
            "Do not call `simplify()` inside the tensor loops",
            FORMAL_TRANSLATOR_PROMPT,
        )

    def test_exactness_is_not_traded_away_for_speed(self):
        self.assertIn("Prefer exact rationals over floats", FORMAL_TRANSLATOR_PROMPT)
        self.assertIn("exact sign", FORMAL_TRANSLATOR_PROMPT)

    def test_the_escape_hatch_is_reduce_not_brute_force(self):
        self.assertIn("reduce the domain", FORMAL_TRANSLATOR_PROMPT)

    def test_existing_scientific_guards_are_untouched(self):
        """A cost optimisation must not quietly relax the epistemic rules."""
        for rule in ("SELF-REFUTATION HARNESS", "SIZE BUDGET"):
            with self.subTest(rule=rule, where="base"):
                self.assertIn(rule, FORMAL_TRANSLATOR_PROMPT)
        # The sampling guard lives in the vNext addendum, which is the prompt
        # production actually sends.
        self.assertIn(
            "Numerical samples cannot discharge a universal claim",
            FORMAL_TRANSLATOR_VNEXT_ADDENDUM,
        )


if __name__ == "__main__":
    unittest.main()
