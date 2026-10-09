"""The vetted ball-arithmetic prelude (core/certified/arb_prelude.py).

The reviewer is told to trust these functions, so each promise in the module
docstring has a test here, and the soundness tests matter most: a bound below
the true supremum, an integer that is not isolated, or an uncertain comparison
must never come back certified.
"""
from __future__ import annotations

import cmath
import math
import random
import unittest
from fractions import Fraction

try:
    import flint  # noqa: F401
    HAVE_FLINT = True
except ImportError:  # pragma: no cover
    HAVE_FLINT = False

if HAVE_FLINT:
    import core.certified.arb_prelude as P
    from flint import acb, arb


def Log(z):
    return P._as_acb(z).log()


@unittest.skipUnless(HAVE_FLINT, "python-flint is not installed")
class Branches(unittest.TestCase):
    def setUp(self):
        P.set_precision(128)

    def tearDown(self):
        P.set_precision(53)

    def test_known_branch_jumps_are_certified(self):
        minus_one, i = acb(-1), acb(0, 1)
        # Log(-1) + Log(-1) = 2*pi*i while Log(1) = 0.
        self.assertEqual(P.branch_index(Log(minus_one) * 2, Log(acb(1)), "(-1)(-1)"), 1)
        # Log(i) + Log(i) = i*pi = Log(-1).
        self.assertEqual(P.branch_index(Log(i) * 2, Log(minus_one), "i*i"), 0)
        # Log(-i) + Log(-i) = -i*pi, but Log(-1) = +i*pi.
        self.assertEqual(P.branch_index(Log(-i) * 2, Log(minus_one), "(-i)(-i)"), -1)

    def test_dividing_by_a_positive_real_keeps_the_branch(self):
        # The Kondo review caught a missing ln 2 in log(u - 2): Log(w) and
        # Log(w/2) + ln 2 agree for every w != 0, on either side of the cut.
        rng = random.Random(7)
        for _ in range(50):
            w = P.cball(str(rng.uniform(-5, 5)), str(rng.uniform(-5, 5)))
            k = P.branch_index(Log(w), Log(w / 2) + arb(2).log(), "ln 2")
            self.assertEqual(k, 0)

    def test_a_ball_on_the_cut_is_not_certified(self):
        on_cut = acb(-1, arb(0, "1e-6"))
        with self.assertRaises(P.Undecided):
            P.branch_index(Log(on_cut) * 2, Log(on_cut * on_cut), "straddles the cut")

    def test_an_integer_needs_a_narrow_ball(self):
        self.assertEqual(P.unique_integer(arb("2.9999999999", "1e-6"), "near 3"), 3)
        with self.assertRaises(P.Undecided):
            P.unique_integer(arb("2.5", "0.6"), "two integers")
        with self.assertRaises(P.Undecided):
            P.unique_integer(arb("2.5", "0.1"), "no integer")


@unittest.skipUnless(HAVE_FLINT, "python-flint is not installed")
class Comparisons(unittest.TestCase):
    def test_true_only_when_certain(self):
        wide = arb("1.5", "1")                       # [0.5, 2.5]
        self.assertTrue(P.is_certainly_lt(1, 2))
        self.assertFalse(P.is_certainly_lt(wide, 2))
        self.assertFalse(P.is_certainly_ge(wide, 2))  # neither side is certified
        self.assertTrue(P.is_certainly_le("1/2", "1/2"))
        self.assertTrue(P.is_certainly_nonzero(acb(0, "1e-30")))
        self.assertFalse(P.is_certainly_nonzero(acb(arb(0, "1e-30"))))

    def test_certify_accepts_only_the_literal_true(self):
        self.assertTrue(P.certify(True, "x"))
        for value in (False, 1, "True", None):
            with self.assertRaises(P.Undecided):
                P.certify(value, "x")

    def test_exact_inputs(self):
        third = P.ball(Fraction(1, 3))
        self.assertTrue(third.contains(arb("1/3")))
        self.assertTrue(P.ball("1/3").contains(arb(1) / 3))
        with self.assertRaises(TypeError):
            P.ball(True)

    def test_upper_float_never_undershoots(self):
        cases = [arb(1) / 3, arb(2).sqrt(), -arb.pi(), arb("-1", "0.99999999999999992"),
                 arb("1e-300", "1e-310"), arb("-7.25", "1e-20")]
        for x in cases:
            with self.subTest(x=str(x)):
                bound = Fraction(P.upper_float(x))
                exact_top = P._exact(x.mid()) + P._exact(x.rad())
                self.assertGreaterEqual(bound, exact_top)
        self.assertEqual(P.upper_float(arb(1) / arb(0)), math.inf)


@unittest.skipUnless(HAVE_FLINT, "python-flint is not installed")
class Sectors(unittest.TestCase):
    def setUp(self):
        P.set_precision(64)

    def tearDown(self):
        P.set_precision(53)

    def test_polar_box_contains_the_whole_rectangle(self):
        rng = random.Random(11)
        r0, r1, t0, t1 = 0.7, 1.9, 2.4, 3.9            # crosses the negative real axis
        box = P.polar_box(r0, r1, t0, t1)
        for _ in range(2000):
            r = rng.uniform(r0, r1)
            t = rng.uniform(t0, t1)
            z = cmath.rect(r, t)   # within ~1e-15 of the rectangle
            self.assertTrue(box.contains(acb(z.real, z.imag)), (r, t))
        # The cover is also not absurdly loose: its half-width stays at the
        # bound (r1-r0)/2 + r_mid (t1-t0)/2, up to Arb's ~30-bit radius rounding.
        spread = (r1 - r0) / 2 + (r0 + r1) / 2 * (t1 - t0) / 2
        self.assertLess(P.upper_float(box.real.rad()), spread * (1 + 1e-8))

    def test_sup_of_exp_minus_z_on_a_cone(self):
        f = lambda z: (-z).exp()
        res = P.sup_abs_on_sector(f, 1, 3, -arb.pi() / 4, arb.pi() / 4)
        true_sup = math.exp(-math.cos(math.pi / 4))    # r = 1, t = +-pi/4
        self.assertTrue(res["certified"])
        self.assertGreaterEqual(res["upper"], true_sup)
        self.assertLess(res["upper"], true_sup * 1.25)

    def test_a_false_bound_is_never_certified(self):
        f = lambda z: (-z).exp()
        true_sup = math.exp(-math.cos(math.pi / 4))
        with self.assertRaises(P.Undecided):
            P.certify_sup_abs_le(f, 1, 3, -arb.pi() / 4, arb.pi() / 4, str(true_sup * 0.99),
                                 "below the true sup", max_depth=5)
        ok = P.certify_sup_abs_le(f, 1, 3, -arb.pi() / 4, arb.pi() / 4, str(true_sup * 1.02),
                                  "just above the true sup")
        self.assertTrue(ok["certified"])

    def test_log_across_the_cut_stays_an_enclosure(self):
        f = lambda z: z.log()
        res = P.sup_abs_on_sector(f, 1, 2, 3 * arb.pi() / 4, 5 * arb.pi() / 4)
        true_sup = abs(complex(math.log(2), math.pi))   # |ln 2 + i pi| at the cut
        self.assertGreaterEqual(res["upper"], true_sup)

    def test_a_pole_in_the_sector_is_reported_not_bounded(self):
        f = lambda z: 1 / (z - 2)
        res = P.sup_abs_on_sector(f, 1, 3, "-0.1", "0.1", n_r=4, n_t=2, max_depth=3)
        self.assertFalse(res["certified"])
        self.assertTrue(res["unresolved"])
        with self.assertRaises(P.Undecided):
            P.certify_sup_abs_le(f, 1, 3, "-0.1", "0.1", 1000, "pole", n_r=4, n_t=2, max_depth=3)

    def test_float_functions_are_rejected(self):
        with self.assertRaises(TypeError):
            P.sup_abs_on_sector(lambda z: math.exp(z), 1, 2, 0, "0.5", n_r=1, n_t=1)

    def test_analytic_tail_is_printed_for_astra(self):
        import io
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            text = P.analytic_tail("  |R(z)| <= 2/|z|^2  for |z| >= 40 in the cone ")
        self.assertEqual(text, "|R(z)| <= 2/|z|^2 for |z| >= 40 in the cone")
        self.assertEqual(out.getvalue().strip(),
                         "ANALYTIC_TAIL: |R(z)| <= 2/|z|^2 for |z| >= 40 in the cone")


if __name__ == "__main__":
    unittest.main()
