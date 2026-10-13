"""A kernel-checked proof whose verdict was never printed.

`lean_nat_add_comm` was the only deterministic operational failure in the
quality suite: 6 CODE_ERRORs in 6 complete runs, while every other operational
failure churned in and out. That distinction was invisible in the aggregate --
the rate sat at 21.2% for seven runs while two cases failed always and
nineteen failed sometimes, and averaging the two modes hid the one with a
reproducible cause.

The cause was not a broken tool. ASTRA proved `Nat.add_comm`, the Lean kernel
accepted it, and `original_claim_verdict` came back SUPPORTED every time. But
`lean <file>` elaborates and stops, so the `def main : IO Unit` that prints the
verdict the case asks for was type-checked and never evaluated. Exit code 0,
empty stdout, and a case scored as broken infrastructure for producing the
right mathematics.

The remedy has to run `main` without weakening what the case checks. Lean
elaborates the whole file before the interpreter starts, so `--run` cannot
print a verdict for a proof that does not compile -- which is exactly the
case's own stated failure mode, "Printing PASS without compiling a theorem".
These tests pin both halves: that the verdict now gets emitted, and that it
still cannot be emitted without the proof.
"""
import unittest

from core.formal_validators import (
    _lean4_missing_main,
    lean4_argv_tail,
    lean4_declares_main,
)


GOOD = (
    "theorem probe (n m : Nat) : n + m = m + n := Nat.add_comm n m\n"
    "\n"
    'def main : IO Unit := IO.println "VERDICT: PASS"\n'
)
NO_MAIN = "theorem probe (n m : Nat) : n + m = m + n := Nat.add_comm n m\n"


class DeclaresMain(unittest.TestCase):
    def test_plain_declaration(self):
        self.assertTrue(lean4_declares_main(GOOD))

    def test_modifiers_and_attributes(self):
        for source in (
            "unsafe def main : IO Unit := pure ()",
            "partial def main (args : List String) : IO UInt32 := pure 0",
            "@[inline] def main : IO Unit := pure ()",
            "noncomputable def main : IO Unit := pure ()",
            "  def main : IO Unit := pure ()",
        ):
            with self.subTest(source=source):
                self.assertTrue(lean4_declares_main(source))

    def test_theorem_only_artifact_declares_no_main(self):
        self.assertFalse(lean4_declares_main(NO_MAIN))

    def test_similar_names_are_not_main(self):
        # `mainLemma` is a different declaration; `\b` has to hold the line or
        # every artifact with a name starting "main" would take `--run` and
        # fail with "unknown declaration 'main'".
        for source in (
            "def mainLemma : Nat := 3",
            "def main_helper : Nat := 3",
            "theorem maintain (n : Nat) : n = n := rfl",
        ):
            with self.subTest(source=source):
                self.assertFalse(lean4_declares_main(source))

    def test_empty_source(self):
        self.assertFalse(lean4_declares_main(""))
        self.assertFalse(lean4_declares_main(None))


class ArgvTail(unittest.TestCase):
    def test_main_gets_run(self):
        self.assertEqual(
            lean4_argv_tail(GOOD, "/tmp/a.lean"),
            ["lean", "--run", "/tmp/a.lean"],
        )

    def test_no_main_stays_on_plain_elaboration(self):
        # The regression this guards: `--run` on a file without `main` exits 1
        # with "unknown declaration 'main'", so an unconditional flag would
        # break every artifact that proves a theorem without printing.
        self.assertEqual(
            lean4_argv_tail(NO_MAIN, "/tmp/a.lean"),
            ["lean", "/tmp/a.lean"],
        )

    def test_path_is_last_either_way(self):
        for source in (GOOD, NO_MAIN):
            with self.subTest(has_main=lean4_declares_main(source)):
                self.assertEqual(
                    lean4_argv_tail(source, "/tmp/a.lean")[-1], "/tmp/a.lean"
                )


class MissingMainFallback(unittest.TestCase):
    """The regex reads source text, so it can be wrong; the retry covers it."""

    def test_detects_the_interpreter_error_on_either_stream(self):
        message = "(interpreter) unknown declaration 'main'"
        self.assertTrue(_lean4_missing_main(message, ""))
        self.assertTrue(_lean4_missing_main("", message))

    def test_does_not_fire_on_an_unrelated_failure(self):
        # A type mismatch must stay a failure. Retrying that one without
        # `--run` would convert a refuted proof into a clean compile.
        self.assertFalse(
            _lean4_missing_main("", "error: Type mismatch\n  Nat.add_comm n m")
        )
        self.assertFalse(_lean4_missing_main("", ""))

    def test_namespaced_main_is_the_false_positive_the_retry_absorbs(self):
        # The real false positive, found by writing this test: `def main`
        # inside a namespace matches the regex, but Lean declares it as
        # `Foo.main` and there is no top-level `main` to interpret. Verified
        # against the pinned toolchain on 2026-08-29 -- `--run` exits 1 with
        # "unknown declaration 'main'" and plain elaboration exits 0 -- so the
        # retry is what keeps this artifact compiling.
        source = (
            "theorem probe (n m : Nat) : n + m = m + n := Nat.add_comm n m\n"
            "\n"
            "namespace Foo\n"
            'def main : IO Unit := IO.println "VERDICT: PASS"\n'
            "end Foo\n"
        )
        self.assertTrue(lean4_declares_main(source))
        self.assertIn("--run", lean4_argv_tail(source, "/tmp/a.lean"))
        self.assertTrue(
            _lean4_missing_main("", "(interpreter) unknown declaration 'main'")
        )

    def test_commented_out_main_is_not_detected_at_all(self):
        # A `--` comment does not reach the regex, so this artifact never takes
        # `--run` and never needs the retry. Asserted because the first draft
        # of these tests assumed the opposite and claimed the retry had been
        # exercised end to end when it had not.
        source = (
            '-- def main : IO Unit := IO.println "VERDICT: PASS"\n'
            "theorem probe (n m : Nat) : n + m = m + n := Nat.add_comm n m\n"
        )
        self.assertFalse(lean4_declares_main(source))
        self.assertNotIn("--run", lean4_argv_tail(source, "/tmp/a.lean"))


class SoundnessIsUnchanged(unittest.TestCase):
    """`--run` must not become a way to print a verdict without a proof."""

    def test_placeholders_are_still_rejected_before_any_invocation(self):
        # `_forbidden_tokens` runs ahead of the argv decision, so a `sorry`
        # never reaches Lean regardless of whether `main` is declared.
        from core.formal_validators import _forbidden_tokens

        cheat = (
            "theorem probe (n m : Nat) : n + m = m + n := by sorry\n"
            'def main : IO Unit := IO.println "VERDICT: PASS"\n'
        )
        self.assertEqual(_forbidden_tokens(cheat), ["sorry"])

    def test_a_false_theorem_still_carries_main(self):
        # Documents the ordering the fix leans on rather than re-testing Lean:
        # this source is selected for `--run`, and Lean elaborates before
        # interpreting, so the type mismatch lands first and `main` never runs.
        # Measured 2026-08-29: exit 1, no "VERDICT: PASS" on stdout.
        false_proof = (
            "theorem probe (n m : Nat) : n + m = m + n + 1 := Nat.add_comm n m\n"
            'def main : IO Unit := IO.println "VERDICT: PASS"\n'
        )
        self.assertIn("--run", lean4_argv_tail(false_proof, "/tmp/a.lean"))


if __name__ == "__main__":
    unittest.main()
