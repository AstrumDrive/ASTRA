"""Job runners are launched without a console window.

Until ASTRA 1.1.3 the runners started with DETACHED_PROCESS through the venv's
python.exe, a launcher whose child is the real interpreter. A detached
launcher has no console, so its child got a new visible one: an empty Windows
Terminal window per runner, titled with the venv's python.exe. On 2026-10-02
five such windows were closed at 15:18; their runners died without a
traceback while the cycles they had started went on and finished. Runners now
start with CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP, with
CREATE_BREAKAWAY_FROM_JOB tried first:

* the three launch sites (astra_submit, astra_cycle_submit, the campaign step
  of the MCP server) pass those flags, never DETACHED_PROCESS, and keep them
  when Windows refuses the breakaway;
* on Windows, the runner of a real astra_submit job owns a console without a
  window while it runs (a helper attaches to that console and reads its
  window), and the job still completes.
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types
from unittest.mock import patch

import pytest

import astra_tool

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


class RecordingPopen:
    """Stand-in for subprocess.Popen that records creationflags and launches nothing."""

    def __init__(self, refuse_breakaway: bool = False):
        self.refuse_breakaway = refuse_breakaway
        self.flags = []

    def __call__(self, args, **kwargs):
        flags = kwargs.get("creationflags", 0)
        self.flags.append(flags)
        if self.refuse_breakaway and flags & CREATE_BREAKAWAY_FROM_JOB:
            raise OSError(5, "Access is denied")
        return types.SimpleNamespace(pid=4242)


def _load_server_module():
    class _FakeFastMCP:
        def __init__(self, *_args, **_kwargs):
            pass

        def tool(self):
            return lambda function: function

        def run(self):
            pass

    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = _FakeFastMCP
    stubs = {
        "mcp": types.ModuleType("mcp"),
        "mcp.server": types.ModuleType("mcp.server"),
        "mcp.server.fastmcp": fastmcp,
    }
    with patch.dict(sys.modules, stubs):
        return importlib.import_module("mcp_server.server")


SERVER = _load_server_module()


def _launch_astra_submit(tmp_path):
    astra_tool._do_submit({"code": "print('VERDICT: PASS')", "oracle": "local"})


def _launch_astra_cycle_submit(tmp_path):
    astra_tool._do_submit_cycle({"intuition": "stand-in"})


def _launch_campaign_step(tmp_path):
    with patch.object(SERVER, "ASTRA_ROOT", str(tmp_path)):
        SERVER._submit_campaign_step_job("campaign-test", None, 600, None)


LAUNCHERS = {
    "astra_submit": _launch_astra_submit,
    "astra_cycle_submit": _launch_astra_cycle_submit,
    "campaign_step": _launch_campaign_step,
}


def _assert_windowless(flags: int) -> None:
    assert flags & CREATE_NO_WINDOW, hex(flags)
    assert flags & CREATE_NEW_PROCESS_GROUP, hex(flags)
    assert not flags & DETACHED_PROCESS, hex(flags)


@pytest.mark.parametrize("site", sorted(LAUNCHERS))
def test_runners_start_without_a_console_window(site, tmp_path, monkeypatch):
    popen = RecordingPopen()
    monkeypatch.setattr(subprocess, "Popen", popen)

    LAUNCHERS[site](tmp_path)

    (flags,) = popen.flags
    _assert_windowless(flags)
    assert flags & CREATE_BREAKAWAY_FROM_JOB


@pytest.mark.parametrize("site", sorted(LAUNCHERS))
def test_a_refused_breakaway_keeps_the_runner_windowless(site, tmp_path, monkeypatch):
    popen = RecordingPopen(refuse_breakaway=True)
    monkeypatch.setattr(subprocess, "Popen", popen)

    LAUNCHERS[site](tmp_path)

    first, retry = popen.flags
    assert first & CREATE_BREAKAWAY_FROM_JOB
    assert not retry & CREATE_BREAKAWAY_FROM_JOB
    _assert_windowless(retry)


# Attaches to another process's console and reports its window. Runs in a
# separate process so the test session's own console is never detached.
CONSOLE_OF_PID = """
import ctypes, json, sys
k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
k32.FreeConsole()
attached = bool(k32.AttachConsole(int(sys.argv[1])))
hwnd = k32.GetConsoleWindow() if attached else 0
visible = bool(u32.IsWindowVisible(hwnd)) if hwnd else False
k32.FreeConsole()
print(json.dumps({"attached": attached, "console_hwnd": hwnd, "visible": visible}))
"""


def _job_meta(jobdir: Path) -> dict:
    try:
        return json.loads((jobdir / "job.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@pytest.mark.skipif(os.name != "nt", reason="Windows console semantics")
def test_a_real_job_runner_has_no_console_window():
    job = astra_tool._do_submit({
        "code": "import time\ntime.sleep(6)\nprint('VERDICT: PASS')\n",
        "oracle": "local",
        "max_seconds": 120,
    })
    jobdir = Path(astra_tool._jobs_root()) / job["job_id"]
    runner_pid = None
    deadline = time.time() + 30
    while time.time() < deadline and runner_pid is None:
        meta = _job_meta(jobdir)
        if meta.get("status") == "running" and meta.get("pid"):
            runner_pid = meta["pid"]
        else:
            time.sleep(0.2)
    assert runner_pid, _job_meta(jobdir)

    probe = subprocess.run(
        [sys.executable, "-c", CONSOLE_OF_PID, str(runner_pid)],
        capture_output=True, text=True, timeout=30,
        creationflags=CREATE_NO_WINDOW,
    )
    console = json.loads(probe.stdout)

    assert console["attached"], console          # the runner does own a console
    assert console["console_hwnd"] == 0, console  # ... and it has no window
    assert not console["visible"], console

    deadline = time.time() + 60
    while time.time() < deadline and _job_meta(jobdir).get("status") == "running":
        time.sleep(0.5)
    meta = _job_meta(jobdir)
    assert meta.get("status") == "done" and meta.get("verdict") == "PASS", meta
