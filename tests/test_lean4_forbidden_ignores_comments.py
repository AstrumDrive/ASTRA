"""A sound proof, rejected for talking about the thing it doesn't do.

`_forbidden_tokens` is a raw text scan for sorry/admit/axiom, so before this
fix it fired on the *word* anywhere in the file, including inside `--` line
comments and `/- -/` (or `/-- -/` doc) block comments. This is not
hypothetical: `lean_nat_add_comm` measured it directly on 2026-08-31
(quality_20260831_125334.json, the run after the cycle-timeout fix removed
the previous failure mode). The translator's corrected patch carried a doc
comment reading "the concrete declaration elaborates with no `sorry`, no
pending goals" and a line comment reading "axiom set via the standard
command" -- prose *about* the absence of these constructs, describing the
very audit machinery (`#print axioms`, `Lean.collectAxioms`) that proves the
axiom closure is empty. `_FORBIDDEN` cannot tell a mention from a use, so it
rejected a proof the reviewer had already approved, before Lean ever ran:
`validator_model_patch_history` recorded `CANNOT_PATCH` because no forbidden
token existed anywhere outside that prose.

These tests pin both halves: that prose mentioning the words no longer
trips the gate, and that an actual `sorry`/`admit`/`axiom` outside a comment
still does -- including the exact source that produced the false positive.
"""
import unittest

from core.formal_validators import _forbidden_tokens, _strip_lean_comments


class ProseIsNotAUse(unittest.TestCase):
    def test_sorry_mentioned_in_a_doc_comment_is_not_forbidden(self):
        source = (
            "/-- Claim 1: the concrete declaration elaborates with no "
            "`sorry`, no pending goals and no kernel error. -/\n"
            "theorem probe (n m : Nat) : n + m = m + n := Nat.add_comm n m\n"
        )
        self.assertEqual(_forbidden_tokens(source), [])

    def test_axiom_mentioned_in_a_line_comment_is_not_forbidden(self):
        source = (
            "-- Claim 3 (human-visible evidence): axiom set via the "
            "standard command.\n"
            "#print axioms probe\n"
        )
        self.assertEqual(_forbidden_tokens(source), [])

    def test_print_axioms_command_is_not_forbidden(self):
        # `axioms` (plural) never matched `\baxiom\b` even before this fix --
        # pinned here so a future change to the regex can't regress it.
        self.assertEqual(_forbidden_tokens("#print axioms probe\n"), [])

    def test_the_exact_rejected_case_now_passes(self):
        # The full validation_code from quality_20260831_125334.json's
        # lean_nat_add_comm record, reproduced verbatim (modulo the
        # ASTRA_ENGINE marker, which clean_lean4_source strips separately).
        source = """import Mathlib

open Lean Lean.Meta Lean.Elab Lean.Elab.Command Lean.Elab.Term

/-- Claim 1: the concrete declaration elaborates with no `sorry`, no pending
    goals and no kernel error. If `Nat.add_comm n m` did not inhabit the
    ascribed type, this very line would fail to compile. -/
theorem astra_nat_add_comm (n m : Nat) : Nat.add n m = Nat.add m n := by
  exact Nat.add_comm n m

/-- Claim 2 (compile-time leg): the proof term inhabits the *universally
    quantified* type verbatim, enforced by the elaborator/kernel and not by
    textual coincidence with the pretty-printer. -/
example : ∀ n m : Nat, Nat.add n m = Nat.add m n := astra_nat_add_comm

-- Claim 3 (human-visible evidence): axiom set via the standard command.
#print axioms astra_nat_add_comm

run_cmd liftTermElabM do
  let expectedStx ← `(∀ n m : Nat, Nat.add n m = Nat.add m n)
  let expected ← Lean.Elab.Term.elabType expectedStx
  let some cinfo := (← getEnv).find? ``astra_nat_add_comm
    | throwError "operational: constant astra_nat_add_comm not found"
  let typeOk ← isDefEq cinfo.type expected
  let axs ← Lean.collectAxioms ``astra_nat_add_comm
  let axOk := axs.isEmpty
  if typeOk && axOk then
    logInfo "VERDICT: PASS"
  else
    logInfo "VERDICT: FAIL"
"""
        self.assertEqual(_forbidden_tokens(source), [])


class RealUseIsStillCaught(unittest.TestCase):
    def test_sorry_tactic_outside_a_comment_is_still_forbidden(self):
        cheat = "theorem probe (n m : Nat) : n + m = m + n := by sorry\n"
        self.assertEqual(_forbidden_tokens(cheat), ["sorry"])

    def test_admit_outside_a_comment_is_still_forbidden(self):
        cheat = "theorem probe (n m : Nat) : n + m = m + n := by admit\n"
        self.assertEqual(_forbidden_tokens(cheat), ["admit"])

    def test_axiom_declaration_outside_a_comment_is_still_forbidden(self):
        cheat = "axiom probe (n m : Nat) : n + m = m + n\n"
        self.assertEqual(_forbidden_tokens(cheat), ["axiom"])

    def test_sorry_after_a_comment_on_the_same_line_is_still_forbidden(self):
        # The comment ends at the newline, so code that follows it on a
        # later line is untouched by the strip.
        cheat = (
            "-- axiom set via the standard command\n"
            "theorem probe (n m : Nat) : n + m = m + n := by sorry\n"
        )
        self.assertEqual(_forbidden_tokens(cheat), ["sorry"])


class BlockCommentsNest(unittest.TestCase):
    def test_nested_block_comment_is_fully_stripped(self):
        # Lean allows nesting; a naive non-greedy `/-.*?-/` would close on
        # the first `-/` and leak the outer comment's tail back into code.
        source = "/- outer /- inner sorry -/ still comment -/\ntheorem probe : True := trivial\n"
        self.assertEqual(_forbidden_tokens(source), [])

    def test_stripped_source_keeps_line_count_stable_enough_for_diagnostics(self):
        # Line comments collapse to a bare newline (not vanish) so line
        # numbers in any future error reporting over the stripped text stay
        # aligned with the original source.
        source = "-- axiom\ntheorem probe : True := trivial\n"
        self.assertEqual(_strip_lean_comments(source).count("\n"), source.count("\n"))


class StringLiteralsAreNotScannedForDelimiters(unittest.TestCase):
    def test_a_dash_dash_inside_a_string_does_not_start_a_comment(self):
        # If `--` inside a string were treated as a comment start, everything
        # after it -- including a real `sorry` on the next line -- would be
        # silently stripped, turning the gate into a bypass instead of a
        # false positive.
        source = (
            'def note : String := "see -- for details"\n'
            "theorem probe (n m : Nat) : n + m = m + n := by sorry\n"
        )
        self.assertEqual(_forbidden_tokens(source), ["sorry"])


if __name__ == "__main__":
    unittest.main()
