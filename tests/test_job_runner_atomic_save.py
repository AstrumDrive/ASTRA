"""A reader holding job.json open must not kill a job runner (Windows).

On 2026-10-02 astra_cycle_job_runner died on ``PermissionError: [WinError 5]``
from the bare ``os.replace`` in its heartbeat ``_save``: a ``grep`` poll had
job.json open at that instant.  astra_job then reported the job as ``killed``
with a frozen heartbeat, and the nested cycle's VALIDATED result, printed to
stdout.log, never reached job.json.

These tests reproduce the collision by making ``os.replace`` raise
PermissionError on the first renames onto job.json, and check that:

* core.atomic_write retries the rename with a 50-200 ms backoff and publishes
  the state;
* exhausted retries raise from ``write_json_atomic`` but not from the
  best-effort writer, which logs to stderr, returns False and leaves the
  previous job.json intact;
* the ``_save`` of each of the three job runners survives a lost write and
  publishes on the next one;
* ``astra_cycle_job_runner.main``, driving a stand-in for the nested
  astra_tool cycle, still writes the final result to job.json after its first
  state write was lost entirely.

If the final save itself exhausts its retries, job.json stays at 'running'
and the finished state survives only in job.json.tmp.  The reader side,
``astra_tool._job_summary`` (astra_job), then reports that newer state once
the runner is dead, and never opens the .tmp while the runner lives.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import textwrap

import pytest

import astra_campaign_step_job_runner
import astra_cycle_job_runner
import astra_job_runner
import astra_tool
from core import atomic_write

REAL_REPLACE = os.replace


class FlakyReplace:
    """Stand-in for os.replace that denies the first ``failures`` renames onto job.json."""

    def __init__(self, failures: int, target_name: str = "job.json"):
        self.failures = failures
        self.target_name = target_name
        self.denied = 0
        self.calls = 0

    def __call__(self, source, target):
        if os.path.basename(os.fspath(target)) == self.target_name:
            self.calls += 1
            if self.denied < self.failures:
                self.denied += 1
                raise PermissionError(13, "Access is denied", os.fspath(target))
        return REAL_REPLACE(source, target)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_backoff_stays_between_50_and_200_ms():
    delays = [
        atomic_write.backoff_delay(attempt)
        for attempt in range(atomic_write.DEFAULT_ATTEMPTS - 1)
    ]
    assert delays[:3] == [0.05, 0.1, 0.2]
    assert all(0.05 <= delay <= 0.2 for delay in delays)
    # The worst case must fit well inside one 5 s heartbeat period.
    assert sum(delays) < 2.0


def test_transient_denials_are_retried_until_the_state_is_published(
    tmp_path, monkeypatch
):
    target = tmp_path / "job.json"
    target.write_text(json.dumps({"status": "queued"}), encoding="utf-8")
    flaky = FlakyReplace(failures=3)
    monkeypatch.setattr(os, "replace", flaky)
    slept = []

    atomic_write.write_json_atomic(target, {"status": "running"}, sleep=slept.append)

    assert _read(target) == {"status": "running"}
    assert (flaky.denied, flaky.calls) == (3, 4)
    assert slept == [0.05, 0.1, 0.2]
    assert not (tmp_path / "job.json.tmp").exists()


def test_exhausted_retries_raise_but_the_best_effort_writer_only_logs(
    tmp_path, monkeypatch, capsys
):
    target = tmp_path / "job.json"
    target.write_text(json.dumps({"status": "running"}), encoding="utf-8")
    flaky = FlakyReplace(failures=10**6)
    monkeypatch.setattr(os, "replace", flaky)

    with pytest.raises(PermissionError):
        atomic_write.write_json_atomic(target, {"status": "done"}, sleep=lambda _: None)
    assert flaky.calls == atomic_write.DEFAULT_ATTEMPTS

    written = atomic_write.save_json_best_effort(
        target, {"status": "done"}, label="job heartbeat", sleep=lambda _: None
    )

    assert written is False
    assert _read(target) == {"status": "running"}  # readers keep the last good state
    assert _read(tmp_path / "job.json.tmp") == {"status": "done"}
    err = capsys.readouterr().err
    assert "job heartbeat" in err and "not written" in err and "PermissionError" in err


def test_other_os_errors_are_not_retried(tmp_path, monkeypatch):
    calls = []

    def broken_replace(source, target):
        calls.append(target)
        raise FileNotFoundError(2, "No such file", os.fspath(source))

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(FileNotFoundError):
        atomic_write.replace_with_retry(tmp_path / "a", tmp_path / "b", sleep=lambda _: None)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "runner",
    [astra_cycle_job_runner, astra_job_runner, astra_campaign_step_job_runner],
    ids=["cycle", "job", "campaign_step"],
)
def test_each_runner_save_survives_a_lost_heartbeat(runner, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(atomic_write, "backoff_delay", lambda attempt: 0.0)
    job_json = tmp_path / "job.json"
    job_json.write_text(json.dumps({"id": "j", "status": "queued"}), encoding="utf-8")
    flaky = FlakyReplace(failures=atomic_write.DEFAULT_ATTEMPTS)
    monkeypatch.setattr(os, "replace", flaky)
    # astra_job_runner takes the job directory as str, the other two as Path.
    jobdir = str(tmp_path) if runner is astra_job_runner else tmp_path
    meta = {"id": "j", "status": "running"}

    assert runner._save(meta, jobdir) is False  # every attempt denied: logged, not raised
    assert _read(job_json)["status"] == "queued"

    meta.update(status="done", exit_code=0)
    assert runner._save(meta, jobdir, final=True) is True

    published = _read(job_json)
    assert published["status"] == "done" and published["exit_code"] == 0
    assert published["ts"] == meta["ts"]
    assert flaky.denied == atomic_write.DEFAULT_ATTEMPTS
    assert "not written" in capsys.readouterr().err


FAKE_NESTED_CYCLE = textwrap.dedent(
    """
    import json, sys, time
    request = json.loads(sys.stdin.read())
    time.sleep(0.5)
    print("phase chatter that is not JSON")
    print(json.dumps({
        "status": "VALIDATED",
        "original_claim_verdict": "SUPPORTED",
        "action_seen": request.get("action"),
    }))
    """
)


def test_cycle_runner_writes_the_final_result_after_lost_heartbeats(
    tmp_path, monkeypatch, capsys
):
    fake_tool = tmp_path / "fake_astra_tool.py"
    fake_tool.write_text(FAKE_NESTED_CYCLE, encoding="utf-8")
    jobdir = tmp_path / "cycle_test_0001"
    jobdir.mkdir()
    (jobdir / "job.json").write_text(
        json.dumps({
            "id": jobdir.name,
            "kind": "deliberative_cycle",
            "status": "queued",
            "max_seconds": 300,
        }),
        encoding="utf-8",
    )
    (jobdir / "request.json").write_text(
        json.dumps({"intuition": "stand-in cycle"}), encoding="utf-8"
    )
    monkeypatch.setattr(astra_cycle_job_runner, "ASTRA_TOOL", fake_tool)
    monkeypatch.setattr(astra_cycle_job_runner, "HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(atomic_write, "backoff_delay", lambda attempt: 0.001)
    # The 'running' write loses all its attempts, the first heartbeat loses two
    # more: the collision of 2026-10-02 and then some.
    flaky = FlakyReplace(failures=atomic_write.DEFAULT_ATTEMPTS + 2)
    monkeypatch.setattr(os, "replace", flaky)

    return_code = astra_cycle_job_runner.main(str(jobdir))

    assert return_code == 0
    assert flaky.denied == atomic_write.DEFAULT_ATTEMPTS + 2
    meta = _read(jobdir / "job.json")
    assert meta["status"] == "done"
    assert meta["exit_code"] == 0
    assert meta["scientific_status"] == "VALIDATED"
    assert meta["operational_error"] is False
    result = _read(jobdir / "result.json")
    assert result["original_claim_verdict"] == "SUPPORTED"
    assert result["action_seen"] == "cycle"
    assert not (jobdir / "job.json.tmp").exists()
    assert "not written" in capsys.readouterr().err


# -- reader side: astra_tool._job_summary ----------------------------------


def _write_job(jobdir: Path, published: dict, staged=None) -> None:
    (jobdir / "job.json").write_text(json.dumps(published), encoding="utf-8")
    if staged is not None:
        text = staged if isinstance(staged, str) else json.dumps(staged)
        (jobdir / "job.json.tmp").write_text(text, encoding="utf-8")


RUNNING = {"id": "c", "status": "running", "pid": 4242, "started_ts": 50.0, "ts": 100.0}
FINISHED = {
    "id": "c",
    "status": "done",
    "pid": 4242,
    "ts": 200.0,
    "duration_s": 30.0,
    "exit_code": 0,
    "scientific_status": "VALIDATED",
}


def test_job_summary_reports_the_unpublished_final_state_of_a_dead_runner(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(astra_tool, "_pid_alive_win", lambda pid: False)
    _write_job(tmp_path, RUNNING, FINISHED)

    summary = astra_tool._job_summary(str(tmp_path))

    assert summary["status"] == "done"
    assert summary["scientific_status"] == "VALIDATED"
    assert summary["state_source"] == "job.json.tmp"
    assert summary["elapsed_s"] == 30.0


@pytest.mark.parametrize(
    "staged",
    [
        dict(FINISHED, ts=100.0),  # not newer than job.json
        dict(FINISHED, ts=90.0),   # older
        dict(FINISHED, ts="?"),    # unreadable heartbeat
        '{"status": "do',          # write cut short
        "[1, 2]",                  # not a job record
    ],
    ids=["same_ts", "older", "bad_ts", "truncated", "not_a_dict"],
)
def test_job_summary_ignores_a_tmp_that_is_not_a_newer_state(staged, tmp_path, monkeypatch):
    monkeypatch.setattr(astra_tool, "_pid_alive_win", lambda pid: False)
    _write_job(tmp_path, RUNNING, staged)

    summary = astra_tool._job_summary(str(tmp_path))

    assert summary["status"] == "killed"
    assert "state_source" not in summary


def test_job_summary_never_opens_the_tmp_while_the_runner_lives(tmp_path, monkeypatch):
    monkeypatch.setattr(astra_tool, "_pid_alive_win", lambda pid: True)
    opened = []
    real_read = astra_tool._read_job_state

    def spy(path):
        opened.append(os.path.basename(path))
        return real_read(path)

    monkeypatch.setattr(astra_tool, "_read_job_state", spy)
    _write_job(tmp_path, RUNNING, FINISHED)

    summary = astra_tool._job_summary(str(tmp_path))

    assert summary["status"] == "running" and summary["alive"] is True
    assert opened == ["job.json"]


class DenyFinalState:
    """Stand-in for os.replace that denies every rename of a finished state onto job.json."""

    def __init__(self):
        self.denied = 0

    def __call__(self, source, target):
        if os.path.basename(os.fspath(target)) == "job.json":
            with open(source, encoding="utf-8") as stream:
                status = json.load(stream).get("status")
            if status in ("done", "failed"):
                self.denied += 1
                raise PermissionError(13, "Access is denied", os.fspath(target))
        return REAL_REPLACE(source, target)


def test_astra_job_reports_a_finished_cycle_whose_final_save_was_lost(
    tmp_path, monkeypatch
):
    fake_tool = tmp_path / "fake_astra_tool.py"
    fake_tool.write_text(FAKE_NESTED_CYCLE, encoding="utf-8")
    jobdir = tmp_path / "cycle_test_0002"
    jobdir.mkdir()
    _write_job(jobdir, {"id": jobdir.name, "kind": "deliberative_cycle",
                        "status": "queued", "max_seconds": 300})
    (jobdir / "request.json").write_text(json.dumps({"intuition": "x"}), encoding="utf-8")
    monkeypatch.setattr(astra_cycle_job_runner, "ASTRA_TOOL", fake_tool)
    monkeypatch.setattr(astra_cycle_job_runner, "HEARTBEAT_SECONDS", 0.05)
    monkeypatch.setattr(atomic_write, "backoff_delay", lambda attempt: 0.001)
    deny = DenyFinalState()
    monkeypatch.setattr(os, "replace", deny)

    assert astra_cycle_job_runner.main(str(jobdir)) == 0
    monkeypatch.setattr(os, "replace", REAL_REPLACE)

    assert deny.denied == atomic_write.FINAL_ATTEMPTS
    assert _read(jobdir / "job.json")["status"] == "running"  # the lost save
    # The runner ran in-process, so its recorded pid is this live test process;
    # in production it is the detached runner, dead by now.
    monkeypatch.setattr(astra_tool, "_pid_alive_win", lambda pid: False)
    summary = astra_tool._job_summary(str(jobdir))
    assert summary["status"] == "done"
    assert summary["scientific_status"] == "VALIDATED"
    assert summary["state_source"] == "job.json.tmp"
