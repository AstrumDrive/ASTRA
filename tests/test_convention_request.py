"""A claim left open only by an unstated convention comes back as a question.

Regression for the 9 October 2026 benchmark: "a/b=c/b implies a=c for all
real a,b,c" and the Hagen-Poiseuille scaling ended VALIDATED with
original_claim_verdict INCONCLUSIVE, although the first validator had decided
every reading of the division at b = 0. The result now names the readings and
the exact re-run for each; status and original_claim_verdict never move.
"""
from __future__ import annotations

import json
import unittest

from agents.analyst import REFUTATION_ANALYST_PROMPT
from core.input_request import (
    CONVENTION_PREFIX,
    CONVENTIONS_MAX,
    build_convention_request,
    build_input_request,
    normalize_convention_request,
)
from core.llm_client import ASTRAIntelligence
from tests.cycle_artifacts import remove_cycle_artifacts
from tests.test_input_request_cycle import GOAL, ND_CODE, RAW, _fake, _run

DIVISION = {
    "question": "How is a/b read at b = 0?",
    "conventions": [
        {"label": "b nonzero", "statement": "The claim quantifies only over b != 0."},
        {"label": "x/0 := 0", "statement": "Division is totalized with x/0 = 0 (Lean/Mathlib)."},
        "Ordinary real division: the hypothesis a/b = c/b is false when b = 0.",
    ],
}
PASS_CODE = (
    "from fractions import Fraction as F\n"
    "ok = all(F(a, b) != F(c, b) or a == c for a in range(-3, 4) for c in range(-3, 4)"
    " for b in (1, 2, -5))\n"
    "print(f\"CHECK restricted: {'OK' if ok else 'FAIL'}\")\n"
    "print('VERDICT: PASS' if ok else 'VERDICT: FAIL')\n"
)
# A PASS that cannot fail: the deterministic guard turns it into WEAK_PASS.
HARDCODED_PASS = "print('CHECK restricted: OK')\nprint('VERDICT: PASS')\n"


def _analysis(status="VALIDATED", verdict="INCONCLUSIVE", request=DIVISION):
    analysis = {"status": status, "reasoning": "decided the restricted claim",
                "original_claim_verdict": verdict,
                "original_claim_reasoning": "P is undecided at b = 0 as stated."}
    if request is not None:
        analysis["convention_request"] = request
    return analysis


class Shape(unittest.TestCase):
    def test_conventions_are_cleaned_deduplicated_and_capped(self):
        raw = {"question": "  Which   reading? ",
               "conventions": ["b != 0", {"label": "", "statement": "b != 0 "},
                               {"label": "no statement"}, 7, "x/0 := 0", "x/0 := x",
                               "x/0 undefined", "a fifth reading"]}
        request = normalize_convention_request(raw)
        self.assertEqual(request["question"], "Which reading?")
        statements = [c["statement"] for c in request["conventions"]]
        self.assertEqual(len(statements), CONVENTIONS_MAX)
        self.assertEqual(statements, ["b != 0", "x/0 := 0", "x/0 := x", "x/0 undefined"])
        self.assertTrue(all(c["label"] for c in request["conventions"]))

    def test_nothing_usable_is_none_never_a_guess(self):
        for raw in (None, "b != 0", [], {}, {"question": "q"}, {"conventions": "b != 0"},
                    {"conventions": [{"label": "only a label"}, ""]}):
            with self.subTest(raw=raw):
                self.assertIsNone(normalize_convention_request(raw))

    def test_long_fields_are_shortened(self):
        request = normalize_convention_request(
            {"question": "q" * 900, "conventions": [{"label": "l" * 200, "statement": "s" * 900}]}
        )
        self.assertLessEqual(len(request["question"]), 500)
        self.assertLessEqual(len(request["conventions"][0]["label"]), 80)
        self.assertLessEqual(len(request["conventions"][0]["statement"]), 400)


class Gate(unittest.TestCase):
    def test_only_a_decided_cycle_with_an_open_claim_asks(self):
        self.assertIsNotNone(build_convention_request(_analysis(), {}))
        self.assertIsNotNone(build_convention_request(_analysis("REFUTED", "SUBSTITUTED"), {}))
        for status in ("CODE_ERROR", "NON_DECIDABLE", "API_ERROR", "", None):
            with self.subTest(status=status):
                self.assertIsNone(build_convention_request(_analysis(status=status), {}))
        for verdict in ("SUPPORTED", "REFUTED", "UNSPECIFIED", ""):
            with self.subTest(verdict=verdict):
                self.assertIsNone(build_convention_request(_analysis(verdict=verdict), {}))
        self.assertIsNone(build_convention_request(_analysis(request=None), {}))
        self.assertIsNone(build_convention_request(None, {}))

    def test_one_rerun_per_reading_plus_other_without_resume(self):
        req = {"intuition": "raw", "objective": "Determine whether P.", "oracle": "astrum",
               "max_mode": True, "resume_checkpoint": r"C:\ck\x.json", "input_policy": "assume"}
        ask = build_convention_request(_analysis(), req)
        self.assertEqual(ask["action_required"], "ASK_USER")
        self.assertEqual(ask["kind"], "convention")
        self.assertEqual(set(ask["options"]),
                         {"convention_1", "convention_2", "convention_3", "other"})
        self.assertIn("How is a/b read at b = 0?", ask["question"])
        self.assertIn("(2) Division is totalized with x/0 = 0", ask["question"])
        self.assertNotIn("resume_checkpoint", ask)
        for name, option in ask["options"].items():
            rerun = option["rerun"]
            with self.subTest(option=name):
                self.assertEqual(rerun["intuition"], "raw")
                self.assertEqual(rerun["objective"], "Determine whether P.")
                self.assertEqual(rerun["oracle"], "astrum")
                self.assertIs(rerun["max_mode"], True)
                # A convention can change the conjecture: never reuse it.
                self.assertNotIn("resume_checkpoint", rerun)
                self.assertNotIn("input_policy", rerun)
                self.assertTrue(rerun["inputs"].startswith(CONVENTION_PREFIX))
        self.assertTrue(ask["options"]["convention_1"]["rerun"]["inputs"].endswith(
            "The claim quantifies only over b != 0."))
        self.assertEqual(ask["options"]["convention_3"]["label"][:20], "Ordinary real divisi")

    def test_inputs_already_supplied_are_kept(self):
        ask = build_convention_request(_analysis(), {"objective": "goal", "inputs": "U0 = 0.3"})
        rerun = ask["options"]["convention_2"]["rerun"]
        self.assertTrue(rerun["inputs"].startswith("U0 = 0.3\n" + CONVENTION_PREFIX))

    def test_missing_input_requests_say_their_kind(self):
        ask = build_input_request(["U0"], "", {})
        self.assertEqual(ask["kind"], "missing_inputs")
        self.assertEqual(set(ask["options"]), {"provide", "assume", "extract"})
        self.assertNotIn("conventions", ask)

    def test_a_missing_convention_adds_one_fresh_option_per_reading(self):
        # Live run 2026-10-09 05:23: the validator itself declared
        # "MISSING: a convention for real division at b = 0".
        req = {"intuition": "raw", "objective": "goal"}
        ask = build_input_request(["a convention for division at b = 0."], r"C:\ck\x.json",
                                  req, convention_request=DIVISION)
        self.assertEqual(ask["kind"], "missing_inputs")
        self.assertEqual(set(ask["options"]), {"provide", "assume", "extract",
                                               "convention_1", "convention_2", "convention_3"})
        self.assertEqual(len(ask["conventions"]), 3)
        self.assertIn("at b = 0. Do you have", ask["question"])      # no doubled period
        self.assertIn("(1) The claim quantifies only over b != 0;", ask["question"])
        self.assertEqual(ask["options"]["provide"]["rerun"]["resume_checkpoint"], r"C:\ck\x.json")
        for name in ("convention_1", "convention_2", "convention_3"):
            rerun = ask["options"][name]["rerun"]
            self.assertNotIn("resume_checkpoint", rerun)
            self.assertTrue(rerun["inputs"].startswith(CONVENTION_PREFIX))
        self.assertEqual(ask["resume_checkpoint"], r"C:\ck\x.json")
        self.assertIn("fresh cycle", ask["note"])
        # Garbage from the analyst leaves the plain question untouched.
        plain = build_input_request(["U0"], "", req, convention_request={"conventions": "x"})
        self.assertEqual(set(plain["options"]), {"provide", "assume", "extract"})


class AnalystContract(unittest.IsolatedAsyncioTestCase):
    def test_prompt_asks_for_readings_not_for_verdicts_per_reading(self):
        self.assertIn("convention_request", REFUTATION_ANALYST_PROMPT)
        self.assertIn("do not state a", REFUTATION_ANALYST_PROMPT)
        self.assertIn("verdict per reading", REFUTATION_ANALYST_PROMPT)
        self.assertIn("CONVENTION chosen by the user", REFUTATION_ANALYST_PROMPT)
        # Live run 05:35: with the request only under rule 3 the analyst of a
        # NON_DECIDABLE cycle omitted it; the NON_DECIDABLE rule must say it.
        rule_1 = REFUTATION_ANALYST_PROMPT.split("2. INDEPENDENT AUDIT")[0]
        self.assertIn("ALSO return `convention_request`", rule_1)
        # The prefix the re-run carries is the phrase the analyst is told to honor.
        self.assertIn("CONVENTION (chosen by the user", CONVENTION_PREFIX)

    async def _analyze(self, reply):
        analyst = ASTRAIntelligence(provider="codex_cli")

        async def fake_call(_system, _user):
            return json.dumps(reply)

        analyst._call_api = fake_call
        return await analyst.analyze_results(
            "a/b=c/b implies a=c when b != 0",
            {"exit_code": 0, "stdout": "CHECK restricted: OK\nVERDICT: PASS", "stderr": "",
             "validation_code": PASS_CODE, "code_review": {"status": "APPROVED"}},
            shared_goal="Determine whether a/b=c/b implies a=c for all real a,b,c.",
            original_claim="Test the cancellation law.",
        )

    async def test_the_readings_survive_the_parser_in_closed_shape(self):
        result = await self._analyze(_analysis())
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["original_claim_verdict"], "INCONCLUSIVE")
        self.assertEqual(len(result["convention_request"]["conventions"]), 3)
        self.assertEqual(result["convention_request"]["conventions"][2]["statement"],
                         DIVISION["conventions"][2])

    async def test_a_malformed_request_is_dropped(self):
        result = await self._analyze(_analysis(request={"conventions": "b != 0"}))
        self.assertNotIn("convention_request", result)
        self.assertEqual(result["original_claim_verdict"], "INCONCLUSIVE")


class CycleResult(unittest.IsolatedAsyncioTestCase):
    async def test_open_claim_carries_the_question_and_keeps_both_axes(self):
        result = await _run(_fake(PASS_CODE, _analysis()), {})
        try:
            self.assertEqual(result["status"], "VALIDATED", result.get("error"))
            self.assertEqual(result["original_claim_verdict"], "INCONCLUSIVE")
            ask = result["input_request"]
            self.assertEqual(ask["kind"], "convention")
            self.assertEqual(ask["options"]["convention_1"]["rerun"]["objective"], GOAL)
            self.assertEqual(ask["options"]["convention_1"]["rerun"]["intuition"], RAW)
            self.assertNotIn("resume_checkpoint", ask["options"]["other"]["rerun"])
        finally:
            remove_cycle_artifacts(result)

    async def test_the_gate_reads_the_final_status_after_the_guard(self):
        # The analyst proposed readings, but the deterministic guard found a
        # PASS that cannot fail: the INCONCLUSIVE has another cause now.
        result = await _run(_fake(HARDCODED_PASS, _analysis()), {})
        try:
            self.assertEqual(result["status"], "WEAK_PASS", result.get("error"))
            self.assertNotIn("input_request", result)
        finally:
            remove_cycle_artifacts(result)

    async def test_a_decided_claim_asks_nothing(self):
        result = await _run(_fake(PASS_CODE, _analysis(verdict="SUPPORTED")), {})
        try:
            self.assertEqual(result["original_claim_verdict"], "SUPPORTED", result.get("error"))
            self.assertNotIn("input_request", result)
        finally:
            remove_cycle_artifacts(result)

    async def test_a_missing_convention_keeps_the_missing_input_question(self):
        analysis = {"status": "NON_DECIDABLE", "reasoning": "convention absent",
                    "missing_inputs": ["a frozen fixed point U0"],
                    "original_claim_verdict": "INCONCLUSIVE", "convention_request": DIVISION}
        result = await _run(_fake(ND_CODE, analysis), {})
        try:
            self.assertEqual(result["status"], "NON_DECIDABLE", result.get("error"))
            self.assertEqual(result["original_claim_verdict"], "INCONCLUSIVE")
            ask = result["input_request"]
            self.assertEqual(ask["kind"], "missing_inputs")
            self.assertEqual(ask["resume_checkpoint"], result["checkpoint"])
            self.assertIn("convention_3", ask["options"])
            self.assertNotIn("resume_checkpoint", ask["options"]["convention_1"]["rerun"])
            self.assertEqual(ask["options"]["convention_1"]["rerun"]["objective"], GOAL)
        finally:
            remove_cycle_artifacts(result)

    async def test_missing_data_without_readings_is_the_plain_question(self):
        analysis = {"status": "NON_DECIDABLE", "reasoning": "U0 absent",
                    "missing_inputs": ["a frozen fixed point U0"]}
        result = await _run(_fake(ND_CODE, analysis), {})
        try:
            self.assertEqual(result["status"], "NON_DECIDABLE", result.get("error"))
            self.assertEqual(set(result["input_request"]["options"]),
                             {"provide", "assume", "extract"})
        finally:
            remove_cycle_artifacts(result)


if __name__ == "__main__":
    unittest.main()
