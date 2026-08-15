"""Removing harness-caused cycles must not quietly rewrite deposited evidence."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "drop_contaminated_cycles", ROOT / "scripts" / "drop_contaminated_cycles.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()
DENIED = {"result": {"status": "TOOL_ERROR", "error": "[WinError 5] Access is denied"}}
GOOD = {"result": {"status": "VALIDATED"}}
REAL_FAILURE = {"result": {"status": "PARTIAL", "error": "timeout tras 193s"}}


def record(cycles, case="gr_invariant_audit", blind="aaa"):
    return {
        "case_id": case,
        "configuration": "full",
        "seed": 11,
        "blind_id": blind,
        "state": "complete",
        "stop_reason": "max_cycles",
        "cycles": list(cycles),
    }


class PlanTests(unittest.TestCase):
    def test_a_contaminated_tail_is_truncated(self):
        keep, refused = TOOL.plan_record(record([GOOD, DENIED, DENIED]), "WinError 5")
        self.assertEqual((keep, refused), (1, []))

    def test_a_fully_contaminated_cell_keeps_nothing(self):
        keep, refused = TOOL.plan_record(record([DENIED, DENIED]), "WinError 5")
        self.assertEqual((keep, refused), (0, []))

    def test_a_clean_cell_is_untouched(self):
        keep, refused = TOOL.plan_record(record([GOOD, REAL_FAILURE]), "WinError 5")
        self.assertEqual((keep, refused), (2, []))

    def test_real_failures_are_never_swept_away(self):
        """A timeout is evidence; only harness damage may be discarded."""
        keep, _refused = TOOL.plan_record(record([REAL_FAILURE]), "WinError 5")
        self.assertEqual(keep, 1)

    def test_interleaved_contamination_is_refused_not_renumbered(self):
        keep, refused = TOOL.plan_record(record([DENIED, GOOD]), "WinError 5")
        self.assertEqual(keep, 2)
        self.assertEqual(refused, [1])


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="astra_drop_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.checkpoint = self.tmp / "checkpoint.json"
        cells = self.tmp / "cells" / "gr_invariant_audit" / "aaa"
        for index in (1, 2, 3):
            (cells / f"cycle_{index:03d}").mkdir(parents=True)
        self.cells = cells
        self.checkpoint.write_text(
            json.dumps(
                {
                    "state": "complete",
                    "records": [record([GOOD, DENIED, DENIED])],
                    "summary": {"stale": True},
                }
            ),
            encoding="utf-8",
        )

    def _run(self, *extra):
        return TOOL.main(
            ["--run", str(self.checkpoint), "--error-contains", "WinError 5", *extra]
        )

    def test_a_dry_run_changes_nothing(self):
        self._run()
        data = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(len(data["records"][0]["cycles"]), 3)
        self.assertTrue((self.cells / "cycle_003").exists())

    def test_apply_truncates_the_record_and_the_directories(self):
        self._run("--apply")
        data = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(len(data["records"][0]["cycles"]), 1)
        self.assertTrue((self.cells / "cycle_001").exists())
        self.assertFalse((self.cells / "cycle_002").exists())
        self.assertFalse((self.cells / "cycle_003").exists())

    def test_the_cell_becomes_resumable_again(self):
        self._run("--apply")
        cell = json.loads(self.checkpoint.read_text(encoding="utf-8"))["records"][0]
        self.assertNotEqual(cell["state"], "complete")
        self.assertNotIn("stop_reason", cell)

    def test_the_stale_summary_is_dropped(self):
        self._run("--apply")
        data = json.loads(self.checkpoint.read_text(encoding="utf-8"))
        self.assertEqual(data["summary"], {})


if __name__ == "__main__":
    unittest.main()
