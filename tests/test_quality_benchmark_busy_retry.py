"""The quality benchmark queues behind a busy model slot instead of failing.

ASTRA admits one full deliberative cycle per model-account set, machine-wide,
because the CLIs are subscriptions rather than per-request API keys. Any other
work on the machine makes a cycle return BUSY, and this runner had no handling
for it: it would have recorded a scheduling condition as an architectural
failure, which is how three research-trajectory runs were lost on 2026-08-15/16.
The trajectory runner gained a retry after that incident; this one did not, and
until now the gap was covered by an external launcher gate rather than by the
runner itself.
"""
import asyncio
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_quality_benchmarks", ROOT / "scripts" / "run_quality_benchmarks.py"
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
GOOD = {"status": "VALIDATED"}


def drive(replies):
    calls = {"n": 0}

    async def fake_once(_payload, *, env, timeout):
        reply = replies[min(calls["n"], len(replies) - 1)]
        calls["n"] += 1
        return dict(reply), ""

    async def no_sleep(_seconds):
        return None

    async def go():
        with patch.object(RUNNER, "_invoke_tool_once", fake_once), \
                patch.object(RUNNER.asyncio, "sleep", no_sleep):
            return await RUNNER._invoke_tool({}, env={}, timeout=10)

    result, _tail = asyncio.run(go())
    return result, calls["n"]


class BusyRetryTests(unittest.TestCase):
    def test_it_waits_instead_of_recording_a_failure(self):
        result, attempts = drive([BUSY, BUSY, GOOD])
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(attempts, 3)

    def test_a_free_slot_costs_one_call(self):
        result, attempts = drive([GOOD])
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(attempts, 1)

    def test_a_slot_that_never_frees_gives_up_and_says_how_long(self):
        result, attempts = drive([BUSY])
        self.assertEqual(result["status"], "BUSY")
        self.assertEqual(attempts, RUNNER._BUSY_MAX_ATTEMPTS + 1)
        self.assertIn("still busy after", result["error"])

    def test_a_real_failure_is_never_retried(self):
        """Only BUSY is transient; a TOOL_ERROR is the measurement."""
        result, attempts = drive([{"status": "TOOL_ERROR", "error": "boom"}])
        self.assertEqual(result["status"], "TOOL_ERROR")
        self.assertEqual(attempts, 1)

    def test_the_wait_outlasts_the_longest_measured_cycle(self):
        # Cycles reach 2400 s on the amended protocol; giving up sooner would
        # turn queuing behind one real cycle into a false failure.
        budget = RUNNER._BUSY_WAIT_SECONDS * RUNNER._BUSY_MAX_ATTEMPTS
        self.assertGreaterEqual(budget, 2400)


if __name__ == "__main__":
    unittest.main()
