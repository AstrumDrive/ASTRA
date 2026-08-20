"""
ASTRA MCP server — expone ASTRA como herramientas para CUALQUIER agente
(Claude Code, Codex, Gemini CLI, Claude Desktop) via Model Context Protocol.

Corre en Python 3.12 (el SDK de MCP necesita >=3.10). Habla con el core de ASTRA
(venv 3.9) por subprocess a traves de astra_tool.py -> versiones desacopladas.

La idea: tu agente favorito se vuelve tu enlace a ASTRA. El agente RAZONA
(conjetura, navega) y llama a estas tools para VERIFICAR con computo real en
ASTRUM (tu RTX 3080) o local.
"""
import json
import os
import signal
import subprocess
import sys
import time

from mcp.server.fastmcp import FastMCP

# --- Paths to the ASTRA core (portable; no user-specific locations) ---
ASTRA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_default_core_python = os.path.join(
    ASTRA_ROOT,
    "venv",
    "Scripts" if os.name == "nt" else "bin",
    "python.exe" if os.name == "nt" else "python",
)
ASTRA_PY = os.environ.get("ASTRA_CORE_PYTHON", _default_core_python)
if not os.path.exists(ASTRA_PY):
    ASTRA_PY = sys.executable
ASTRA_TOOL = os.path.join(ASTRA_ROOT, "astra_tool.py")

# The development line runs beside production in the same clients, so it must
# not introduce itself with production's name: a client listing two servers
# both called "astra" gives the operator no way to tell which one answered.
# The name says "development" rather than "version 2" on purpose - promotion
# is still blocked at G6, and once it lands this checkout BECOMES astra and
# the dev entry disappears, instead of leaving a stale version number behind.
# ASTRA_MCP_SERVER_NAME overrides it for exactly that promotion.
MCP_SERVER_NAME = os.environ.get("ASTRA_MCP_SERVER_NAME") or (
    "astra_dev" if os.path.basename(ASTRA_ROOT).endswith("2.0") else "astra"
)
mcp = FastMCP(MCP_SERVER_NAME)


def _kill_tree(pid: int) -> None:
    """Terminate the ASTRA subprocess tree on Windows, macOS, or Linux."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=15,
            )
        else:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        pass


def _read_child_progress(pid: int):
    """Autopsia post-timeout: astra_tool escribe hitos de fase en
    workspace/progress/cycle_<pid>.json; si el kill llego antes del API_ERROR,
    ese archivo dice en QUE FASE estaba el ciclo y cuanto llevaba cada una."""
    try:
        p = os.path.join(ASTRA_ROOT, "workspace", "progress", f"cycle_{pid}.json")
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        d["age_s"] = round(max(0.0, time.time() - d.get("ts", 0)), 1)
        return d
    except Exception:
        return None


def _call_astra(req: dict, timeout: int = 300) -> dict:
    """Invoca astra_tool.py (venv 3.9) con una peticion JSON y parsea la respuesta.
    Usa Popen (no run) para conocer el PID del hijo: si hay timeout, se lee su
    archivo de progreso y el error reporta la fase donde murio el ciclo."""
    proc = subprocess.Popen(
        [ASTRA_PY, ASTRA_TOOL],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", cwd=ASTRA_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        start_new_session=os.name != "nt",
    )
    try:
        out, err = proc.communicate(input=json.dumps(req), timeout=timeout)
    except subprocess.TimeoutExpired:
        pid = proc.pid
        # Kill the full tree so timed-out model children cannot keep consuming
        # quota after the MCP caller has already returned.
        _kill_tree(pid)
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
        res = {"error": f"astra_tool timeout tras {timeout}s (proceso matado)"}
        prog = _read_child_progress(pid)
        if prog:
            res["last_progress"] = prog   # fase culpable + timings parciales
            res["hint"] = (f"el ciclo murio en la fase '{prog.get('stage')}' "
                           f"(hace {prog.get('age_s')}s); sube el timeout de la tool "
                           "o revisa esa fase")
        return res
    if proc.returncode != 0:
        return {"error": f"astra_tool exit {proc.returncode}", "stderr": (err or "")[-600:]}
    lines = [l for l in (out or "").strip().splitlines() if l.strip()]
    if not lines:
        return {"error": "astra_tool no devolvio salida", "stderr": (err or "")[-600:]}
    try:
        return json.loads(lines[-1])   # ultima linea = objeto JSON
    except Exception as e:
        return {"error": f"parseo JSON fallo: {e}", "raw": (out or "")[-600:]}


@mcp.tool()
def astra_execute(code: str, oracle: str = "local", timeout: int = 180) -> str:
    """
    Run a verification script through ASTRA's oracle and return real results.

    Use this to VERIFY a physics/math hypothesis with actual computation instead
    of trusting an LLM's judgment. Write a self-contained script (sympy, einsteinpy,
    z3, scipy, numpy, qutip, pint, in-house packages, or a Sage/Maxima/Cadabra/
    Lean script with an '# ASTRA_ENGINE: ...' marker) that prints its evidence and ends with a line
    'VERDICT: PASS' or 'VERDICT: FAIL'.

    Args:
        code: the full script to execute.
        oracle: where to run it — 'local' (this machine, default),
                'astrum' (remote GPU, opt-in), or 'auto' (the model may tag the code with
                '# ASTRA_ORACLE: remote|local'; otherwise a heuristic sends
                GPU/heavy compute to ASTRUM and light symbolic work to local).
        timeout: seconds before giving up (default 180).

    Returns a JSON string with: stdout, stderr, exit_code, verdict (PASS/FAIL/NONE),
    oracle_used, engine.
    """
    res = _call_astra(
        {"action": "execute", "code": code, "oracle": oracle, "timeout": timeout},
        timeout=timeout + 60,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_client_validate(
    case_id: str = "",
    oracle: str = "auto",
    timeout: int = 300,
) -> str:
    """
    Run ASTRA's minimum application-facing assurance package.

    The validator router sends formal invariants to pinned Lean 4, constraints
    to Z3, symbolic formulas to SymPy, numerical models to SciPy, dimensional
    checks to Pint, and project cases to their scientific package. Every result
    includes an explicit claim verdict, artifact hash, assumptions, limitations,
    structured evidence, provenance and a reproduction command.

    Args:
        case_id: one case ID, a comma-separated list, or empty for all six cases.
        oracle: 'auto', 'local', 'astrum', or 'both'. Unsupported combinations
                are skipped rather than silently rerouted.
        timeout: per-evidence-bundle execution limit in seconds.
    """
    res = _call_astra(
        {
            "action": "client_validate",
            "case_id": case_id,
            "oracle": oracle,
            "timeout": timeout,
        },
        timeout=min(1740, max(600, timeout * 6 + 60)),
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_cycle(intuition: str, oracle: str = "local", timeout: int = 1500,
                exec_timeout: int = 0, objective: str = "") -> str:
    """
    Run ASTRA's FULL deliberative multi-model pipeline and return a verdict.

    Codex and agy propose and cross-critique hypotheses against a shared final
    objective; Codex synthesizes the consensus. Claude writes the falsifiable
    validation program, Codex independently reviews it, the selected oracle
    executes it, Codex audits the evidence, and agy proposes the next direction.
    Use astra_execute when YOU wrote the code and only need the oracle.

    Slower than astra_execute. Compact cycles may finish in several minutes;
    adversarial scientific audits commonly require 15-30 minutes.

    Args:
        intuition: the current hypothesis or research direction (LaTeX/plain text ok).
        objective: optional overarching scientific goal shared by all three
            models. When empty, intuition is also used as the final objective.
        oracle: 'local' (default), 'astrum' (opt-in, remote GPU), or 'auto'.
        timeout: seconds for the synchronous WHOLE cycle (default 1500; the
            client wall is tool_timeout_sec=1800 in Codex). ASTRA reserves time
            to return a PARTIAL result and checkpoint instead of being killed.
            For complex audits use astra_cycle_submit, then poll astra_job.
        exec_timeout: seconds for the EXECUTION phase only (0 = .env default,
            usually 180). Raise it for legitimately heavy computation (sweeps,
            GPU runs on ASTRUM) and keep timeout > exec_timeout + 400.

    Returns JSON with separate layers: `status`/`atomic_status` for the bounded
    conjecture, `oracle_verdict` for executable PASS/FAIL, `goal_coverage` for
    the shared objective, and `scientific_status` (`VALIDATED` only for complete
    coverage, otherwise `ATOMIC_VALIDATED`/`ATOMIC_REFUTED`). It also includes
    shared_goal, deliberation, conjecture, code_review, code, execution,
    analysis, navigation, providers, timings, and 'warnings'/'cli_models' when a
    CLI model hit its usage limit and a fallback served the phase. Internal
    calls use phase-specific caps and are additionally clamped to the remaining
    global budget. Checkpoints preserve completed work.
    """
    req = {
        "action": "cycle",
        "intuition": intuition,
        "oracle": oracle,
        "cycle_timeout_seconds": int(timeout),
        "cycle_return_buffer_seconds": 60,
    }
    if objective.strip():
        req["objective"] = objective.strip()
    if exec_timeout and exec_timeout > 0:
        req["exec_timeout"] = int(exec_timeout)
    res = _call_astra(req, timeout=timeout)
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_cycle_submit(
    intuition: str,
    oracle: str = "local",
    max_seconds: int = 7200,
    exec_timeout: int = 0,
    objective: str = "",
) -> str:
    """
    Queue a FULL ASTRA deliberative cycle as a persistent background job.

    This is the production route for complex scientific audits. It is not bound
    by the synchronous MCP wall, checkpoints every completed phase, waits for
    the single shared model-account slot, and survives the calling task. Poll
    the returned job_id with astra_job.

    A completed job (`status=done`) is operationally finished. Its scientific
    result must be read from `scientific_status` together with `goal_coverage`;
    an atomic oracle PASS does not certify a broader paper or research program.

    Args:
        intuition: current hypothesis or research direction.
        objective: optional shared final scientific objective.
        oracle: 'local', 'astrum', or 'auto'.
        max_seconds: hard ceiling including queue time; default 7200 (2 hours).
        exec_timeout: execution-phase ceiling; 0 uses ASTRA's configured default.
    """
    req = {
        "action": "cycle_submit",
        "intuition": intuition,
        "oracle": oracle,
        "max_seconds": int(max_seconds),
    }
    if objective.strip():
        req["objective"] = objective.strip()
    if exec_timeout and exec_timeout > 0:
        req["exec_timeout"] = int(exec_timeout)
    res = _call_astra(req, timeout=60)
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_submit(code: str, oracle: str = "local", max_seconds: int = 86400) -> str:
    """
    Submit a LONG computation as a DETACHED background job; returns immediately.

    Use this instead of astra_execute when the run may exceed ~10 minutes (the
    MCP client's synchronous wall): large parameter sweeps, GPU runs on ASTRUM,
    dense scans. The job survives this session and even a client restart — poll
    it with astra_job(job_id). Make the script print progress lines and end with
    'VERDICT: PASS' or 'VERDICT: FAIL'.

    Args:
        code: full script (same conventions as astra_execute).
        oracle: 'local' (default), 'astrum' (remote GPU — keep this machine
                awake: the runner holds the SSH), or 'auto'.
        max_seconds: hard kill ceiling for the job (default 86400 = 24 h).

    Returns JSON: job_id, runner_pid, oracle, max_seconds.
    """
    res = _call_astra({"action": "submit", "code": code, "oracle": oracle,
                       "max_seconds": max_seconds}, timeout=60)
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_job(job_id: str = "") -> str:
    """
    Poll an async job started with astra_submit or astra_cycle_submit.

    Returns status (queued/running/done/failed/killed), heartbeat age, elapsed
    seconds, a LIVE stdout tail (local python jobs stream their output), and the
    final result (verdict, exit_code, duration_s) once finished. Empty job_id
    lists the 10 most recent jobs. Poll every 1-5 min on long runs; a running
    job with a fresh heartbeat is healthy even if stdout is quiet.
    """
    res = _call_astra({"action": "job", "job_id": job_id}, timeout=60)
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_capacity() -> str:
    """
    Report local CPU/thread capacity and ASTRA's safe parallelism policy.

    ASTRA detects process-visible logical CPUs, estimates physical cores,
    respects CPU affinity and reports recommended local workers. Independent
    local validators/benchmarks may use those workers; complete deliberative
    cycles remain serialized because they share model subscriptions.
    """
    res = _call_astra({"action": "capacity"}, timeout=60)
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_cluster_submit(
    code: str,
    project: str = "",
    priority: int = 0,
    cpu_slots: int = 0,
    gpu_slots: int = 0,
    memory_mb: int = 0,
    max_seconds: int = 3600,
) -> str:
    """Queue persistent scientific computation on the shared ASTRUM node.

    Unlike a direct remote oracle call, this job is admitted by ASTRUM's central
    CPU/GPU scheduler, is attributed to ASTRA_CLIENT_ID, and continues if the
    laptop, agent, SSH session, or local MCP server disconnects. Poll the
    returned job_id with astra_cluster_job.

    Args:
        code: self-contained validation/calculation script. ASTRA_ENGINE markers
            route Sage, Maxima, Cadabra, Lean, sci, and company-package jobs.
        project: optional project/audit label; ASTRA_PROJECT_ID is the default.
        priority: -10..10. Keep 0 for normal work; use positive values only for
            genuinely interactive or urgent validation.
        cpu_slots: requested logical CPU slots; 0 selects an engine-aware default.
        gpu_slots: requested GPU slots; 0 auto-detects common CUDA/JAX/CuPy use.
        memory_mb: advisory memory reservation; 0 leaves it unspecified.
        max_seconds: execution timeout after the job starts.
    """
    res = _call_astra(
        {
            "action": "cluster_submit",
            "code": code,
            "project": project,
            "priority": int(priority),
            "cpu_slots": int(cpu_slots),
            "gpu_slots": int(gpu_slots),
            "memory_mb": int(memory_mb),
            "max_seconds": int(max_seconds),
        },
        timeout=60,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_cluster_job(
    job_id: str = "",
    client_filter: str = "",
    limit: int = 20,
) -> str:
    """Poll one shared ASTRUM job or list the central multi-client queue.

    Empty job_id lists recent jobs from Nelson, Gabriel, and any future clients.
    Set client_filter to one ASTRA_CLIENT_ID to narrow the list. Completed jobs
    include their result, evidence tails, resource claims, attribution, events,
    and artifact directory.
    """
    res = _call_astra(
        {
            "action": "cluster_job",
            "job_id": job_id,
            "client_filter": client_filter,
            "limit": int(limit),
        },
        timeout=60,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_cluster_cancel(job_id: str) -> str:
    """Cancel a queued/running ASTRUM job and record who requested it."""
    res = _call_astra(
        {"action": "cluster_cancel", "job_id": job_id},
        timeout=60,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_cluster_capacity() -> str:
    """Report ASTRUM's shared CPU/GPU slots, usage, queue depth, and reserve."""
    res = _call_astra({"action": "cluster_capacity"}, timeout=60)
    return json.dumps(res, indent=2, ensure_ascii=False)


def _pid_alive(pid) -> bool:
    if os.name != "nt":
        try:
            os.kill(int(pid), 0)
            return True
        except (OSError, TypeError, ValueError):
            return False
    try:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED_INFO
        if h:
            ctypes.windll.kernel32.CloseHandle(h)
            return True
    except Exception:
        pass
    return False


@mcp.tool()
def astra_probe() -> str:
    """
    PROBE — see what ASTRA is doing RIGHT NOW without disturbing it.

    Reads the per-phase heartbeat files every cycle writes (workspace/progress/)
    plus process liveness. Use it whenever a cycle seems slow BEFORE assuming a
    hang: most model phases take 30-240s, while translation/repair may take up
    to its larger configured cap. Zero cost, instant, safe to poll every ~60s.

    Returns JSON: in_flight (pid, stage, seconds since last heartbeat, partial
    timings), recent (finished/killed cycles with final stage), and a hint.
    """
    import glob
    now = time.time()
    in_flight, recent = [], []
    for f in sorted(glob.glob(os.path.join(ASTRA_ROOT, "workspace", "progress", "cycle_*.json")),
                    key=os.path.getmtime, reverse=True)[:12]:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        d["age_s"] = round(max(0.0, now - d.get("ts", 0)), 1)
        d["alive"] = _pid_alive(d.get("pid", -1))
        if d.get("stage") in ("done", "failed") or not d["alive"]:
            recent.append(d)
        else:
            in_flight.append(d)
    if in_flight:
        top = in_flight[0]
        hint = (f"ASTRA esta TRABAJANDO: fase '{top.get('stage')}' (heartbeat hace "
                f"{top.get('age_s')}s). Traduccion/reparacion puede usar un presupuesto "
                "mayor que otras fases. Sondea de nuevo en ~60s antes de asumir cuelgue.")
    elif recent:
        hint = (f"No hay ciclos en vuelo. El ultimo termino en stage '{recent[0].get('stage')}'"
                + ("" if recent[0].get("stage") in ("done", "failed")
                   else " (proceso muerto: probable kill por timeout externo)"))
    else:
        hint = "Sin rastros de ciclos (directorio de progreso vacio)."
    return json.dumps({"in_flight": in_flight, "recent": recent[:5], "hint": hint},
                      indent=2, ensure_ascii=False)


@mcp.tool()
def astra_status() -> str:
    """
    Health check for ASTRA: confirms whether ASTRUM (the remote GPU workstation)
    is reachable right now and reports its hostname. Call this before a heavy run.
    """
    res = _call_astra(
        {"action": "execute",
         "code": "import platform; print('HOST', platform.node()); print('VERDICT: PASS')",
         "oracle": "astrum", "timeout": 30},
        timeout=60,
    )
    return json.dumps({
        "astrum_reachable": res.get("verdict") == "PASS",
        "astrum_host": (res.get("stdout") or "").replace("VERDICT: PASS", "").strip(),
        "raw": res,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def astra_engines() -> str:
    """
    List ASTRUM's authoritative scientific-engine registry.

    Use this instead of PATH discovery. It reports the managed oracle, sci,
    SageMath, Cadabra, Maxima, Lean, and company-package (`pkgs`) environments.
    """
    res = _call_astra({"action": "engines"}, timeout=60)
    return json.dumps(res, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# ASTRA 2.0 campaign tools — DEVELOPMENT LINE ONLY.
#
# `ASTRA2_ACCEPTANCE.md` forbids exposing these through the PRODUCTION MCP
# before promotion. They are registered only when this server runs from the
# 2.0 checkout, which is the same condition that renames the server itself,
# so a promoted checkout stops advertising them until that decision is taken
# deliberately. ASTRA_CAMPAIGN_TOOLS=0 disables them regardless.
# ---------------------------------------------------------------------------

def _campaign_tools_enabled() -> bool:
    flag = (os.environ.get("ASTRA_CAMPAIGN_TOOLS") or "").strip().strip("'\"")
    if flag:
        return flag.lower() in {"1", "true", "on", "yes"}
    return MCP_SERVER_NAME != "astra"


def _campaign_api():
    sys.path.insert(0, ASTRA_ROOT) if ASTRA_ROOT not in sys.path else None
    from core import campaign_api

    return campaign_api


def _campaign_result(payload) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


if _campaign_tools_enabled():

    @mcp.tool()
    def astra_campaign_start(
        objective: str,
        success_definition: str,
        deliverables: list[str],
        budget_cycles: int = 6,
        budget_model_calls: int = 72,
        budget_wall_seconds: int = 21600,
        budget_execution_seconds: int = 3600,
        allowed_evidence_classes: list[str] | None = None,
        initial_portfolio: dict | None = None,
    ) -> str:
        """
        Start a long-horizon ASTRA 2.0 research campaign (development line).

        A campaign is an append-only ledger of branches, episodes, claims,
        evidence and deterministic decisions, unlike `astra_cycle`, which runs
        exactly one bounded cycle. Nothing runs yet: this only creates the
        campaign and, when an initial portfolio is supplied, selects the first
        branch. Drive it with `astra_campaign_step`.

        Budgets are hard ceilings, enforced fail-closed and accounted per
        dimension. `deliverables` are the mandatory outcomes; the campaign
        cannot be declared complete while any remains unresolved.
        """
        api = _campaign_api()
        try:
            result = api.astra_campaign_start(
                objective=objective,
                success_definition=success_definition,
                deliverables=list(deliverables),
                allowed_evidence_classes=list(
                    allowed_evidence_classes
                    or ["SYMBOLIC", "NUMERICAL", "COUNTEREXAMPLE", "FORMAL"]
                ),
                budget={
                    "cycles": int(budget_cycles),
                    "model_calls": int(budget_model_calls),
                    "wall_seconds": int(budget_wall_seconds),
                    "execution_seconds": int(budget_execution_seconds),
                    "human_interventions": 1,
                    "remote_jobs": 0,
                },
                initial_portfolio=initial_portfolio,
            )
        except Exception as exc:
            return _campaign_result({"error": f"{type(exc).__name__}: {exc}"})
        return _campaign_result(result)

    @mcp.tool()
    def astra_campaign_status(campaign_id: str) -> str:
        """
        Read-only state of a campaign: recommended next action, active branch,
        unresolved deliverables, budget spent and remaining, and the last
        decision. Takes no writer lock, so it is safe while a step is running.
        """
        api = _campaign_api()
        try:
            return _campaign_result(api.astra_campaign_status(campaign_id))
        except Exception as exc:
            return _campaign_result({"error": f"{type(exc).__name__}: {exc}"})

    @mcp.tool()
    def astra_campaign_step(campaign_id: str) -> str:
        """
        Run ONE campaign step: a full atomic cycle on the active branch, then
        the deterministic decision that follows from its evidence.

        This spends real model quota, roughly one `astra_cycle`. It records an
        episode with its five separate status axes, evidence with hashed
        artifacts, any materially different alternatives the synthesis
        proposed, and the decision, then checkpoints. Returns what happened
        and the campaign status afterwards.
        """
        api = _campaign_api()
        try:
            import asyncio

            result = asyncio.run(api.astra_campaign_step(campaign_id))
        except Exception as exc:
            return _campaign_result({"error": f"{type(exc).__name__}: {exc}"})
        return _campaign_result(result)

    @mcp.tool()
    def astra_campaign_stop(
        campaign_id: str, mode: str = "pause", reason: str = ""
    ) -> str:
        """
        Stop a campaign: `pause` keeps it resumable, `cancel` is terminal and
        cannot be undone. Prefer `pause` unless the objective is abandoned.
        """
        api = _campaign_api()
        try:
            return _campaign_result(
                api.astra_campaign_stop(
                    campaign_id, mode=mode, reason=reason or None
                )
            )
        except Exception as exc:
            return _campaign_result({"error": f"{type(exc).__name__}: {exc}"})

    @mcp.tool()
    def astra_campaign_reactivate(campaign_id: str) -> str:
        """Return a PAUSED campaign to ACTIVE after a human review."""
        api = _campaign_api()
        try:
            return _campaign_result(api.astra_campaign_reactivate(campaign_id))
        except Exception as exc:
            return _campaign_result({"error": f"{type(exc).__name__}: {exc}"})

    @mcp.tool()
    def astra_campaign_list() -> str:
        """List every campaign in this checkout with its status and progress."""
        api = _campaign_api()
        try:
            return _campaign_result(api.astra_campaign_list())
        except Exception as exc:
            return _campaign_result({"error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    # Banner/title go to stderr and the window title only - never stdout, which
    # carries the stdio JSON-RPC transport.
    try:
        from core.astra_identity import banner
        banner("MCP server")
    except Exception:
        pass
    mcp.run()  # transporte stdio (lo que usan los CLIs de agentes)
