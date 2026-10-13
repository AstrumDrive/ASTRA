"""Formal proof validators used by ASTRA's evidence router.

Lean 3 remains pinned separately for the miniF2F benchmark.  New client-facing
formalizations use a pinned Lean 4 + Mathlib project so benchmark compatibility
and product development cannot silently change one another's toolchains.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
LEAN4_VERSION = "4.30.0"
LEAN4_TOOLCHAIN = f"leanprover/lean4:v{LEAN4_VERSION}"
MATHLIB4_COMMIT = "c5ea00351c28e24afc9f0f84379aa41082b1188f"
_FORBIDDEN = re.compile(r"\b(?:sorry|admit|axiom)\b", re.IGNORECASE)
_ENGINE_MARKER = re.compile(r"^\s*#\s*ASTRA_ENGINE:\s*(?:lean|lean4)\s*$", re.I | re.M)


def clean_lean4_source(source: str) -> str:
    return _ENGINE_MARKER.sub("", source or "").lstrip()


# `_FORBIDDEN` is a raw text scan, so before this fix it fired on the *word*
# sorry/admit/axiom anywhere in the file -- including inside `--` line
# comments and `/- -/` (or `/-- -/` doc) block comments. `lean_nat_add_comm`
# measured this directly on 2026-08-31 (quality_20260831_125334.json,
# post-timeout-fix): a sound proof was REJECTED before Lean ever ran because
# its doc comments said "no `sorry`" and "axiom set via the standard command"
# -- prose *about* the absence of these constructs, not a use of them. Nested
# block comments are tracked with a depth counter (Lean allows `/- /- -/ -/`)
# and `"..."` string contents are passed through untouched but not scanned
# for comment delimiters, so a stray `--` or `/-` inside a string literal
# can't be used to smuggle real code past the gate by making it look like a
# comment.
def _strip_lean_comments(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    depth = 0
    in_string = False
    while i < n:
        c = source[i]
        if depth > 0:
            if source.startswith("/-", i):
                depth += 1
                i += 2
            elif source.startswith("-/", i):
                depth -= 1
                i += 2
            else:
                i += 1
            continue
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(source[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if source.startswith("/-", i):
            depth = 1
            i += 2
            continue
        if source.startswith("--", i):
            j = source.find("\n", i)
            if j == -1:
                break
            out.append("\n")
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _forbidden_tokens(source: str) -> list[str]:
    code_only = _strip_lean_comments(source)
    return sorted({match.group(0).lower() for match in _FORBIDDEN.finditer(code_only)})


# `lean <file>` elaborates the file and stops: a `def main : IO Unit` is
# type-checked but never evaluated, so a script ending in
# `IO.println "VERDICT: PASS"` compiles cleanly and prints nothing at all.
#
# That silence is what made `lean_nat_add_comm` the only deterministic
# CODE_ERROR in the quality suite -- 6 failures in 6 complete runs, while
# every other operational failure churned. ASTRA got the mathematics right
# each time: `original_claim_verdict` was SUPPORTED and the kernel accepted
# the proof, but the case asks the script to print a verdict and the runner
# never gave `main` a chance to run.
#
# Measured 2026-08-29 against the pinned Lean 4.30.0 / Mathlib project:
#
#   valid theorem + main, no --run  -> exit 0, stdout empty
#   valid theorem + main, --run     -> exit 0, stdout "VERDICT: PASS"
#   FALSE theorem + main, --run     -> exit 1, type mismatch, no PASS printed
#   valid theorem, no main, --run   -> exit 1, "unknown declaration 'main'"
#
# The third line is why this is not a loosening of the gate: Lean elaborates
# the whole file before the interpreter starts, so a proof that does not
# compile fails first and `main` never executes. The case's own stated
# failure mode -- "Printing PASS without compiling a theorem" -- stays
# impossible, and `_FORBIDDEN` still rejects `sorry`/`admit`/`axiom`
# independently.
#
# The fourth line is why this is conditional: an unconditional `--run` would
# break every artifact that proves a theorem without printing anything.
_LEAN_MAIN = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*"
    r"(?:private\s+|protected\s+|unsafe\s+|partial\s+|noncomputable\s+)*"
    r"def\s+main\b",
    re.M,
)
_LEAN_MISSING_MAIN = "unknown declaration 'main'"


def lean4_declares_main(source: str) -> bool:
    """True when the artifact defines a `main` that `--run` could evaluate."""
    return bool(_LEAN_MAIN.search(source or ""))


def lean4_argv_tail(source: str, path: str) -> list[str]:
    """`lean` arguments for `source`, evaluating `main` when one is declared."""
    if lean4_declares_main(source):
        return ["lean", "--run", path]
    return ["lean", path]


def _lean4_missing_main(stdout: str, stderr: str) -> bool:
    """True when `--run` failed only because there is no `main` to run.

    The declaration scan is a regex over source text, so it can be fooled by a
    `main` inside a comment or string, or by one nested in a namespace. When
    that happens the run is retried without `--run`, which makes this change
    incapable of turning a currently-passing artifact into a failure: the
    worst case is exactly the previous behaviour.
    """
    return _LEAN_MISSING_MAIN in (stdout or "") or _LEAN_MISSING_MAIN in (stderr or "")


def _unavailable(detail: str, oracle: str) -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "stdout": "",
        "stderr": detail,
        "exit_code": -2,
        "engine": "lean4",
        "oracle": oracle,
        "lean_version": LEAN4_VERSION,
        "mathlib_commit": MATHLIB4_COMMIT,
    }


def _is_windows() -> bool:
    return sys.platform == "win32"


def _evaluate_lean4_local_wsl(
    source: str,
    timeout: int,
    *,
    project: str,
    lake: str,
) -> dict[str, Any]:
    distro = os.environ.get("ASTRA_WSL_DISTRO", "").strip().strip("'\"")
    if not _is_windows() or shutil.which("wsl") is None:
        return _unavailable(
            "The configured WSL Lean 4 environment requires wsl.exe on Windows.",
            "local",
        )

    workspace = ROOT / "workspace" / "formal"
    workspace.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".lean",
        prefix="astra_client_",
        dir=workspace,
        encoding="utf-8",
        delete=False,
    )
    path = Path(handle.name)
    try:
        with handle:
            handle.write(source)
        from core.engine_router import _win_to_wsl_path

        argv_tail = lean4_argv_tail(source, _win_to_wsl_path(str(path)))
        command = ["wsl"]
        if distro:
            command.extend(["-d", distro])
        command.extend(["--cd", project, "--", lake, "env", *argv_tail])
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if (
            result.returncode != 0
            and "--run" in argv_tail
            and _lean4_missing_main(result.stdout, result.stderr)
        ):
            result = subprocess.run(
                [item for item in command if item != "--run"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        return {
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-8000:],
            "exit_code": result.returncode,
            "engine": "lean4",
            "oracle": "local",
            "runtime": "wsl",
            "wsl_distro": distro or "default",
            "lean_version": LEAN4_VERSION,
            "mathlib_commit": MATHLIB4_COMMIT,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "stdout": "",
            "stderr": f"Lean 4 compilation exceeded {timeout} seconds.",
            "exit_code": 124,
            "engine": "lean4",
            "oracle": "local",
            "runtime": "wsl",
            "wsl_distro": distro or "default",
            "lean_version": LEAN4_VERSION,
            "mathlib_commit": MATHLIB4_COMMIT,
        }
    finally:
        path.unlink(missing_ok=True)


def _evaluate_lean4_local(source: str, timeout: int) -> dict[str, Any]:
    wsl_project = (
        os.environ.get("ASTRA_LOCAL_LEAN4_WSL_ROOT", "")
        .strip()
        .strip("'\"")
    )
    wsl_lake = (
        os.environ.get("ASTRA_LOCAL_LEAN4_WSL_LAKE_BIN", "")
        .strip()
        .strip("'\"")
    )
    if wsl_project or wsl_lake:
        if not wsl_project or not wsl_lake:
            return _unavailable(
                "Both ASTRA_LOCAL_LEAN4_WSL_ROOT and "
                "ASTRA_LOCAL_LEAN4_WSL_LAKE_BIN are required.",
                "local",
            )
        return _evaluate_lean4_local_wsl(
            source,
            timeout,
            project=wsl_project,
            lake=wsl_lake,
        )

    project_raw = os.environ.get("ASTRA_LOCAL_LEAN4_ROOT", "").strip()
    if not project_raw:
        return _unavailable(
            "ASTRA_LOCAL_LEAN4_ROOT is not configured; use the ASTRUM oracle "
            "or point it at the pinned Mathlib 4 project.",
            "local",
        )
    project = Path(project_raw).expanduser().resolve()
    lake = os.environ.get("ASTRA_LOCAL_LAKE_BIN", "").strip() or shutil.which("lake")
    if not project.is_dir() or not lake:
        return _unavailable(
            f"Pinned Lean 4 project or lake executable is unavailable: {project}",
            "local",
        )

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".lean",
        prefix="astra_client_",
        dir=project,
        encoding="utf-8",
        delete=False,
    )
    path = Path(handle.name)
    try:
        with handle:
            handle.write(source)
        argv_tail = lean4_argv_tail(source, str(path))
        result = subprocess.run(
            [lake, "env", *argv_tail],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if (
            result.returncode != 0
            and "--run" in argv_tail
            and _lean4_missing_main(result.stdout, result.stderr)
        ):
            result = subprocess.run(
                [lake, "env", "lean", str(path)],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        return {
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-8000:],
            "exit_code": result.returncode,
            "engine": "lean4",
            "oracle": "local",
            "lean_version": LEAN4_VERSION,
            "mathlib_commit": MATHLIB4_COMMIT,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "stdout": "",
            "stderr": f"Lean 4 compilation exceeded {timeout} seconds.",
            "exit_code": 124,
            "engine": "lean4",
            "oracle": "local",
            "lean_version": LEAN4_VERSION,
            "mathlib_commit": MATHLIB4_COMMIT,
        }
    finally:
        path.unlink(missing_ok=True)


async def _evaluate_lean4_remote(source: str, timeout: int) -> dict[str, Any]:
    project = os.environ.get(
        "ASTRA_REMOTE_LEAN4_ROOT",
        "~/astra-benchmarks/mathlib4-v4.30.0",
    )
    lake_bin = os.environ.get("ASTRA_REMOTE_LAKE_BIN", "~/.elan/bin/lake")
    git_bin = os.environ.get(
        "ASTRA_REMOTE_GIT_BIN",
        "~/miniforge3/envs/astra-bench/bin/git",
    )
    source_b64 = base64.b64encode(source.encode("utf-8")).decode("ascii")
    # Decided here rather than remotely so both oracles run the identical
    # argv for the same artifact; the remote half only replays the decision.
    run_flag = ["--run"] if lean4_declares_main(source) else []
    remote_code = f"""
import base64, json, os, subprocess, tempfile
project = os.path.abspath(os.path.expanduser({project!r}))
lake_bin = os.path.abspath(os.path.expanduser({lake_bin!r}))
git_bin = os.path.abspath(os.path.expanduser({git_bin!r}))
source = base64.b64decode({source_b64!r}).decode("utf-8")
payload = {{}}
env = os.environ.copy()
env["PATH"] = (
    os.path.dirname(git_bin)
    + os.pathsep
    + os.path.dirname(lake_bin)
    + os.pathsep
    + env.get("PATH", "")
)
if not os.path.isdir(project) or not os.path.isfile(lake_bin):
    payload = {{
        "returncode": -2,
        "stderr": "Pinned Lean 4 project or lake executable is unavailable",
    }}
else:
    commit = subprocess.run(
        [git_bin, "-C", project, "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=20, env=env,
    ).stdout.strip()
    fd, path = tempfile.mkstemp(
        prefix="astra_client_", suffix=".lean", dir=project
    )
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(source)
        if commit != {MATHLIB4_COMMIT!r}:
            payload = {{
                "returncode": -3,
                "stderr": "Mathlib commit mismatch: " + commit,
                "commit": commit,
            }}
        else:
            try:
                run_flag = {run_flag!r}
                result = subprocess.run(
                    [lake_bin, "env", "lean"] + run_flag + [path],
                    cwd=project,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout={int(timeout)},
                )
                if result.returncode != 0 and run_flag and (
                    {_LEAN_MISSING_MAIN!r} in (result.stdout or "")
                    or {_LEAN_MISSING_MAIN!r} in (result.stderr or "")
                ):
                    result = subprocess.run(
                        [lake_bin, "env", "lean", path],
                        cwd=project,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout={int(timeout)},
                    )
                version = subprocess.run(
                    [lake_bin, "env", "lean", "--version"],
                    cwd=project,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                ).stdout.strip()
                payload = {{
                    "returncode": result.returncode,
                    "stdout": result.stdout[-8000:],
                    "stderr": result.stderr[-8000:],
                    "commit": commit,
                    "version": version,
                }}
            except subprocess.TimeoutExpired:
                payload = {{
                    "returncode": 124,
                    "stderr": "Lean 4 compilation exceeded {int(timeout)} seconds",
                    "commit": commit,
                }}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
print(json.dumps(payload))
"""
    from core.remote_executor import execute_remote_code

    response = await execute_remote_code(remote_code, timeout=timeout + 75)
    if int(response.get("exit_code", -1)) != 0:
        return {
            "status": "REMOTE_ERROR",
            "stdout": str(response.get("stdout") or "")[-8000:],
            "stderr": str(response.get("stderr") or "")[-8000:],
            "exit_code": int(response.get("exit_code", -1)),
            "engine": "lean4",
            "oracle": "astrum",
            "lean_version": LEAN4_VERSION,
            "mathlib_commit": MATHLIB4_COMMIT,
        }
    try:
        result = json.loads(str(response.get("stdout") or "").strip())
    except json.JSONDecodeError:
        return {
            "status": "REMOTE_ERROR",
            "stdout": str(response.get("stdout") or "")[-8000:],
            "stderr": "Remote Lean 4 evaluator returned non-JSON output.",
            "exit_code": -13,
            "engine": "lean4",
            "oracle": "astrum",
            "lean_version": LEAN4_VERSION,
            "mathlib_commit": MATHLIB4_COMMIT,
        }

    returncode = int(result.get("returncode", -1))
    status = (
        "PASS" if returncode == 0
        else "TIMEOUT" if returncode == 124
        else "UNAVAILABLE" if returncode == -2
        else "ENVIRONMENT_MISMATCH" if returncode == -3
        else "FAIL"
    )
    return {
        "status": status,
        "stdout": str(result.get("stdout") or "")[-8000:],
        "stderr": str(result.get("stderr") or "")[-8000:],
        "exit_code": returncode,
        "engine": "lean4",
        "oracle": "astrum",
        "lean_version": LEAN4_VERSION,
        "lean_version_output": result.get("version", ""),
        "lean_toolchain": LEAN4_TOOLCHAIN,
        "mathlib_commit": result.get("commit") or MATHLIB4_COMMIT,
    }


async def evaluate_lean4_source(
    source: str,
    *,
    oracle: str = "auto",
    timeout: int = 180,
) -> dict[str, Any]:
    """Compile a Lean 4 artifact without accepting proof placeholders."""
    source = clean_lean4_source(source)
    forbidden = _forbidden_tokens(source)
    if forbidden:
        return {
            "status": "REJECTED",
            "stdout": "",
            "stderr": "Forbidden formal-proof placeholders or declarations: "
            + ", ".join(forbidden),
            "exit_code": -4,
            "engine": "lean4",
            "oracle": oracle,
            "forbidden": forbidden,
            "lean_version": LEAN4_VERSION,
            "mathlib_commit": MATHLIB4_COMMIT,
        }

    normalized = oracle.strip().lower()
    if normalized == "remote":
        normalized = "astrum"
    if normalized not in {"auto", "local", "astrum"}:
        raise ValueError(f"Unsupported Lean 4 oracle: {oracle}")
    if normalized == "auto":
        local_result = _evaluate_lean4_local(source, timeout)
        if local_result.get("status") != "UNAVAILABLE":
            return local_result
        if os.environ.get("ASTRA_REMOTE_HOST", "").strip():
            return await _evaluate_lean4_remote(source, timeout)
        return local_result
    if normalized == "astrum":
        return await _evaluate_lean4_remote(source, timeout)
    return _evaluate_lean4_local(source, timeout)


async def bootstrap_remote_formal_environment(
    *,
    timeout: int = 3600,
) -> dict[str, Any]:
    """Run ASTRA's tracked no-sudo bootstrap script on ASTRUM."""
    script = (ROOT / "remote" / "bootstrap_external_benchmarks.sh").read_bytes()
    script_b64 = base64.b64encode(script).decode("ascii")
    remote_code = f"""
import base64, json, os, subprocess, tempfile
root = os.path.abspath(os.path.expanduser("~/astra-benchmarks"))
os.makedirs(root, exist_ok=True)
fd, path = tempfile.mkstemp(prefix="astra_bootstrap_", suffix=".sh", dir=root)
os.close(fd)
try:
    with open(path, "wb") as handle:
        handle.write(base64.b64decode({script_b64!r}))
    os.chmod(path, 0o700)
    try:
        result = subprocess.run(
            ["bash", path],
            capture_output=True,
            text=True,
            timeout={int(timeout)},
        )
        payload = {{
            "returncode": result.returncode,
            "stdout": result.stdout[-20000:],
            "stderr": result.stderr[-12000:],
        }}
    except subprocess.TimeoutExpired as exc:
        payload = {{
            "returncode": 124,
            "stdout": (exc.stdout or "")[-20000:]
                if isinstance(exc.stdout, str) else "",
            "stderr": "Bootstrap exceeded {int(timeout)} seconds",
        }}
finally:
    try:
        os.remove(path)
    except OSError:
        pass
print(json.dumps(payload))
"""
    from core.remote_executor import execute_remote_code

    response = await execute_remote_code(remote_code, timeout=timeout + 90)
    if int(response.get("exit_code", -1)) != 0:
        return {
            "status": "REMOTE_ERROR",
            "returncode": int(response.get("exit_code", -1)),
            "stdout": str(response.get("stdout") or "")[-20000:],
            "stderr": str(response.get("stderr") or "")[-12000:],
        }
    try:
        result = json.loads(str(response.get("stdout") or "").strip())
    except json.JSONDecodeError:
        return {
            "status": "REMOTE_ERROR",
            "returncode": -13,
            "stdout": str(response.get("stdout") or "")[-20000:],
            "stderr": "Remote bootstrap returned non-JSON output.",
        }
    return {
        "status": "READY" if result.get("returncode") == 0 else (
            "TIMEOUT" if result.get("returncode") == 124 else "FAILED"
        ),
        **result,
    }
