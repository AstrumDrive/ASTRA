"""A bounded cycle and a persistent one need different per-call ceilings.

Measured 2026-08-13/14: benchmark translations have a p90 of 431 s, while the
research-grade GR validator needed 696 s to write and 658 s to patch. One
variable served both, so 480 s starved real physics and raising it globally
would let a single phase eat the budget a bounded cycle keeps for the repair.
A persistent cycle has no whole-cycle wall, so the longer ceiling costs nothing
on runs that do not reach it.
"""
import unittest
from pathlib import Path
from unittest.mock import patch

from astra_tool import PERSISTENT_PHASE_TIMEOUT, _do_cycle

ENV = {
    "ASTRA_CYCLE_CACHE": "0",
    "ASTRA_CONJECTURE_PROVIDER": "codex_cli",
    "ASTRA_TRANSLATOR_TIMEOUT": "480",
    "ASTRA_NAVIGATE_AFTER_CYCLE": "0",
    "ASTRA_MAX_RETRIES": "0",
    "ASTRA_ORACLE_MODE": "local",
    "ASTRA_CODE_REVIEW": "0",
}
PROVIDERS = {
    "conjecture": "codex_cli", "translator": "claude_cli",
    "reviewer": "codex_cli", "analyst": "codex_cli",
    "navigator": "agy_cli", "synth": "codex_cli",
}


async def run_cycle(extra_request, seen, env_extra=None):
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
            seen.append(self.cli_timeout)
            return "print('CHECK a: OK')\nprint('VERDICT: PASS')\n"

        async def review_validation_code(self, **_kwargs):
            return {"status": "APPROVED", "reasoning": "", "coverage": [],
                    "revision_instructions": "", "defect_labels": [],
                    "runtime_checks": []}

        async def analyze_results(self, *_args, **_kwargs):
            return {"status": "VALIDATED", "reasoning": "ok"}

    request = {"action": "cycle", "intuition": "Decide X."}
    request.update(extra_request)
    env = {**ENV, **(env_extra or {})}
    with patch.dict("os.environ", env, clear=False), patch(
        "core.preflight.phase_provider_map", return_value=PROVIDERS
    ), patch("core.llm_client.ASTRAIntelligence", FakeIntelligence):
        result = await _do_cycle(request)
    checkpoint = Path(result.get("checkpoint") or "")
    if checkpoint.name and checkpoint.exists():
        checkpoint.unlink()
    return result


class ScalingTests(unittest.IsolatedAsyncioTestCase):
    """A fixed ceiling stops meaning anything when the wall moves.

    Measured 2026-08-16 (`ASTRA2_ABLATION_RUN3_20260816.md`): with the cycle
    budget amended to 2400 s, seven of eight timeouts were the translator and
    four died at exactly 480 s - the value in `.env`, sized for a 1500 s cycle -
    while the median translation in that same run took 573 s.
    """

    async def test_the_ceiling_scales_with_the_benchmark_budget(self):
        seen = []
        await run_cycle({"cycle_timeout_seconds": 2400}, seen)
        self.assertEqual(seen[0], 840)
        # The measured median translation, which 480 s cut in half the time.
        self.assertGreater(seen[0], 573)

    async def test_it_is_a_floor_and_never_a_cut(self):
        """At the old budget it must not drop below what was configured."""
        seen = []
        await run_cycle({"cycle_timeout_seconds": 1500}, seen)
        self.assertGreaterEqual(seen[0], 480)

    async def test_an_operator_who_configured_more_still_keeps_it(self):
        seen = []
        await run_cycle({"cycle_timeout_seconds": 3000}, seen,
                        {"ASTRA_TRANSLATOR_TIMEOUT": "1200"})
        # 1200 beats the fraction's 1050 and the cycle can fund it.
        self.assertEqual(seen[0], 1200)

    async def test_the_whole_cycle_budget_still_outranks_everything(self):
        """A generous ceiling is a request, not a licence to overrun the wall."""
        seen = []
        await run_cycle({"cycle_timeout_seconds": 1500}, seen,
                        {"ASTRA_TRANSLATOR_TIMEOUT": "1000"})
        self.assertLess(seen[0], 1000)
        self.assertGreater(seen[0], 525)   # still above the fraction's floor

    async def test_the_scaled_ceiling_still_fits_the_cycle(self):
        """Room for the phases after it, or the fix just moves the failure."""
        seen = []
        await run_cycle({"cycle_timeout_seconds": 2400}, seen)
        conjecture, review, repair, tail = 270, 205, 375, 270
        self.assertLess(seen[0] + conjecture + review + repair + tail, 2340)


class CeilingTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_bounded_cycle_keeps_the_configured_ceiling(self):
        seen = []
        # A phase with no fraction of its own is governed by its configured
        # value; 3000 s of wall leaves the share cap slack.
        await run_cycle({"cycle_timeout_seconds": 3000}, seen)
        self.assertEqual(seen[0], int(3000 * 0.35))

    async def test_a_persistent_cycle_gets_the_research_ceiling(self):
        seen = []
        await run_cycle({"persistent_cycle": True}, seen)
        self.assertEqual(seen[0], PERSISTENT_PHASE_TIMEOUT["TRANSLATOR"])
        # 696 s was a real translation that the bounded ceiling would have cut.
        self.assertGreater(seen[0], 696)

    async def test_an_operator_who_asked_for_more_keeps_more(self):
        seen = []
        await run_cycle({"persistent_cycle": True}, seen,
                        {"ASTRA_TRANSLATOR_TIMEOUT": "1800"})
        self.assertEqual(seen[0], 1800)

    async def test_the_persistent_override_is_honoured(self):
        seen = []
        await run_cycle({"persistent_cycle": True}, seen,
                        {"ASTRA_TRANSLATOR_TIMEOUT_PERSISTENT": "900"})
        self.assertEqual(seen[0], 900)


if __name__ == "__main__":
    unittest.main()
