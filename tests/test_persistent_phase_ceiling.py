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


class CeilingTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_bounded_cycle_keeps_the_configured_ceiling(self):
        seen = []
        # 3000 s of wall leaves the share cap slack, so nothing but the
        # configured value can govern here.
        await run_cycle({"cycle_timeout_seconds": 3000}, seen)
        self.assertEqual(seen[0], 480)

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
