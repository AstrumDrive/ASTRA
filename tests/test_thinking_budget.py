"""Keep room in the output budget for the answer itself.

Measured 2026-08-14 over four translator calls
(`docs/evidence/ASTRA2_PLAN_ARTIFACT_INJECTION_20260814.md`):

    call                       output tokens   stop_reason   text emitted
    cycle 2, first             1732            end_turn      1383 chars
    cycle 2, repair            64000           max_tokens    NONE
    cycle 3, translate         59181           end_turn      10449 chars
    cycle 3, patch             56630           end_turn      5812 chars

The repair reasoned until the output ceiling and never answered; ASTRA saw only
a timeout. The successful calls came within 8 % of that same ceiling, so the
margin is thin by nature and not a one-off.
"""
import unittest
from unittest.mock import patch

from core import cli_backend
from core.cli_backend import CliResult, _claude_thinking_cap, call_cli


class CapSelectionTests(unittest.TestCase):
    def test_the_default_leaves_room_without_biting_a_working_run(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("ASTRA_CLAUDE_MAX_THINKING_TOKENS", None)
            cap = int(_claude_thinking_cap())
        # Thinking is bounded above by the total, so clearing the successful
        # totals keeps every observed working call intact.
        self.assertGreater(cap, 56630)
        # And the reserve has to fit the answer: the largest validator measured
        # was 250 lines / 10.4 k characters, roughly 3 k tokens.
        self.assertGreaterEqual(64000 - cap, 5000)

    def test_an_operator_can_retune_or_disable_it(self):
        for raw, expected in (("12000", "12000"), ("0", None), ("off", None)):
            with self.subTest(raw=raw):
                with patch.dict(
                    "os.environ", {"ASTRA_CLAUDE_MAX_THINKING_TOKENS": raw}
                ):
                    self.assertEqual(_claude_thinking_cap(), expected)

    def test_a_typo_falls_back_instead_of_failing_a_cycle(self):
        with patch.dict(
            "os.environ", {"ASTRA_CLAUDE_MAX_THINKING_TOKENS": "mucho"}
        ):
            self.assertEqual(int(_claude_thinking_cap()), 58000)


class EnvWiringTests(unittest.TestCase):
    def _capture_env(self, kind, environ):
        seen = {}

        def fake_invoke(_kind, _promptfile, _outfile, _model, _ws, env, _timeout):
            seen.update(env)
            return CliResult(True, text="ok", model_used="default")

        with patch.dict("os.environ", environ, clear=False), patch.object(
            cli_backend, "_invoke_once", fake_invoke
        ):
            call_cli(kind, "prompt", timeout=5)
        return seen

    def test_the_claude_child_gets_the_cap(self):
        import os

        environ = dict(os.environ)
        environ.pop("MAX_THINKING_TOKENS", None)
        environ.pop("ASTRA_CLAUDE_MAX_THINKING_TOKENS", None)
        with patch.dict("os.environ", environ, clear=True):
            seen = self._capture_env("claude", {})
        self.assertEqual(seen.get("MAX_THINKING_TOKENS"), "58000")

    def test_an_exported_value_outranks_the_default(self):
        seen = self._capture_env("claude", {"MAX_THINKING_TOKENS": "8000"})
        self.assertEqual(seen.get("MAX_THINKING_TOKENS"), "8000")

    def test_other_clis_are_left_alone(self):
        import os

        environ = dict(os.environ)
        environ.pop("MAX_THINKING_TOKENS", None)
        with patch.dict("os.environ", environ, clear=True):
            seen = self._capture_env("agy", {})
        self.assertIsNone(seen.get("MAX_THINKING_TOKENS"))


if __name__ == "__main__":
    unittest.main()
