"""Plan-mode artifacts are removed where they are produced, and never silently.

ASTRA invokes `agy` with `--mode plan` deliberately - it is the read-only
sandbox that keeps the CLI from writing files or executing, the same role as
`--tools ""` for claude. The artifact pointer is therefore the structural cost
of that safety choice, present in 72 % of the deliberations sampled on
2026-08-14, and it is what killed cycle_20260814_091435_ea77 once synthesis let
it through into the conjecture.

The samples below are real, taken from deposited checkpoints. The wording
varies and changes language; the `file://` link does not.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from core import cli_backend
from core.cli_backend import strip_plan_artifacts


def _promptfile():
    path = os.path.join(tempfile.mkdtemp(prefix="astra_test_"), "prompt.txt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("prompt")
    return path

REAL_SAMPLES = [
    "The formal proposition has been constructed.\n\n"
    "[unitary_evolution_trace_plan.md](file:///C:/Users/Nelson/.gemini/"
    "antigravity-cli/brain/df78e853/plan.md)",
    "I have formalized the intuition into a rigorous, testable mathematical "
    "hypothesis within an implementation plan. \n\nPlease review the "
    "[schwarzschild_ricci_hypothesis.md](file:///C:/Users/Nelson/.gemini/"
    "antigravity-cli/brain/ace2f810/plan.md)",
    "He estructurado la refutacion adversarial de RIVAL A en el artefacto "
    "[`refutation_plan.md`](file:///C:/Users/Nelson/.gemini/antigravity-cli/"
    "brain/3f29adbe/plan.md)",
    "You can review the formalization here: [hagen_poiseuille_plan.md]"
    "(file:///C:/Users/Nelson/.gemini/antigravity-cli/brain/77b4b7a5/plan.md)",
]

# The one that actually reached a conjecture and cost a cycle 1471 s.
FATAL = (
    "All conclusions about extensive flat cavities remain deferred.\n\n"
    "---\n"
    "Review the proposed implementation plan artifact [plan.md](file:///C:/"
    "Users/Nelson/.gemini/antigravity-cli/brain/f1509b72/plan.md) to formally "
    "construct the exact symbolic python validator for this conjecture. "
    "Pending your approval."
)


class StrippingTests(unittest.TestCase):
    def test_every_real_sample_loses_its_artifact_pointer(self):
        for sample in REAL_SAMPLES:
            with self.subTest(sample=sample[:48]):
                clean, note = strip_plan_artifacts(sample)
                self.assertNotIn("file://", clean)
                self.assertNotIn("plan.md", clean)
                self.assertTrue(note)

    def test_a_reply_that_is_only_a_pointer_comes_back_empty(self):
        """Two of the four real samples are nothing but the pointer.

        That is not an answer: the model wrote its content to a file ASTRA
        cannot read. Returning empty lets the caller treat it as the
        operational failure it is, instead of feeding a useless instruction
        into the ensemble.
        """
        for sample in REAL_SAMPLES[2:]:
            with self.subTest(sample=sample[:48]):
                clean, note = strip_plan_artifacts(sample)
                self.assertEqual(clean, "")
                self.assertTrue(note)

    def test_the_fatal_one_keeps_the_physics_and_drops_the_order(self):
        clean, note = strip_plan_artifacts(FATAL)
        self.assertIn("extensive flat cavities remain deferred", clean)
        self.assertNotIn("file://", clean)
        self.assertNotIn("Pending your approval", clean)
        # The trailing separator left behind by the removed paragraph goes too.
        self.assertFalse(clean.rstrip().endswith("---"))
        self.assertIn("plan-mode artifact removed", note)

    def test_removal_is_announced(self):
        _clean, note = strip_plan_artifacts(REAL_SAMPLES[0])
        self.assertIn("1 line(s)", note)

    def test_ordinary_answers_are_untouched(self):
        for text in (
            "The conjecture is refuted by the counterexample x = 0.",
            "See https://arxiv.org/abs/2405.02709 for the shell construction.",
            "",
        ):
            with self.subTest(text=text[:40]):
                clean, note = strip_plan_artifacts(text)
                self.assertEqual(clean, text)
                self.assertEqual(note, "")

    def test_the_caller_turns_a_pointer_only_reply_into_a_failure(self):
        """End to end: an answer left in a file is a failed call, not content."""
        only = "[plan.md](file:///C:/Users/Nelson/.gemini/brain/x/plan.md)"
        seen = {}

        class _Proc:
            returncode = 0
            stdout = only
            stderr = ""

        with patch.object(cli_backend.subprocess, "Popen") as popen:
            popen.return_value.communicate.return_value = (only, "")
            popen.return_value.pid = 1234
            popen.return_value.returncode = 0
            res = cli_backend._invoke_once(
                "agy", _promptfile(), "out.txt", None, ".", dict(os.environ), 5
            )
        seen["res"] = res
        self.assertFalse(res.ok)
        self.assertIn("plan-mode", res.error)


if __name__ == "__main__":
    unittest.main()
