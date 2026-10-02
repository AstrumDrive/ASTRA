"""Make it obvious, at a glance, that a running process is ASTRA - and which line.

A multi-agent research engine spawns a lot of activity (Python, subscription CLIs,
WSL) that can look anonymous in a terminal or in Task Manager. This module lets
ASTRA announce itself: a one-time banner on stderr and a live console-window title,
both stamped with the version (1.0 vs 2.0), the action, and the PID. If you see
this, it is ASTRA; if activity is happening WITHOUT it, that is worth a second
look.

The version is inferred from the checkout this file lives in: the 2.0 line is
recognised by its ASTRA2_ACCEPTANCE.md gate file or its ASTRA-2.0 directory name,
and every other checkout of this repository is production (1.0), whatever the
clone was named. ASTRA_VERSION overrides the inference.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BANNER_PRINTED = False


def astra_version() -> str:
    override = os.environ.get("ASTRA_VERSION", "").strip()
    if override:
        return override
    here = Path(__file__).resolve()
    # The 2.0 line carries its acceptance gate at the checkout root; the
    # directory name is kept as a second signal for checkouts that predate it.
    if (here.parents[1] / "ASTRA2_ACCEPTANCE.md").is_file():
        return "2.0"
    if any(p == "ASTRA-2.0" for p in here.parts):
        return "2.0"
    # A production clone may live under any directory name (a collaborator's
    # ~/Dev/astra, a CI checkout); its version is the VERSION file at the
    # checkout root (semantic versioning, see CHANGELOG.md). A clone that
    # predates that file is the original 1.0.
    try:
        text = (here.parents[1] / "VERSION").read_text(encoding="utf-8").strip()
        if text:
            return text.splitlines()[0].strip()
    except Exception:
        pass
    return "1.0"


def checkout_root() -> str:
    # core/astra_identity.py -> the checkout directory two levels up.
    return str(Path(__file__).resolve().parents[1])


def astra_line() -> str:
    """'production' for the 1.0 line, 'development' for 2.0."""
    return "development" if astra_version().startswith("2") else "production"


_REVISION: str | None = None


def checkout_revision() -> str:
    """Short commit hash and date of the checkout, e.g. '3be95bb 2026-10-02'.

    Read from the .git files first (no subprocess, works under a sandbox),
    then `git log` for the date, then 'unknown' (a zip install). Cached per
    process. Requested 2026-10-02: the cycle window said only 'ASTRA 1.0' and
    Nelson could not tell which checkout, which commit or which profile ran.
    """
    global _REVISION
    if _REVISION is not None:
        return _REVISION
    root = Path(checkout_root())
    short = ""
    try:
        head = (root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref: "):
            ref = head[5:].strip()
            ref_file = root / ".git" / ref
            if ref_file.is_file():
                short = ref_file.read_text(encoding="utf-8").strip()[:7]
            else:
                packed = root / ".git" / "packed-refs"
                if packed.is_file():
                    for line in packed.read_text(encoding="utf-8").splitlines():
                        parts = line.split()
                        if len(parts) == 2 and parts[1] == ref:
                            short = parts[0][:7]
                            break
        else:
            short = head[:7]
    except Exception:
        short = ""
    stamp = short or "unknown"
    try:
        import subprocess  # local import: only for the commit date
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h %cs"], cwd=str(root),
            capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip():
            stamp = out.stdout.strip()
    except Exception:
        pass
    _REVISION = stamp
    return stamp


def identity_label() -> str:
    """One line that says which ASTRA this is: 'ASTRA 1.0 production @3be95bb 2026-10-02'."""
    return f"ASTRA {astra_version()} {astra_line()} @{checkout_revision()}"


def set_console_title(action: str = "running") -> None:
    """Name the cmd/PowerShell window so it is recognisable in the taskbar and
    Task Manager (Apps view). Best-effort; silent if unavailable."""
    title = f"{identity_label()} - {action} - PID {os.getpid()}"
    try:
        if os.name == "nt":
            import ctypes  # local import: only needed on Windows
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        else:
            # xterm-family terminals honour this OSC escape.
            sys.stderr.write(f"\033]0;{title}\a")
            sys.stderr.flush()
    except Exception:
        pass


def banner(action: str = "running", *, force: bool = False) -> None:
    """Print a distinctive one-time ASTRA banner to stderr, and set the window
    title. Called at process entry points; safe to call more than once."""
    global _BANNER_PRINTED
    set_console_title(action)
    if _BANNER_PRINTED and not force:
        return
    _BANNER_PRINTED = True
    v = astra_version()
    # ASCII only: Windows cp1252 consoles (cmd, PowerShell 5.1) mangle box-drawing
    # and other non-ASCII glyphs, and a garbled banner defeats the purpose.
    line = "=" * 62
    profile = os.environ.get("ASTRA_ARCHITECTURE_PROFILE", "").strip().strip("'\"")
    msg = (
        f"\n{line}\n"
        f"  ASTRA {v} -- scientific validation engine\n"
        f"  line   : {astra_line()}\n"
        f"  commit : {checkout_revision()}\n"
        + (f"  profile: {profile}\n" if profile else "")
        + f"  action : {action}\n"
        f"  PID    : {os.getpid()}\n"
        f"  source : {checkout_root()}\n"
        f"  NOTE   : closing this window ABORTS the ASTRA run in progress.\n"
        f"           If this appears and you did not start ASTRA, investigate.\n"
        f"{line}\n"
    )
    try:
        sys.stderr.write(msg)
        sys.stderr.flush()
    except Exception:
        pass
