"""A busy model slot is a queue, not a result.

Measured 2026-08-14: a stale cycle lock made all eight cells of a full vs
full-linear ablation return BUSY in about two seconds each. The runner recorded
every one as an operational failure and finished the "run" in 45 s with
`operational_failure_rate: 1.0` for BOTH arms - a number that looks like a
finding about the architectures and is purely an artifact of scheduling.
"""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

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
BUSY = {
    "status": "BUSY",
    "error": "Another full ASTRA deliberative cycle is already using the "
             "shared model-account set.",
}
GOOD = {"status": "VALIDATED", "code": "print('VERDICT: PASS')"}


class Budget:
    execution_timeout_seconds = 60
    cycle_timeout_seconds = 600


class Program:
    resources = ()
    budget = Budget()

    def research_brief(self):
        return "objective"


def record():
    return {"configuration": "full", "seed": 11, "cycles": [],
            "case_id": "gr_invariant_audit", "objective": "objective"}


def run(replies):
    calls = {"n": 0}

    def fake_invoke(_program, _env, _request):
        reply = replies[min(calls["n"], len(replies) - 1)]
        calls["n"] += 1
        return dict(reply), ""

    with patch.object(RUNNER, "_invoke_cycle_once", fake_invoke), patch.object(
        RUNNER.time, "sleep", lambda _s: None
    ):
        result, _duration, _raw = RUNNER._run_cycle(
            program=Program(),
            record=record(),
            direction="go",
            oracle="local",
            strict_primary_models=False,
        )
    return result, calls["n"]


class BusyRetryTests(unittest.TestCase):
    def test_it_waits_instead_of_scoring_a_failure(self):
        result, attempts = run([BUSY, BUSY, GOOD])
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(attempts, 3)

    def test_a_normal_result_is_returned_on_the_first_call(self):
        result, attempts = run([GOOD])
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(attempts, 1)

    def test_a_permanently_busy_slot_still_gives_up_and_says_so(self):
        result, attempts = run([BUSY])
        self.assertEqual(result["status"], "BUSY")
        self.assertEqual(attempts, RUNNER._BUSY_MAX_ATTEMPTS + 1)
        self.assertIn("still busy after", result["error"])

    def test_a_real_failure_is_never_retried(self):
        """Only BUSY is transient; a TOOL_ERROR is the measurement."""
        result, attempts = run([{"status": "TOOL_ERROR", "error": "boom"}])
        self.assertEqual(result["status"], "TOOL_ERROR")
        self.assertEqual(attempts, 1)

    def test_the_wait_is_long_enough_to_outlast_a_real_cycle(self):
        # Cycles measured today ran 1471-2013 s; the ablation must be able to
        # queue behind one rather than scoring it as broken.
        self.assertGreaterEqual(
            RUNNER._BUSY_WAIT_SECONDS * RUNNER._BUSY_MAX_ATTEMPTS, 1200
        )


if __name__ == "__main__":
    unittest.main()
