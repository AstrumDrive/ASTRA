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

from astra_tool import (
    PHASE_BUDGET_SHARE,
    PHASE_DOWNSTREAM_RESERVE,
    review_round_reserve,
)
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


class LoopAwareReserveTests(unittest.TestCase):
    """The validation loop is not a line: review runs again after each repair.

    Measured 2026-08-16 (`ASTRA2_ABLATION_RUN3_20260816.md`): a final review
    round was refused with 571.83 s still on the clock, because it was asked to
    hold back 613 s for a repair that could no longer run - the revision budget
    was already spent.
    """

    def test_a_repair_that_can_still_run_is_funded(self):
        self.assertEqual(
            review_round_reserve(model_revisions=0, max_revisions=1),
            PHASE_DOWNSTREAM_RESERVE["REVIEWER"],
        )

    def test_a_repair_that_cannot_run_is_not_reserved_for(self):
        self.assertEqual(
            review_round_reserve(model_revisions=1, max_revisions=1),
            PHASE_DOWNSTREAM_RESERVE["TRANSLATOR_REPAIR"],
        )

    def test_the_measured_refusal_would_now_go_through(self):
        """Replay the exact cell that failed: 571.83 s left of 2400."""
        cycle, clock = budget(2400.0)
        clock.advance(2400.0 - 571.83)
        stale = cycle.phase_timeout(
            240, share=PHASE_BUDGET_SHARE["REVIEWER"],
            reserve_seconds=review_round_reserve(0, 1),
        )
        fixed = cycle.phase_timeout(
            240, share=PHASE_BUDGET_SHARE["REVIEWER"],
            reserve_seconds=review_round_reserve(1, 1),
        )
        self.assertLess(stale, 45)           # what actually happened
        self.assertGreaterEqual(fixed, 45)   # what should have happened

    def test_a_genuinely_spent_budget_is_still_refused(self):
        """Relaxing the reserve must not disable the guard."""
        cycle, clock = budget(2400.0)
        clock.advance(2380.0)
        self.assertLess(
            cycle.phase_timeout(
                240, share=PHASE_BUDGET_SHARE["REVIEWER"],
                reserve_seconds=review_round_reserve(1, 1),
            ),
            45,
        )


class StarvationGuardTests(unittest.IsolatedAsyncioTestCase):
    """A call that cannot succeed must not be made.

    Measured 2026-08-15: with the reserve in place, the SECOND review round -
    the one after a repair - was handed ceilings of 6 s and 1 s, because by then
    what remains is roughly the reserve itself. ASTRA issued those calls anyway
    and reported `timeout tras 1s`, which reads as a hung model rather than an
    exhausted budget.
    """

    async def _run(self, cycle_seconds):
        from unittest.mock import patch

        from astra_tool import _do_cycle

        calls = []

        class FakeIntelligence:
            def __init__(self, provider, cli_models=None, cli_timeout=None):
                self.provider = provider
                self.cli_models = cli_models
                self.cli_timeout = cli_timeout
                self.cli_warnings = []
                self.cli_last_model = None
                self.cli_cost_usd = 0.0

            async def generate_conjecture(self, axiomatic_base, intuition):
                return "Prove X."

            async def translate_to_code(self, _conjecture, **_kwargs):
                return "print('CHECK a: OK')\nprint('VERDICT: PASS')\n"

            async def review_validation_code(self, **_kwargs):
                calls.append("review")
                return {"status": "APPROVED", "reasoning": "", "coverage": [],
                        "revision_instructions": "", "defect_labels": [],
                        "runtime_checks": []}

            async def analyze_results(self, *_args, **_kwargs):
                return {"status": "VALIDATED", "reasoning": "ok"}

        env = {
            "ASTRA_CYCLE_CACHE": "0",
            "ASTRA_CONJECTURE_PROVIDER": "codex_cli",
            "ASTRA_NAVIGATE_AFTER_CYCLE": "0",
            "ASTRA_MAX_RETRIES": "0",
            "ASTRA_ORACLE_MODE": "local",
        }
        providers = {
            "conjecture": "codex_cli", "translator": "claude_cli",
            "reviewer": "codex_cli", "analyst": "codex_cli",
            "navigator": "agy_cli", "synth": "codex_cli",
        }
        with patch.dict("os.environ", env, clear=False), patch(
            "core.preflight.phase_provider_map", return_value=providers
        ), patch("core.llm_client.ASTRAIntelligence", FakeIntelligence):
            result = await _do_cycle({
                "action": "cycle",
                "intuition": "Decide X.",
                "cycle_timeout_seconds": cycle_seconds,
            })
        from pathlib import Path

        checkpoint = Path(result.get("checkpoint") or "")
        if checkpoint.name and checkpoint.exists():
            checkpoint.unlink()
        return result, calls

    async def test_an_exhausted_budget_stops_instead_of_burning_a_call(self):
        result, calls = await self._run(100)
        self.assertEqual(calls, [], "the reviewer was called with no budget")
        self.assertIn("Cycle budget exhausted", str(result.get("error")))
        self.assertIn("45s", str(result.get("error")))

    async def test_a_healthy_budget_still_reviews(self):
        _result, calls = await self._run(2400)
        self.assertEqual(calls, ["review"])


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
