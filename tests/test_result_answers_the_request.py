"""An episode is evidence only if the cycle ran for this claim.

Walked through on 2026-08-16 in campaign cmp_5e3c37c77e7b4841. A cycle job from
an unrelated project - an adversarial manuscript peer review - was running in
the same minute as a campaign step, and its result was fed in through the
`cycle_runner` hook. The ledger gained a SUPPORTS record whose validator checks
holonomy lifts and winding numbers, attached to a claim about the conformal
factor and the null energy condition.

Nothing downstream could have caught it. Every status axis, every gate and every
hash was correct about a result that answered a different question.
"""
import unittest

from core.campaign_executor import (
    CampaignExecutorError,
    _assert_result_answers_request,
)

CAMPAIGN_OBJECTIVE = (
    "Decide whether a constant-velocity travelling-wave spacetime can satisfy "
    "the pointwise energy conditions with non-exotic matter."
)
# The real foreign objective, abridged.
FOREIGN_OBJECTIVE = (
    "Produce an adversarial, evidence-oriented peer-review memo for the "
    "manuscript, with explicit separation of mathematical validity."
)


def request(objective=CAMPAIGN_OBJECTIVE):
    return {"objective": objective, "intuition": "decide the NEC at p"}


class BindingTests(unittest.TestCase):
    def test_the_foreign_result_is_refused(self):
        with self.assertRaises(CampaignExecutorError) as caught:
            _assert_result_answers_request(
                request(), {"status": "VALIDATED", "shared_goal": FOREIGN_OBJECTIVE}
            )
        message = str(caught.exception)
        # The message must show both sides; a bare refusal is hard to act on.
        self.assertIn("requested", message)
        self.assertIn("answered", message)

    def test_a_matching_result_passes(self):
        _assert_result_answers_request(
            request(), {"status": "VALIDATED", "shared_goal": CAMPAIGN_OBJECTIVE}
        )

    def test_surrounding_whitespace_is_not_a_mismatch(self):
        _assert_result_answers_request(
            request(), {"shared_goal": f"  {CAMPAIGN_OBJECTIVE}\n"}
        )

    def test_a_result_without_a_goal_is_allowed_through(self):
        """Test doubles carry no shared_goal; the check cannot bind them."""
        _assert_result_answers_request(request(), {"status": "VALIDATED"})

    def test_a_request_without_an_objective_cannot_bind_either(self):
        _assert_result_answers_request(
            {"intuition": "x"}, {"shared_goal": FOREIGN_OBJECTIVE}
        )

    def test_the_check_is_exact_not_fuzzy(self):
        """A near-miss objective is still a different question."""
        with self.assertRaises(CampaignExecutorError):
            _assert_result_answers_request(
                request(), {"shared_goal": CAMPAIGN_OBJECTIVE + " Also prove X."}
            )


if __name__ == "__main__":
    unittest.main()
