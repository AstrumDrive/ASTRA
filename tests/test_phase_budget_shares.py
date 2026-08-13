"""No single phase call may starve the phases after it.

Measured 2026-08-13 over 84 deposited cycles
(`docs/evidence/ASTRA2_PHASE_BUDGET_20260813.md`): the configured per-call
ceilings sum to exactly the usable whole-cycle budget, so any retry pushed the
cycle past its wall.  Clamping to the remaining time alone did not help,
because an early phase may legitimately consume all of it.  These tests pin
the share cap that prevents that, and pin that a normal cycle is never
clamped by it.
"""
import unittest

from astra_tool import PHASE_BUDGET_SHARE
from core.cycle_budget import CycleBudget


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def budget(total=1500.0, buffer=60.0):
    clock = FakeClock()
    return CycleBudget(total, return_buffer_seconds=buffer, clock=clock), clock


class ShareCapTests(unittest.TestCase):
    def test_share_caps_a_runaway_phase(self):
        cycle, _clock = budget()
        # 1440 s usable: a 480 s request is well inside a 0.45 share (648 s),
        # so the configured ceiling still governs.
        self.assertEqual(cycle.phase_timeout(480, share=0.45), 480)
        # A request larger than its share is cut down to the share.
        self.assertEqual(cycle.phase_timeout(1200, share=0.45), 648)

    def test_without_a_share_the_old_behavior_is_unchanged(self):
        cycle, _clock = budget()
        self.assertEqual(cycle.phase_timeout(1200), 1200)
        self.assertEqual(cycle.phase_timeout(5000), 1440)

    def test_share_is_of_what_remains_not_of_the_total(self):
        cycle, clock = budget()
        clock.advance(1000.0)  # 440 s usable left
        self.assertEqual(cycle.phase_timeout(480, share=0.5), 220)

    def test_downstream_phases_always_survive_a_runaway(self):
        """The invariant: after a maximal call, time is left for the rest."""
        cycle, clock = budget()
        for _ in range(6):
            granted = cycle.phase_timeout(9999, share=0.45)
            self.assertGreater(granted, 0)
            clock.advance(granted)
            self.assertGreater(
                cycle.usable_seconds,
                0,
                "a maximal phase consumed the entire remaining budget",
            )

    def test_a_typical_cycle_is_never_clamped_by_its_share(self):
        # p90 per phase from the 84-cycle measurement, run in pipeline order.
        measured_p90 = [
            ("CONJECTURE", 197),
            ("TRANSLATOR", 431),
            ("REVIEWER", 169),
            ("TRANSLATOR", 343),  # bounded repair reuses the translator budget
            ("ANALYST", 40),
            ("NAVIGATOR", 34),
        ]
        cycle, clock = budget()
        for phase, needed in measured_p90:
            granted = cycle.phase_timeout(
                480 if phase == "TRANSLATOR" else 240,
                share=PHASE_BUDGET_SHARE[phase],
            )
            self.assertGreaterEqual(
                granted,
                needed,
                f"{phase} would be clamped below its measured p90 ({needed}s)",
            )
            clock.advance(needed)
        self.assertGreater(cycle.usable_seconds, 0)

    def test_every_configured_share_is_a_sane_fraction(self):
        for phase, share in PHASE_BUDGET_SHARE.items():
            with self.subTest(phase=phase):
                self.assertGreater(share, 0.0)
                self.assertLess(share, 1.0)

    def test_persistent_cycles_are_unbounded_as_before(self):
        cycle = CycleBudget(None)
        self.assertEqual(cycle.phase_timeout(480, share=0.1), 480)

    def test_malformed_share_degrades_to_no_cap(self):
        cycle, _clock = budget()
        for value in ("not a number", None, -1.0, 0.0, 1.0, 5.0):
            with self.subTest(value=value):
                self.assertEqual(cycle.phase_timeout(1200, share=value), 1200)


if __name__ == "__main__":
    unittest.main()
