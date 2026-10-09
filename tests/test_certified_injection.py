"""`# ASTRA_CERTIFIED: arb`: how the vetted prelude reaches a validator, the
guards around it, and what a cycle reports (core/certified/__init__.py)."""
from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from core.certified import (
    PRELUDE_API,
    expand_certified,
    parse_analytic_tails,
    prelude_info,
    prelude_source,
    shadowed_names,
)

try:
    import flint  # noqa: F401
    HAVE_FLINT = True
except ImportError:  # pragma: no cover
    HAVE_FLINT = False

VALIDATOR = """# ASTRA_EST_RUNTIME: short
# ASTRA_CERTIFIED: arb
set_precision(128)
k = branch_index(acb(-1).log() * 2, acb(1).log(), "(-1)(-1)")
print(f"CHECK branch: {'OK' if k == 1 else 'FAIL'} -- k = {k}")
print("VERDICT: PASS" if k == 1 else "VERDICT: FAIL")
raise RuntimeError("line six")
"""


class Expansion(unittest.TestCase):
    def test_without_marker_nothing_changes(self):
        code = "print('VERDICT: PASS')\n"
        self.assertEqual(expand_certified(code, "python"), (code, None, None))

    def test_prelude_in_plain_text_then_the_validator_unchanged(self):
        expanded, info, error = expand_certified(VALIDATOR, "python")
        self.assertIsNone(error)
        self.assertTrue(expanded.startswith(prelude_source().rstrip("\n")))
        self.assertIn(f"_astra_validator = {VALIDATOR!r}", expanded)   # verbatim
        self.assertIn("compile(_astra_validator, 'validator.py', \"exec\")", expanded)
        self.assertEqual(info, prelude_info())
        self.assertRegex(info["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(info["version"], "arb-1")

    def test_nothing_that_looks_obfuscated(self):
        # A workstation antivirus deleted the base64 version on launch.
        expanded, _info, _error = expand_certified(VALIDATOR, "python")
        for token in ("base64", "b64decode", "zlib", "marshal"):
            self.assertNotIn(token, expanded)

    def test_a_repeated_marker_loads_the_prelude_once(self):
        code = "# ASTRA_CERTIFIED: arb\nx = 1\n# ASTRA_CERTIFIED: arb\nprint(x)\n"
        expanded, _info, error = expand_certified(code, "python")
        self.assertIsNone(error)
        self.assertEqual(expanded.count('ASTRA_CERTIFIED_VERSION = "arb-1"'), 1)

    def test_other_engines_and_kinds_are_refused(self):
        for engine in ("sage", "sci", "pkgs", "lean4"):
            with self.subTest(engine=engine):
                _code, info, error = expand_certified(VALIDATOR, engine)
                self.assertIsNone(info)
                self.assertIn("Python engine only", error)
        _code, _info, error = expand_certified("# ASTRA_CERTIFIED: mpfi\nx=1\n", "python")
        self.assertIn("unknown kind mpfi", error)
        _code, _info, error = expand_certified("if True:\n    # ASTRA_CERTIFIED: arb\n    x=1\n", "python")
        self.assertIn("top-level", error)

    def test_rebinding_a_vetted_name_is_refused(self):
        bad = {
            "def": "def branch_index(a, b, w):\n    return 0\n",
            "assign": "certify = lambda c, w: True\n",
            "import": "from mylib import upper_float\n",
            "import as": "import os as sup_abs_on_sector\n",
            "class": "class Undecided(Exception):\n    pass\n",
        }
        for kind, body in bad.items():
            with self.subTest(kind=kind):
                code = "# ASTRA_CERTIFIED: arb\n" + body
                _code, info, error = expand_certified(code, "python")
                self.assertIsNone(info)
                self.assertIn("rebinds vetted helper", error)
        self.assertEqual(shadowed_names("from flint import arb, acb\nx = ball(1)\n"), [])

    @unittest.skipUnless(HAVE_FLINT, "python-flint is not installed")
    def test_api_list_matches_the_prelude(self):
        import core.certified.arb_prelude as prelude  # noqa: F401  (needs flint)
        for name in PRELUDE_API:
            with self.subTest(name=name):
                self.assertTrue(hasattr(prelude, name))

    def test_analytic_tails_are_parsed_once_each(self):
        stdout = ("CERTIFIED_PRELUDE: arb-1\nANALYTIC_TAIL: |R| <= 2/|z|^2 for |z| >= 40\n"
                  "CHECK a: OK\n  ANALYTIC_TAIL:   |R| <= 2/|z|^2   for |z| >= 40\n"
                  "ANALYTIC_TAIL: second lemma\nVERDICT: PASS\n")
        self.assertEqual(parse_analytic_tails(stdout),
                         ["|R| <= 2/|z|^2 for |z| >= 40", "second lemma"])


@unittest.skipUnless(HAVE_FLINT, "python-flint is not installed")
class Executor(unittest.TestCase):
    def _run(self, code):
        from core.executor import execute_python_code

        with patch.dict(os.environ, {"ASTRA_ORACLE_MODE": "local"}):
            return asyncio.run(execute_python_code(code, timeout=120))

    def test_local_run_uses_the_prelude_and_records_it(self):
        result = self._run(VALIDATOR)
        self.assertIn("CERTIFIED_PRELUDE: arb-1", result["stdout"])
        self.assertIn("CHECK branch: OK -- k = 1", result["stdout"])
        self.assertEqual(result["certified_prelude"], prelude_info())
        # Tracebacks cite the validator's own lines, with their text.
        self.assertIn('File "validator.py", line 7', result["stderr"])
        self.assertIn('raise RuntimeError("line six")', result["stderr"])

    def test_a_future_import_at_the_top_still_works(self):
        code = ("from __future__ import annotations\n# ASTRA_CERTIFIED: arb\n"
                "def k() -> int:\n    return branch_index(acb(-1).log() * 2, acb(1).log(), 'x')\n"
                "print('k =', k())\n")
        result = self._run(code)
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertIn("k = 1", result["stdout"])

    def test_refusal_never_runs_the_code(self):
        code = "# ASTRA_CERTIFIED: arb\ndef certify(c, w):\n    return True\nprint('VERDICT: PASS')\n"
        result = self._run(code)
        self.assertEqual(result["exit_code"], -2)
        self.assertEqual(result["stdout"], "")
        self.assertIn("rebinds vetted helper name(s) certify", result["stderr"])

    def test_plain_code_is_unchanged(self):
        result = self._run("print('VERDICT: PASS')\n")
        self.assertEqual(result["stdout"].strip(), "VERDICT: PASS")
        self.assertNotIn("certified_prelude", result)


class Prompts(unittest.TestCase):
    def test_author_reviewer_and_analyst_know_the_contract(self):
        from agents.analyst import REFUTATION_ANALYST_PROMPT
        from agents.reviewer import reviewer_prompt
        from agents.translator import FORMAL_TRANSLATOR_PROMPT

        self.assertIn("# ASTRA_CERTIFIED: arb", FORMAL_TRANSLATOR_PROMPT)
        for name in ("branch_index", "certify_sup_abs_le", "analytic_tail", "Undecided"):
            self.assertIn(name, FORMAL_TRANSLATOR_PROMPT)
        self.assertIn("never negate it", FORMAL_TRANSLATOR_PROMPT)
        for vnext in (False, True):
            for variant in ("", "neutral"):
                prompt = reviewer_prompt(vnext, variant)
                with self.subTest(vnext=vnext, variant=variant):
                    self.assertIn("# ASTRA_CERTIFIED: arb", prompt)
                    self.assertIn("Treat its functions as correct", prompt)
        self.assertIn("ANALYTIC_TAIL", REFUTATION_ANALYST_PROMPT)
        self.assertIn("conditionally", REFUTATION_ANALYST_PROMPT)

    def test_reviewer_rules_are_numbered_once(self):
        import re

        from agents.reviewer import reviewer_prompt

        numbers = re.findall(r"(?m)^(\d+)\. ", reviewer_prompt(True))
        self.assertEqual(numbers, [str(n) for n in range(1, len(numbers) + 1)])


if __name__ == "__main__":
    unittest.main()


TAIL_CODE = (
    "# ASTRA_CERTIFIED: arb\n"
    "res = sup_abs_on_sector(lambda z: (-z).exp(), 1, 3, -arb.pi() / 4, arb.pi() / 4)\n"
    "analytic_tail('|exp(-z)| <= exp(-3 cos(pi/4)) for |z| > 3 in the cone')\n"
    "ok = res['certified'] and res['upper'] < 0.6\n"
    "print(f\"CHECK cone: {'OK' if ok else 'FAIL'} -- sup <= {res['upper']}\")\n"
    "print('VERDICT: PASS' if ok else 'VERDICT: FAIL')\n"
)


@unittest.skipUnless(HAVE_FLINT, "python-flint is not installed")
class CycleResult(unittest.IsolatedAsyncioTestCase):
    async def test_a_tail_lemma_makes_the_verdict_conditional(self):
        from tests.cycle_artifacts import remove_cycle_artifacts
        from tests.test_input_request_cycle import _fake, _run

        analysis = {"status": "VALIDATED", "reasoning": "sector bound certified",
                    "original_claim_verdict": "SUPPORTED",
                    "original_claim_reasoning": "P holds on the sector.",
                    "goal_coverage": "COMPLETE", "goal_resolved": True}
        result = await _run(_fake(TAIL_CODE, analysis), {})
        try:
            self.assertEqual(result["status"], "VALIDATED", result.get("error"))
            tail = "|exp(-z)| <= exp(-3 cos(pi/4)) for |z| > 3 in the cone"
            self.assertEqual(result["analytic_tails"], [tail])
            self.assertIs(result["conditional_on_assumptions"], True)
            self.assertIn(f"Prove the analytic tail lemma: {tail}", result["deferred_claims"])
            self.assertNotEqual(result["goal_coverage"]["status"], "complete")
            self.assertEqual(result["certified_prelude"], prelude_info())
            # The analyst reads the validator as written, not the prelude.
            self.assertEqual(result["execution"]["validation_code"].splitlines()[0],
                             "# ASTRA_CERTIFIED: arb")
        finally:
            remove_cycle_artifacts(result)
