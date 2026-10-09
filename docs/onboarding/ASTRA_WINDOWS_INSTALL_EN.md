# ASTRA + ASTRUM on a collaborator's Windows 11 workstation

This guide installs ASTRA on a collaborator's own Windows 11 PC so that every
ASTRA call, every ASTRUM job and every model CLI runs **on that PC**, under an
SSH key that identifies the collaborator. It is the Windows counterpart of
[`ASTRA_MACOS_INSTALL_EN.md`](ASTRA_MACOS_INSTALL_EN.md).

Why this matters: a Claude session can only reach ASTRA through a computer
that has ASTRA installed and is registered as a *local device* of the account
in use. If a collaborator uses the shared company account without installing
ASTRA, their session silently runs ASTRA on **someone else's** registered PC,
with that person's SSH identity and file access. Installing ASTRA locally is
what keeps each researcher on their own machine and their own identity.

No API keys, CLI login tokens, Tailscale state or SSH private keys are shared.

## 1. Supported layout

| Layer | Runs on the collaborator's PC | Runs on ASTRUM |
|---|---:|---:|
| Claude Desktop / Claude Code / Codex as MCP client, ASTRA MCP server | Yes | No |
| Codex, Claude Code and `agy` subscription CLIs | Yes | No |
| Python, SymPy, Z3, NumPy/SciPy, mpmath, Pint, QuTiP | Yes | Yes |
| SageMath, Maxima, Cadabra, Lean 4 + Mathlib, Wolfram | No | Authoritative |
| GPU and scientific job queue (`astra_cluster_*`) | No | Yes |

## 2. Prerequisites

Install from the official distributions, not from the Microsoft Store:

- **Python 3.12** (python.org, "Add to PATH" checked). Store Python runs in a
  sandbox that hides parts of `AppData` and breaks the MCP registration.
- **Git for Windows.**
- **Node.js LTS** (for the model CLIs).
- **Tailscale**, signed in to the company tailnet. The PC must show up in the
  tailnet; the administrator confirms it with `tailscale status` on ASTRUM.
- **Windows OpenSSH client** (built in: `C:\Windows\System32\OpenSSH\ssh.exe`).
- **Claude Desktop** (the app, not only the browser), signed in with the
  account that will use ASTRA.

Install the model CLIs:

```powershell
npm install -g @anthropic-ai/claude-code
npm install -g @openai/codex
```

and the Antigravity `agy` CLI from its official installer. Then sign in to each
one interactively with the credentials assigned to you (the company
subscription for company work):

```powershell
claude
codex login
agy
```

Do not paste those tokens into `.env`. ASTRA uses the CLIs' own credential
stores; several accounts per CLI can be kept with
[`../CLI_ACCOUNT_PROFILES.md`](../CLI_ACCOUNT_PROFILES.md).

## 3. Clone and install ASTRA

```powershell
mkdir C:\Dev -Force
cd C:\Dev
git clone https://github.com/AstrumDrive/ASTRA.git
cd ASTRA
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\install.ps1
```

The installer creates `venv\` with Python 3.12, installs
`requirements-workstation.txt` (including the MCP SDK) and creates the desktop
shortcut. It is idempotent and preserves `.env`.

## 4. Give this PC individual ASTRUM access

Create a dedicated key. Replace `yourname` with your first name in lowercase;
it becomes your identity in the ASTRUM job queue.

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\astra_astrum_ed25519 -C "astra-yourname"
Get-Content $env:USERPROFILE\.ssh\astra_astrum_ed25519.pub
```

Send **only** the `.pub` line to the ASTRUM administrator, out of band (not
through a Claude chat). The administrator authorizes it for **your own ASTRUM
account** (your first name in lowercase) and tells you the host.

Your ASTRUM account reaches only the shared job manager: it has no shell and
no file transfer, and everything you submit or cancel is recorded under that
account. The administrator account `astrum` is not for daily work.

Create or edit `C:\Users\<you>\.ssh\config`:

```sshconfig
Host astrum
    HostName YOUR_TAILSCALE_HOST
    User yourname
    IdentityFile ~/.ssh/astra_astrum_ed25519
    IdentitiesOnly yes
    ProxyCommand tailscale nc %h %p
    ConnectTimeout 20
    ServerAliveInterval 30
```

`tailscale` must be on `PATH` (the Tailscale installer adds it). Test the route
with the Windows OpenSSH client:

```powershell
C:\Windows\System32\OpenSSH\ssh.exe astrum info
```

You should see a short JSON with the ASTRUM `host`, your `client_id`,
`"authenticated": true` and the engine list (`oracle`, `sci`, `sage`, ...).
Any other command, or a plain `ssh astrum`, answers with an error that says the
account only reaches the job manager; that is expected. Never replace the alias
with the raw IP, another key or a hand-written proxy.

Edit `.env` (copy it from `.env.example` on first install) and set the remote
block. `ASTRA_REMOTE_SCHEDULER=1` is required: it is the only route your ASTRUM
account accepts. Your identity comes from your ASTRUM account; put your name in
`ASTRA_CLIENT_ID` anyway, for local logs:

```dotenv
ASTRA_ORACLE_MODE=local
ASTRA_REMOTE_HOST=astrum
ASTRA_REMOTE_SSH_BIN=C:\Windows\System32\OpenSSH\ssh.exe
ASTRA_REMOTE_SSH_OPTIONS=
ASTRA_REMOTE_PYTHON=~/astra-worker/venv/bin/python
ASTRA_REMOTE_WORKER=~/astra-worker/astra_remote_worker.py
ASTRA_REMOTE_WORKDIR=~/astra-worker/workspace
ASTRA_REMOTE_CONNECT_TIMEOUT=15
ASTRA_CLIENT_ID=yourname
ASTRA_PROJECT_ID=general
ASTRA_REMOTE_SCHEDULER=1
ASTRA_REMOTE_CLUSTER_MANAGER=~/astra-worker/astra_cluster_manager.py
ASTRA_REMOTE_QUEUE_WAIT=300
```

`ASTRA_REMOTE_SSH_BIN` matters: Git's bundled `ssh` does not read the same
configuration as the Windows OpenSSH client.

## 5. Verify the installation

These checks do not call the language models:

```powershell
.\venv\Scripts\python.exe scripts\astra_doctor.py --remote
.\venv\Scripts\python.exe -m pytest -q
```

The doctor checks the binaries, the production architecture and the ASTRUM
route; it cannot prove that each subscription has remaining quota.

## 6. Register ASTRA in your MCP client

All registrations use absolute paths to **your** clone.

### Claude Desktop (the app)

Settings → Developer → *Edit Config*. This opens the right
`claude_desktop_config.json` even for the packaged (MSIX) install, whose real
file lives under
`%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\`. Add:

```json
{
  "mcpServers": {
    "astra": {
      "command": "C:\\Dev\\ASTRA\\venv\\Scripts\\python.exe",
      "args": ["C:\\Dev\\ASTRA\\mcp_server\\server.py"]
    }
  }
}
```

Restart the app. The `astra` tools appear under the connectors as
*Desktop · Local dev*, bound to **this** PC. The same ASTRA is then available in
claude.ai in the browser when you pick this PC as the local device.

### Claude Code

```powershell
claude mcp add -s user astra -- "C:\Dev\ASTRA\venv\Scripts\python.exe" "C:\Dev\ASTRA\mcp_server\server.py"
```

In the `env` block of `~\.claude\settings.json` set `MCP_TIMEOUT` to `60000`
and `MCP_TOOL_TIMEOUT` to at least `1800000`; a deliberative cycle can run 10 to
25 minutes.

### Codex

```powershell
codex mcp add astra -- "C:\Dev\ASTRA\venv\Scripts\python.exe" "C:\Dev\ASTRA\mcp_server\server.py"
```

and in `~\.codex\config.toml`:

```toml
[mcp_servers.astra]
startup_timeout_sec = 120
tool_timeout_sec = 1800
```

## 7. First end-to-end test, and what the administrator sees

From the MCP client, in this order:

1. `astra_status` — must return the ASTRUM hostname.
2. `astra_cluster_capacity` — must return the shared slot counts.
3. `astra_cluster_submit` with a trivial script (`print("hello")`, engine
   `python`, timeout 30).

On ASTRUM the job is recorded with your ASTRUM account as `client_id` and your
Tailscale IP (administrator view):

```bash
python3 - <<'EOF'
import sqlite3
c = sqlite3.connect("/home/astrum/astra-worker/cluster/state.db")
print(c.execute("select job_id, client_id, source_ip, status from jobs order by created_ts desc limit 3").fetchall())
EOF
```

If the job shows another person's `client_id` or IP, your session is not
running ASTRA on your PC: check that Claude Desktop lists *your* computer under
Settings → Account → *Local devices* and that `.ssh\config` has `User yourname`.

## 8. Shared-queue etiquette

- `astra_cluster_cancel` cancels only your own jobs; the administrator can
  cancel any job. To free a slot held by someone else, ask them.
- Each person has quotas (by default 16 CPU slots and 1 GPU running, 20 jobs
  queued). A job above your running quota waits while other people's jobs
  start; `astra_cluster_capacity` shows `per_client_running` and the quotas.
- Declare memory for heavy jobs; a zero memory request is "unspecified".
- For MPI codes such as Quantum ESPRESSO, pass `threads_per_process=1` to
  `astra_cluster_submit`. Otherwise every MPI rank opens one BLAS/OpenMP thread
  per reserved slot: 12 ranks on 12 slots become 144 threads, and the run is
  slower for everyone.
- Anything longer than one or two minutes belongs on ASTRUM, not on the PC.

## 9. Updating safely

```powershell
cd C:\Dev\ASTRA
git pull --ff-only
.\install.ps1
.\venv\Scripts\python.exe scripts\astra_doctor.py --remote
```

Restart the MCP client afterwards so it picks up the new server code.

---

## Administrator checklist (ASTRUM side)

Done once per collaborator by the ASTRUM administrator, logged in as `astrum`.
Accounts, the gate and the per-user key files are installed by
`remote/setup_astra_queue_access.sh`; see
[`../ASTRUM_ACCESO_POR_USUARIO.md`](../ASTRUM_ACCESO_POR_USUARIO.md). New
collaborators must first be added to `QUEUE_USERS` in that script.

```bash
# 1. Confirm the collaborator's PC is on the tailnet.
tailscale status | grep -i windows

# 2. Save the .pub line they sent you, then authorize it (plan first, then apply).
cd ~/astra-worker/queue-access
sudo bash setup_astra_queue_access.sh --add-key yourname ~/yourname.pub
sudo bash setup_astra_queue_access.sh --add-key yourname ~/yourname.pub --apply
```

Tell the collaborator, out of band: `HostName` = ASTRUM's Tailscale IP, `User`
= their ASTRUM account. After their first test job, confirm in `state.db` that
it carries their account as `client_id` and their IP (section 7). Never add a
collaborator's key for the `astrum` account.
