"""Colour in the progress window (1.1.19)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import astra_progress as ap  # noqa: E402

VIEW = "\n".join([
    f"{ap.LABEL}  pid 1  started 10:00:00  [running]",
    "Objective : Determine whether P",
    "Phase     : review (round 1, revision 0)                elapsed 3m",
    "Progress  : [######........................]  20%   ETA ~ 10:09",
    "Phases    : conjecture 2m | plan 24s | review ... | analyze -",
    "Models    :",
    "  conjecture codex_cli  gpt-6.1-sol@ultra",
    "  review     codex_cli  gpt-6.1-sol@max   -> answered by gpt-6-luna (fallback)  <- now",
    "Outcome   : VALIDATED",
    "Claim P   : REFUTED",
    "Cause     : boom",
    "Last beat : 2s ago",
])


class Colour(unittest.TestCase):
    def setUp(self):
        self.lines = ap.colorize(VIEW).split("\n")

    def test_current_stage_is_yellow(self):
        now = self.lines[7]
        self.assertTrue(now.startswith(ap._C["yellow"]))
        self.assertIn(ap._paint("  <- now", "yellow"), now)
        self.assertIn(ap._paint("review ...", "yellow"), self.lines[4])
        self.assertIn(ap._C["yellow"], self.lines[2])

    def test_verdicts_and_failures(self):
        self.assertIn(ap._paint("VALIDATED", "green"), self.lines[8])
        self.assertIn(ap._paint("REFUTED", "red"), self.lines[9])
        self.assertIn(ap._paint("boom", "red"), self.lines[10])
        self.assertIn(ap._paint("[running]", "cyan"), self.lines[0])
        self.assertIn(ap._C["magenta"] + "-> answered by", self.lines[7])

    def test_verdict_words_are_whole_tokens(self):
        self.assertEqual(ap._verdict_colour("UNSUPPORTED"), "yellow")
        self.assertEqual(ap._verdict_colour("SUPPORTED"), "green")
        self.assertEqual(ap._verdict_colour("INCONCLUSIVE"), "yellow")
        self.assertEqual(ap._verdict_colour("CODE_ERROR"), "red")

    def test_plain_text_is_preserved(self):
        import re
        plain = re.sub(r"\x1b\[[0-9;]*m", "", ap.colorize(VIEW))
        self.assertEqual(plain, VIEW)


if __name__ == "__main__":
    unittest.main()
