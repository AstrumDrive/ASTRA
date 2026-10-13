"""Reviewer rules 17-18 (1.1.11, from ASTRA 2.0 a1c2128)."""
import unittest

from agents.reviewer import CODE_REVIEWER_VNEXT_PROMPT, CODE_REVIEWER_VNEXT_PROMPT_NEUTRAL


class ReviewerBurdenRules(unittest.TestCase):
    def test_rules_are_in_both_vnext_prompts(self):
        for prompt in (CODE_REVIEWER_VNEXT_PROMPT, CODE_REVIEWER_VNEXT_PROMPT_NEUTRAL):
            self.assertIn("17. MATCH THE BURDEN TO THE DECISIVE QUESTION", prompt)
            self.assertIn("18. RULE 17 NEVER OPENS THE GATE", prompt)
            self.assertIn("`sampling_as_proof`", prompt)

    def test_no_reference_to_a_rule_production_does_not_have(self):
        self.assertNotIn("Rules 2, 3, 4 and 15", CODE_REVIEWER_VNEXT_PROMPT)


if __name__ == "__main__":
    unittest.main()
