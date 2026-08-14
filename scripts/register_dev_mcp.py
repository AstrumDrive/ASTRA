"""Register the ASTRA 2.0 MCP server ALONGSIDE production, never replacing it.

`HANDOFF.md` §9 forbids pointing the production MCP entry at this checkout and
forbids running the repository installers from here, because they write the
key `astra` and would overwrite the daily-use route. This script exists so the
2.0 line can be reachable from the same tools **without** that risk: it writes
a separate server named `astra_dev`, leaves every other entry untouched, backs up
each file first, and verifies afterwards that the production entry is
byte-identical to what it was.

Clients handled (all machine-local, none of them committed):

- Codex          ~/.codex/config.toml
- Claude Code    ~/.claude.json
- Antigravity    ~/.gemini/config/mcp_config.json

  python scripts/register_dev_mcp.py --dry-run     # default
  python scripts/register_dev_mcp.py --apply
  python scripts/register_dev_mcp.py --remove --apply
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_NAME = "astra_dev"
PRODUCTION_NAME = "astra"

PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
if not PYTHON.is_file():  # POSIX collaborators
    PYTHON = ROOT / "venv" / "bin" / "python"
SERVER = ROOT / "mcp_server" / "server.py"

CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
CLAUDE_CONFIG = Path.home() / ".claude.json"
ANTIGRAVITY_CONFIG = Path.home() / ".gemini" / "config" / "mcp_config.json"

# Same tool surface production approves individually, so the 2.0 entry behaves
# the same way rather than silently defaulting to a different approval policy.
CODEX_TOOLS = (
    "astra_capacity",
    "astra_client_validate",
    "astra_cycle",
    "astra_cycle_submit",
    "astra_engines",
    "astra_execute",
    "astra_job",
    "astra_probe",
    "astra_status",
    "astra_submit",
)


class Refuse(SystemExit):
    pass


def backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = path.with_suffix(path.suffix + f".astradevbak-{stamp}")
    shutil.copy2(path, target)
    return target


def production_fingerprint(text: str, client: str) -> str:
    """The production entry as it appears now, to compare after writing."""
    if client == "codex":
        match = re.search(
            r"^\[mcp_servers\.astra\]\s*$.*?(?=^\[mcp_servers\.(?!astra\.)|\Z)",
            text,
            re.M | re.S,
        )
        return match.group(0) if match else ""
    data = json.loads(text) if text.strip() else {}
    return json.dumps(
        (data.get("mcpServers") or {}).get(PRODUCTION_NAME), sort_keys=True
    )


# --- JSON clients (Claude Code, Antigravity) -------------------------------


def json_plan(path: Path, remove: bool) -> tuple[str, str] | None:
    if not path.exists():
        return None
    original = path.read_text(encoding="utf-8")
    data = json.loads(original) if original.strip() else {}
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise Refuse(f"mcpServers is not an object in {path}")
    if remove:
        if SERVER_NAME not in servers:
            return None
        servers.pop(SERVER_NAME)
    else:
        entry = {
            "type": "stdio",
            "command": str(PYTHON),
            "args": [str(SERVER)],
            "env": {},
        }
        # Antigravity's own writer omits "type"/"env"; match its shape there.
        if path == ANTIGRAVITY_CONFIG:
            entry = {"command": str(PYTHON), "args": [str(SERVER)],
                     "cwd": str(ROOT)}
        if servers.get(SERVER_NAME) == entry:
            return None
        servers[SERVER_NAME] = entry
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return original, updated


# --- Codex TOML ------------------------------------------------------------


def codex_block() -> str:
    lines = [
        "",
        f"[mcp_servers.{SERVER_NAME}]",
        f"command = '{PYTHON}'",
        f"args = ['{SERVER}']",
        "startup_timeout_sec = 120.0",
        "tool_timeout_sec = 1800.0",
        "",
    ]
    for tool in CODEX_TOOLS:
        lines.append(f"[mcp_servers.{SERVER_NAME}.tools.{tool}]")
        lines.append('approval_mode = "approve"')
        lines.append("")
    return "\n".join(lines)


def codex_plan(remove: bool) -> tuple[str, str] | None:
    if not CODEX_CONFIG.exists():
        return None
    original = CODEX_CONFIG.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"\n*^\[mcp_servers\.{SERVER_NAME}\]\s*$.*?"
        rf"(?=^\[mcp_servers\.(?!{SERVER_NAME}\.)|^\[plugins|\Z)",
        re.M | re.S,
    )
    stripped = pattern.sub("\n", original)
    if remove:
        return (original, stripped) if stripped != original else None
    updated = stripped.rstrip("\n") + "\n" + codex_block()
    return (original, updated) if updated != original else None


# --- driver ----------------------------------------------------------------


CLIENTS = {
    "codex": (CODEX_CONFIG, lambda remove: codex_plan(remove)),
    "claude": (CLAUDE_CONFIG, lambda remove: json_plan(CLAUDE_CONFIG, remove)),
    "antigravity": (
        ANTIGRAVITY_CONFIG,
        lambda remove: json_plan(ANTIGRAVITY_CONFIG, remove),
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the changes (default is a dry run)")
    parser.add_argument("--remove", action="store_true",
                        help="remove the astra_dev entry instead of adding it")
    parser.add_argument("--only", default="",
                        help="comma-separated: codex,claude,antigravity")
    args = parser.parse_args(argv)

    if not args.remove:
        if not PYTHON.is_file():
            raise Refuse(f"Interpreter not found: {PYTHON}")
        if not SERVER.is_file():
            raise Refuse(f"MCP server not found: {SERVER}")

    selected = [c.strip() for c in args.only.split(",") if c.strip()] or list(
        CLIENTS
    )
    print(f"server name : {SERVER_NAME}   (production '{PRODUCTION_NAME}' is "
          "never touched)")
    print(f"interpreter : {PYTHON}")
    print(f"server      : {SERVER}")
    print(f"mode        : {'REMOVE' if args.remove else 'ADD'}"
          f"{'' if args.apply else '  (dry run)'}")
    print()

    changed = 0
    for client in selected:
        path, planner = CLIENTS[client]
        if not path.exists():
            print(f"[skip   ] {client:12s} no config at {path}")
            continue
        plan = planner(args.remove)
        if plan is None:
            print(f"[ok     ] {client:12s} already in the desired state")
            continue
        original, updated = plan
        before = production_fingerprint(original, client)
        after = production_fingerprint(updated, client)
        if before != after:
            raise Refuse(
                f"REFUSING: the production '{PRODUCTION_NAME}' entry would "
                f"change in {path}"
            )
        if not args.apply:
            delta = len(updated.splitlines()) - len(original.splitlines())
            print(f"[would  ] {client:12s} {path}  ({delta:+d} lines)")
            changed += 1
            continue
        saved = backup(path)
        path.write_text(updated, encoding="utf-8")
        # Re-read from disk: the check that matters is what ended up written.
        final = production_fingerprint(path.read_text(encoding="utf-8"), client)
        if final != before:
            shutil.copy2(saved, path)
            raise Refuse(
                f"Production entry changed after writing {path}; restored the "
                f"backup {saved}"
            )
        print(f"[written] {client:12s} {path}")
        print(f"           backup {saved}")
        changed += 1

    print()
    if not changed:
        print("Nothing to do.")
    elif not args.apply:
        print("Dry run only. Re-run with --apply to write.")
    else:
        print("Done. Restart or refresh each client to pick the server up:")
        print("  Codex        restart the CLI/app")
        print("  Claude Code  restart the app")
        print("  Antigravity  Settings > MCP Servers > Refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
