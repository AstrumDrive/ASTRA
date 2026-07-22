# Controlling ASTRA from an agent

ASTRA includes a Model Context Protocol (MCP) server. A compatible client such
as Codex or Claude Code can use ASTRA as an execution and validation layer while
the agent plans the investigation and writes the test code.

## Exposed tools

| Tool | Purpose |
|---|---|
| `astra_execute` | Run a self-contained validation script locally, remotely, or in automatic mode. |
| `astra_cycle` | Run the complete conjecture → translation → execution → analysis pipeline. |
| `astra_probe` | Inspect the current phase and heartbeat without interrupting a cycle. |
| `astra_submit` | Start a long detached computation. |
| `astra_job` | List or poll detached jobs and retrieve incremental output. |
| `astra_status` | Check whether the configured remote worker is reachable. |

Every validation script should print its evidence and end with either
`VERDICT: PASS` or `VERDICT: FAIL`.

## Install the MCP environment

Create the main ASTRA environment first. Then create a separate MCP environment:

```powershell
python -m venv mcp_server\venv
.\mcp_server\venv\Scripts\python -m pip install mcp
```

The server locates the ASTRA repository relative to `mcp_server/server.py`.
If the main environment is elsewhere, set `ASTRA_CORE_PYTHON` to its Python
executable before starting the server.

## Register with Codex

From the repository root:

```powershell
$mcpPython = (Resolve-Path .\mcp_server\venv\Scripts\python.exe).Path
$server = (Resolve-Path .\mcp_server\server.py).Path
codex mcp add astra -- $mcpPython $server
codex mcp get astra
```

Open a new Codex task after registration so the tools are loaded.

## Example requests

- “Use `astra_status` to check the remote oracle.”
- “Write three independent SymPy checks of this identity and run them with `astra_execute`.”
- “Use `astra_cycle` to test whether this metric violates the NEC.”
- “Submit this parameter sweep with `astra_submit` and poll it with `astra_job`.”

## Extending the oracle

A Python script may import any package installed in the selected environment.
This supports public packages and project-specific libraries such as
`GR_python`, `pyWarpFactory`, or `warp_bubble_optimization`.

Lean 4 is selected with:

```lean
# ASTRA_ENGINE: lean
import Mathlib
```

Lean and Mathlib must be installed natively or in WSL. Kernel acceptance checks
the formal statement; it does not establish that the formalization is an
adequate physical model.

For Mathematica, run
[`mathematica-agent-bridge`](https://github.com/xys004/mathematica-agent-bridge)
beside ASTRA. An agent can use the bridge to evaluate Wolfram Language, operate
on notebooks, compare expressions, and independently cross-check ASTRA output.

## Security

Both ASTRA and the Mathematica bridge execute generated code. Run them only in
trusted environments, keep credentials outside the repository, and review code
before granting access to sensitive data or machines.
