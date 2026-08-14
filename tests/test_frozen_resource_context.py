"""A case's `resources` mixes data files with capability notes.

Found 2026-08-14 while starting the stage-6 ablation: the canary tier died on
its first cell because `_frozen_resource_context` called `read_bytes()` on
"Optional GR_python package, resolved through ASTRA_GR_PYTHON_ROOT". Four of the
six frozen cases declare notes like that, including `gr_invariant_audit`, which
is one of the two canary cases - so the canary tier could not start at all.
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_research_trajectory_benchmarks",
        ROOT / "scripts" / "run_research_trajectory_benchmarks.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()


class Program:
    def __init__(self, resources):
        self.resources = tuple(resources)


class ClassificationTests(unittest.TestCase):
    def test_capability_notes_are_not_paths(self):
        for note in (
            "Optional GR_python package, resolved through ASTRA_GR_PYTHON_ROOT",
            "Lean 4 environment resolved through ASTRA_LOCAL_LEAN4_ROOT or the "
            "configured ASTRUM oracle",
            "Wolfram/Mathematica bridge when available",
        ):
            with self.subTest(note=note[:40]):
                self.assertFalse(RUNNER._looks_like_repo_file(note))

    def test_real_data_files_are_paths(self):
        for path in (
            "benchmarks/research_trajectory/resources/growth_observations.csv",
            "benchmarks/research_trajectory/resources/partial_bloch_observations.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(RUNNER._looks_like_repo_file(path))


class ContextTests(unittest.TestCase):
    def test_a_note_is_passed_through_as_text(self):
        note = "Optional GR_python package, resolved through ASTRA_GR_PYTHON_ROOT"
        context = RUNNER._frozen_resource_context(Program([note]))
        self.assertIn("AVAILABLE ENVIRONMENT", context)
        self.assertIn(note, context)

    def test_a_data_file_is_embedded_with_its_hash(self):
        rel = "benchmarks/research_trajectory/resources/growth_observations.csv"
        context = RUNNER._frozen_resource_context(Program([rel]))
        self.assertIn("SHA256:", context)
        self.assertIn(rel, context)
        head = (ROOT / rel).read_text(encoding="utf-8").splitlines()[0]
        self.assertIn(head, context)

    def test_a_missing_data_file_still_fails_loudly(self):
        """A mistyped path must not quietly degrade into a prose note."""
        with self.assertRaises(FileNotFoundError):
            RUNNER._frozen_resource_context(
                Program(["benchmarks/research_trajectory/resources/nope.csv"])
            )

    def test_escaping_the_repo_is_still_refused(self):
        with self.assertRaises(ValueError):
            RUNNER._frozen_resource_context(Program(["../../etc/passwd.csv"]))

    def test_every_frozen_case_can_build_its_context(self):
        """The regression that mattered: all six cases, not just the two easy ones."""
        from core.research_programs import load_research_programs

        programs = load_research_programs()
        self.assertEqual(len(programs), 6)
        for program in programs:
            with self.subTest(case=program.id):
                RUNNER._frozen_resource_context(program)


if __name__ == "__main__":
    unittest.main()
