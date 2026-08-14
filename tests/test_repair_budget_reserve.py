"""The validator repair runs last, so a share of the leftovers starves it.

Measured 2026-08-14 over the stage-6 ablation
(`docs/evidence/ASTRA2_ABLATION_FULL_VS_LINEAR_20260814.md`): all twelve
validator repairs timed out, with 124-454 s of budget left and a median ceiling
of 165 s against the 480 s configured. Cycles that validated ran a median of
882 s; cycles that failed, 1249 s. A cycle that needs a repair has already spent
its budget getting there, and a proportional rule gives the last phase the least.

Two things were wrong and both are pinned here: the benchmark's frozen 1800 s
budget never reached ASTRA, which planned against its own 1500 s default, and
nothing held budget back for the phases that still had to run.
"""
import unittest

from astra_tool import PHASE_BUDGET_SHARE, PHASE_DOWNSTREAM_RESERVE
from core.cycle_budget import CycleBudget


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def budget(total=1800.0):
    clock = FakeClock()
    return CycleBudget(total, return_buffer_seconds=60.0, clock=clock), clock


def ceiling(cycle, phase, configured):
    key = phase.upper()
    return cycle.phase_timeout(
        configured,
        share=PHASE_BUDGET_SHARE.get(key),
        reserve_seconds=PHASE_DOWNSTREAM_RESERVE.get(key, 0),
    )


class ReserveTests(unittest.TestCase):
    def test_the_repair_survives_a_realistic_cycle(self):
        """Replay the medians measured in the ablation and check the repair."""
        cycle, clock = budget()
        clock.advance(276)                      # conjecture, measured median
        clock.advance(460)                      # translation, measured median
        clock.advance(140)                      # review, measured median
        got = ceiling(cycle, "TRANSLATOR_REPAIR", 480)
        # It used to get 165 s at this point. It must now get its full ceiling.
        self.assertEqual(got, 480)

    def test_the_old_1500_budget_was_the_other_half_of_the_problem(self):
        cycle, clock = budget(1500.0)
        clock.advance(276 + 460 + 140)
        starved = ceiling(cycle, "TRANSLATOR_REPAIR", 480)
        self.assertLess(starved, 480)
        # ...and the frozen benchmark budget is what makes it fit.
        roomy, clock2 = budget(1800.0)
        clock2.advance(276 + 460 + 140)
        self.assertEqual(ceiling(roomy, "TRANSLATOR_REPAIR", 480), 480)

    def test_early_phases_are_not_clamped_by_the_reserve(self):
        """The reserve must buy the repair time without breaking the start."""
        cycle, clock = budget()
        self.assertEqual(ceiling(cycle, "CONJECTURE", 240), 240)
        clock.advance(276)
        self.assertEqual(ceiling(cycle, "TRANSLATOR", 480), 480)
        clock.advance(460)
        self.assertEqual(ceiling(cycle, "REVIEWER", 240), 240)

    def test_the_reserve_holds_back_what_the_tail_actually_costs(self):
        # Execution, analysis and navigation measured about 270 s together;
        # the repair p90 is 343 s. Everything before the repair leaves both.
        self.assertEqual(
            PHASE_DOWNSTREAM_RESERVE["TRANSLATOR"],
            PHASE_DOWNSTREAM_RESERVE["TRANSLATOR_REPAIR"] + 343,
        )

    def test_a_late_cycle_still_gets_a_usable_call_not_zero(self):
        """The reserve must never drive a phase to nothing."""
        cycle, clock = budget()
        clock.advance(1700)
        self.assertGreaterEqual(ceiling(cycle, "TRANSLATOR_REPAIR", 480), 1)

    def test_a_persistent_cycle_is_unaffected(self):
        cycle = CycleBudget(None)
        self.assertEqual(ceiling(cycle, "TRANSLATOR_REPAIR", 1200), 1200)


class ReserveArithmeticTests(unittest.TestCase):
    def test_reserve_and_share_both_apply(self):
        cycle, _clock = budget(1800.0)
        # 1740 usable, reserve 613 -> 1127 allowed; share 0.3 -> 522 is tighter.
        self.assertEqual(
            cycle.phase_timeout(2000, share=0.30, reserve_seconds=613), 522
        )
        # With no share, the reserve governs.
        self.assertEqual(
            cycle.phase_timeout(2000, share=None, reserve_seconds=613), 1127
        )

    def test_a_nonsense_reserve_is_ignored_rather_than_fatal(self):
        cycle, _clock = budget(1800.0)
        for bad in (None, "", "later", -50):
            with self.subTest(reserve=bad):
                self.assertEqual(
                    cycle.phase_timeout(300, reserve_seconds=bad), 300
                )


if __name__ == "__main__":
    unittest.main()
