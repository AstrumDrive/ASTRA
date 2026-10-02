"""astra_job recovers a cycle's result from stdout.log when its runner died.

On 2026-10-02 five cycle runners were terminated together, with no
traceback, while their nested astra_tool cycles went on to finish VALIDATED.
astra_tool prints its result as the one JSON line of stdout.log; only the
runner copies it to result.json and job.json, so all five read as 'killed'.
The reader side now recovers that line:

* a dead runner whose cycle printed its result reads 'done', with the same
  summary fields the runner writes, ``state_source: stdout.log`` and
  ``exit_code: None`` (not observable), and astra_job returns the result;
* a dead runner whose cycle is still working reads 'running' with
  ``runner_alive: False`` instead of 'killed', until max_seconds plus a
  grace, past which a live nested pid is taken for a reused one;
* a half-written result line, or a job that is not a deliberative cycle, is
  never recovered;
* the runner's own final state in job.json.tmp wins over stdout.log;
* recovering from stdout.log after a real runner run reproduces the fields
  that run wrote to job.json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import textwrap
import time

import pytest

import astra_cycle_job_runner
import astra_tool
from core import atomic_write

RESULT = {
    "status": "VALIDATED",
    "scientific_status": "ATOMIC_VALIDATED",
    "atomic_status": "VALIDATED",
    "original_claim_verdict": "SUPPORTED",
    "oracle_verdict": "PASS",
    "goal_coverage": {"status": "partial"},
}
RUNNER_PID, NESTED_PID = 111, 222
SUMMARY_FIELDS = (
    "scientific_status",
    "atomic_status",
    "goal_coverage",
    "oracle_verdict",
    "operational_error",
)


@pytest.fixture
def jobs_root(tmp_path, monkeypatch):
    monkeypatch.setattr(astra_tool, "_jobs_root", lambda: str(tmp_path))
    return tmp_path


def _liveness(monkeypatch, *alive_pids):
    monkeypatch.setattr(
        astra_tool, "_pid_alive_win", lambda pid: int(pid) in alive_pids
    )


def _running_cycle(jobs_root: Path, *, started_ago=600.0, max_seconds=18000,
                   stdout=None, kind="deliberative_cycle") -> Path:
    now = time.time()
    meta = {
        "id": "cycle_test_recover",
        "status": "running",
        "oracle": "local",
        "max_seconds": max_seconds,
        "created_ts": now - started_ago - 3,
        "started_ts": now - started_ago,
        "ts": now - started_ago + 60,
        "pid": RUNNER_PID,
        "nested_pid": NESTED_PID,
    }
    if kind:
        meta["kind"] = kind
    jobdir = jobs_root / meta["id"]
    jobdir.mkdir()
    (jobdir / "job.json").write_text(json.dumps(meta), encoding="utf-8")
    if stdout is not None:
        (jobdir / "stdout.log").write_text(stdout, encoding="utf-8")
    return jobdir


def test_dead_runner_reads_done_with_the_result_from_stdout(jobs_root, monkeypatch):
    _liveness(monkeypatch)
    jobdir = _running_cycle(jobs_root, stdout=json.dumps(RESULT) + "\n")

    job = astra_tool._do_job({"job_id": jobdir.name})

    assert job["status"] == "done"
    assert job["state_source"] == "stdout.log"
    assert job["exit_code"] is None
    assert job["scientific_status"] == "ATOMIC_VALIDATED"
    assert job["goal_coverage"] == "partial"
    assert job["oracle_verdict"] == "PASS"
    assert job["operational_error"] is False
    started = json.loads((jobdir / "job.json").read_text(encoding="utf-8"))["started_ts"]
    assert job["duration_s"] == pytest.approx(
        os.path.getmtime(jobdir / "stdout.log") - started, abs=0.01
    )
    assert job["elapsed_s"] == job["duration_s"]
    assert job["result"] == RESULT
    # Recovery is read-only: the job directory is left as it was.
    assert json.loads((jobdir / "job.json").read_text(encoding="utf-8"))["status"] == "running"
    assert not (jobdir / "result.json").exists()


def test_the_listing_shows_the_recovered_state(jobs_root, monkeypatch):
    _liveness(monkeypatch)
    _running_cycle(jobs_root, stdout=json.dumps(RESULT) + "\n")

    (row,) = astra_tool._do_job({})["jobs"]

    assert row["status"] == "done"
    assert row["state_source"] == "stdout.log"
    assert row["scientific_status"] == "ATOMIC_VALIDATED"


def test_a_cycle_outliving_its_runner_reads_running_until_it_prints(jobs_root, monkeypatch):
    _liveness(monkeypatch, NESTED_PID)
    jobdir = _running_cycle(jobs_root, stdout="")

    working = astra_tool._job_summary(str(jobdir))

    assert working["status"] == "running"
    assert working["alive"] is True
    assert working["runner_alive"] is False
    assert "state_source" not in working

    (jobdir / "stdout.log").write_text(json.dumps(RESULT) + "\n", encoding="utf-8")
    finished = astra_tool._job_summary(str(jobdir))

    assert finished["status"] == "done"
    assert finished["state_source"] == "stdout.log"


def test_a_live_nested_pid_past_the_budget_is_a_reused_pid(jobs_root, monkeypatch):
    _liveness(monkeypatch, NESTED_PID)
    jobdir = _running_cycle(
        jobs_root, started_ago=3600 + astra_tool._ORPHAN_GRACE_S + 60,
        max_seconds=3600, stdout="",
    )

    summary = astra_tool._job_summary(str(jobdir))

    assert summary["status"] == "killed"
    assert "runner_alive" not in summary


@pytest.mark.parametrize("cycle_alive", [False, True], ids=["cycle_dead", "cycle_alive"])
def test_a_half_written_result_line_is_not_a_result(cycle_alive, jobs_root, monkeypatch):
    _liveness(monkeypatch, *([NESTED_PID] if cycle_alive else []))
    jobdir = _running_cycle(jobs_root, stdout=json.dumps(RESULT)[:-12])

    summary = astra_tool._job_summary(str(jobdir))

    assert summary["status"] == ("running" if cycle_alive else "killed")
    assert "state_source" not in summary


def test_only_deliberative_cycles_are_recovered(jobs_root, monkeypatch):
    _liveness(monkeypatch)
    jobdir = _running_cycle(jobs_root, stdout=json.dumps(RESULT) + "\n", kind=None)

    summary = astra_tool._job_summary(str(jobdir))

    assert summary["status"] == "killed"
    assert "state_source" not in summary


def test_the_runners_own_final_state_wins_over_stdout(jobs_root, monkeypatch):
    _liveness(monkeypatch)
    jobdir = _running_cycle(jobs_root, stdout=json.dumps(RESULT) + "\n")
    meta = json.loads((jobdir / "job.json").read_text(encoding="utf-8"))
    staged = dict(meta, status="done", exit_code=0, duration_s=12.5,
                  scientific_status="REFUTED", ts=meta["ts"] + 5)
    (jobdir / "job.json.tmp").write_text(json.dumps(staged), encoding="utf-8")

    summary = astra_tool._job_summary(str(jobdir))

    assert summary["state_source"] == "job.json.tmp"
    assert summary["exit_code"] == 0
    assert summary["scientific_status"] == "REFUTED"


FAKE_NESTED_CYCLE = textwrap.dedent(
    """
    import json, sys, time
    from pathlib import Path
    sys.stdin.read()
    time.sleep(0.3)
    print(Path(__file__).with_name("result_to_print.json").read_text(encoding="utf-8").strip())
    """
)


def test_recovery_reproduces_what_the_runner_writes(tmp_path, jobs_root, monkeypatch):
    fake_tool = tmp_path / "fake_astra_tool.py"
    fake_tool.write_text(FAKE_NESTED_CYCLE, encoding="utf-8")
    (tmp_path / "result_to_print.json").write_text(
        json.dumps(dict(RESULT, error=None)), encoding="utf-8"
    )
    jobdir = jobs_root / "cycle_test_parity"
    jobdir.mkdir()
    (jobdir / "job.json").write_text(json.dumps({
        "id": jobdir.name, "kind": "deliberative_cycle", "status": "queued",
        "oracle": "local", "max_seconds": 300, "created_ts": time.time(),
        "ts": time.time(),
    }), encoding="utf-8")
    (jobdir / "request.json").write_text(json.dumps({"intuition": "x"}), encoding="utf-8")
    monkeypatch.setattr(astra_cycle_job_runner, "ASTRA_TOOL", fake_tool)
    monkeypatch.setattr(astra_cycle_job_runner, "HEARTBEAT_SECONDS", 0.05)

    assert astra_cycle_job_runner.main(str(jobdir)) == 0
    written = json.loads((jobdir / "job.json").read_text(encoding="utf-8"))
    written_result = json.loads((jobdir / "result.json").read_text(encoding="utf-8"))
    assert written["status"] == "done" and written["exit_code"] == 0

    # Rewind the job to the runner's last heartbeat, as if it had died there.
    heartbeat = {k: written[k] for k in (
        "id", "kind", "oracle", "max_seconds", "created_ts", "pid",
        "nested_pid", "started_ts",
    )}
    heartbeat.update(status="running", ts=written["started_ts"] + 0.1)
    atomic_write.write_json_atomic(jobdir / "job.json", heartbeat)
    (jobdir / "result.json").unlink()
    _liveness(monkeypatch)

    recovered = astra_tool._do_job({"job_id": jobdir.name})

    assert recovered["status"] == written["status"]
    for field in SUMMARY_FIELDS:
        assert recovered[field] == written[field], field
    assert recovered["result"] == written_result
    assert recovered["exit_code"] is None and recovered["state_source"] == "stdout.log"
