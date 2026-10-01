"""The validator author must see the user's own claim text, not only the objective.

Regression for the 2026-10-01 research-claims measurement: definitions written
in ``intuition`` never reached the validator author, which declared them
MISSING (docs/evidence/RESEARCH_CLAIMS_COMPARISON_20260930.md).
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import astra_tool  # noqa: E402

build = astra_tool.build_translation_input


class TranslationInputTests(unittest.TestCase):
    def test_intuition_definitions_reach_the_author(self):
        text = build(
            "Determine whether [B_1, H_J] = -i J C_1.",
            "Model: impurity spin S = sigma/2 tensored with four Jordan-Wigner modes 0up, 0dn, 1up, 1dn. H_J = J sum_a S^a s_0^a.",
            "",
            "[Hypothesis] The commutator identity holds.",
        )
        self.assertIn("SHARED FINAL OBJECTIVE:\nDetermine whether", text)
        self.assertIn("USER'S CLAIM AND DEFINITIONS", text)
        self.assertIn("four Jordan-Wigner modes 0up, 0dn, 1up, 1dn", text)
        self.assertTrue(text.endswith("CONSENSUS CONJECTURE TO VALIDATE:\n[Hypothesis] The commutator identity holds."))

    def test_objective_and_intuition_before_conjecture_and_after_goal(self):
        text = build("goal", "claim with definitions", "USER INPUTS:\n- J = 1", "conjecture")
        order = [text.index(k) for k in ("SHARED FINAL OBJECTIVE", "USER'S CLAIM AND DEFINITIONS", "USER INPUTS", "CONSENSUS CONJECTURE")]
        self.assertEqual(order, sorted(order))

    def test_no_duplicate_block_when_intuition_is_the_goal(self):
        # A request without `objective` uses the intuition as shared goal.
        text = build("same text", "same text", "", "conjecture")
        self.assertNotIn("USER'S CLAIM AND DEFINITIONS", text)
        self.assertEqual(text.count("same text"), 1)

    def test_long_intuition_is_capped_but_conjecture_stays_within_reviewer_window(self):
        long_claim = "x" * (astra_tool.AUTHOR_INTUITION_CHARS + 2000)
        text = build("goal", long_claim, "", "THE CONJECTURE")
        self.assertIn("[... truncated for the author", text)
        self.assertLess(text.index("CONSENSUS CONJECTURE TO VALIDATE"), 5000)
        self.assertIn("THE CONJECTURE", text)

    def test_empty_intuition_keeps_legacy_shape(self):
        text = build("goal", "", "", "conjecture")
        self.assertEqual(text, "SHARED FINAL OBJECTIVE:\ngoal\n\nCONSENSUS CONJECTURE TO VALIDATE:\nconjecture")


if __name__ == "__main__":
    unittest.main()
