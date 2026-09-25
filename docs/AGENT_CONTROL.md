# Controlling ASTRA from an agent

ASTRA ships a Model Context Protocol (MCP) server, `mcp_server/server.py`. Any
MCP client (Codex, Claude Code, Claude Desktop, Antigravity, Gemini CLI) can use
ASTRA as its execution and validation layer: the agent plans the investigation
and writes the tests, ASTRA runs the deliberative cycle and the oracles, and the
evidence comes back to the same conversation.

The layout is identical on Windows and macOS. The installers (`install.ps1`,
`install_macos.sh`) create one `venv/` that holds the validation stack, the MCP
SDK, and pytest; the server finds the repository relative to its own file, so no
path in this document is user-specific.

| | Windows | macOS / Linux |
|---|---|---|
| Interpreter | `venv\Scripts\python.exe` | `venv/bin/python` |
| Server | `mcp_server\server.py` | `mcp_server/server.py` |

If the ASTRA core lives in a different environment, set `ASTRA_CORE_PYTHON` to
that interpreter before launching the server; the server process itself only
needs the `mcp` package.

## Exposed tools

The production server (name `astra`) registers fifteen tools in five families.

| Family | Tools | Purpose |
|---|---|---|
| Deliberation | `astra_cycle`, `astra_cycle_submit` | Conjecture, translation, review, oracle, and analysis in one pass; the `_submit` form runs detached for cycles longer than the client's tool wall. |
| Execution | `astra_execute`, `astra_client_validate` | Run an existing validation script on the local, remote, or automatic oracle; produce the minimum client-facing evidence suite. |
| Jobs | `astra_submit`, `astra_job` | Start a long detached computation and poll it with incremental output. |
| Observation | `astra_probe`, `astra_telemetry`, `astra_status`, `astra_engines`, `astra_capacity` | Phase and heartbeat of a live cycle, summary of the finished pool, worker reachability, engine inventory, free cycle slots. |
| Cluster | `astra_cluster_submit`, `astra_cluster_job`, `astra_cluster_cancel`, `astra_cluster_capacity` | Submit, poll, cancel, and size work on the ASTRUM workstation. |

A sixth family, `astra_campaign_*` (start, status, step, step_submit, stop,
reactivate, list), drives multi-cycle programmes. It is registered only when
the server is not named `astra` (the development profile) or when
`ASTRA_CAMPAIGN_TOOLS=1` is set explicitly.

Every validation script prints its evidence and ends with `VERDICT: PASS`,
`VERDICT: FAIL`, or `VERDICT: NON-DECIDABLE` followed by `MISSING:` lines and
exit code 3.

## Register the server

Run the commands from the repository root. Open a new agent session afterwards
so the tool list is loaded. `server.py` is read once at start; `.env`, `core/`,
and `astra_tool.py` are read fresh on every call, so configuration changes do
not require re-registering.

### Antigravity

The installers already write the workspace-scoped entry
`.agents/mcp_config.json`. To redo it, or to register globally:

```bash
venv/bin/python scripts/configure_antigravity_mcp.py            # workspace
venv/bin/python scripts/configure_antigravity_mcp.py --global   # ~/.gemini/config/mcp_config.json
```

On Windows use `.\venv\Scripts\python.exe` in place of `venv/bin/python`.

### Codex

```bash
codex mcp add astra -- "$PWD/venv/bin/python" "$PWD/mcp_server/server.py"
```

```powershell
codex mcp add astra -- "$PWD\venv\Scripts\python.exe" "$PWD\mcp_server\server.py"
```

A deliberative cycle can legitimately run 10 to 25 minutes. Raise the walls for
this server in `~/.codex/config.toml` and restart Codex:

```toml
[mcp_servers.astra]
startup_timeout_sec = 120
tool_timeout_sec = 1800
```

### Claude Code

```bash
claude mcp add astra -- "$PWD/venv/bin/python" "$PWD/mcp_server/server.py"
```

```powershell
claude mcp add astra -- "$PWD\venv\Scripts\python.exe" "$PWD\mcp_server\server.py"
```

The default scope registers the server for the current directory only; add
`-s user` to make it available in every project.

A cold start of the MCP SDK can exceed the default 30 s connection wall. In the
`env` block of `~/.claude/settings.json` set `MCP_TIMEOUT` (connection, ms) to
`60000` and `MCP_TOOL_TIMEOUT` (tool execution, ms) to at least `1800000`.

### Claude Desktop

Add the server to `claude_desktop_config.json`, found under `%APPDATA%\Claude\`
on Windows and `~/Library/Application Support/Claude/` on macOS, with absolute
paths:

```json
{
  "mcpServers": {
    "astra": {
      "command": "/absolute/path/to/ASTRA/venv/bin/python",
      "args": ["/absolute/path/to/ASTRA/mcp_server/server.py"]
    }
  }
}
```

The desktop app watches this file and restarts the server when it changes.

## Example requests

- "Use `astra_status` to check the remote oracle, then `astra_engines` for the
  authoritative engine inventory."
- "Write three independent SymPy checks of this identity and run them with
  `astra_execute`."
- "Use `astra_cycle_submit` to test whether this metric violates the NEC, and
  poll the job with `astra_job`."
- "Submit this parameter sweep with `astra_submit` and follow it with
  `astra_job`."

Computations longer than a few minutes belong in `astra_submit` or
`astra_cycle_submit`; poll a live cycle with `astra_probe` before deciding that
it is stuck.

## Extending the oracle

A validation script may import any package installed in `venv/`, including
project-specific libraries such as `GR_python`, `pyWarpFactory`, or
`warp_bubble_optimization` when their roots are configured in `.env`.

External engines are selected with a first-line marker:

```python
# ASTRA_ENGINE: sage      # SageMath
# ASTRA_ENGINE: maxima    # Maxima
# ASTRA_ENGINE: cadabra   # Cadabra (tensor algebra)
# ASTRA_ENGINE: lean4     # Lean 4 + Mathlib
```

On Windows these run through the Debian WSL distribution named in
`ASTRA_WSL_DISTRO`; on macOS they run natively when installed or, in the
supported collaborator layout, on ASTRUM through the remote oracle. Lean kernel
acceptance checks the formal statement; it does not establish that the
formalization is an adequate physical model.

For Wolfram Language, run
[`mathematica-agent-bridge`](https://github.com/xys004/mathematica-agent-bridge)
beside ASTRA and point `ASTRA_MATHEMATICA_BRIDGE_ROOT` at it.

## Security

ASTRA and the Mathematica bridge execute generated code. Run them only in
trusted environments, keep credentials outside the repository (`.env`, CLI
login stores, SSH keys), and review generated code before granting access to
sensitive data or machines.
