from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


HOST = "127.0.0.1"
PORT = 5050
URL  = f"http://{HOST}:{PORT}"


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def open_browser(url: str) -> None:
    if os.environ.get("WSL_DISTRO_NAME"):
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass
    webbrowser.open(url)


def auto_install_requirements() -> bool:
    req_path = Path(__file__).resolve().parent / "requirements.txt"
    if not req_path.exists():
        print("[WARN] requirements.txt not found. Skipping auto-install.")
        return True

    print("\n[SETUP] Checking and installing Python dependencies...")
    print("        This may take a few minutes on first run.\n")

    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "-r", str(req_path),
            "--disable-pip-version-check",
        ]
    )

    if result.returncode != 0:
        print("\n[WARN] Some dependencies may not have installed correctly.")
        print("       You can retry manually:  pip install -r requirements.txt")
        return False

    print("\n[OK]   All Python dependencies are installed.\n")
    return True


def wait_for_server(url: str, timeout: int = 30) -> bool:
    health_url = f"{url}/api/health"
    for _ in range(timeout):
        try:
            with urllib.request.urlopen(health_url, timeout=1):
                return True
        except Exception:
            time.sleep(1)
    return False


def main() -> int:
    clear_screen()
    print("=" * 68)
    print("   ASTRA PRODUCTION WIZARD  —  Setup & Launch")
    print("=" * 68)

    # ── Step 0: Python version ──────────────────────────────────────────
    if sys.version_info < (3, 9):
        print(f"\n[FAIL] Python 3.9+ required. You have {sys.version.split()[0]}")
        print("       Download from https://python.org/downloads/")
        input("\nPress Enter to exit...")
        return 1

    print(f"\n[OK]   Python {sys.version.split()[0]}")

    # ── Step 1: Auto-install requirements ──────────────────────────────
    auto_install_requirements()

    # Safe to import ASTRA modules now that dependencies are installed
    from core.preflight import (
        print_checks,
        prompt_for_api_keys,
        prompt_for_phase_providers,
        run_preflight,
    )

    # ── Step 2: API keys ────────────────────────────────────────────────
    prompt_for_api_keys()

    # ── Step 3: Provider layout ─────────────────────────────────────────
    phase_providers = prompt_for_phase_providers()

    # ── Step 4: Preflight ───────────────────────────────────────────────
    verify_api = (
        input("\nRun a live API health check before launch? [Y/n]: ")
        .strip().lower() != "n"
    )
    checks = run_preflight(verify_api=verify_api, phase_providers=phase_providers)
    ready  = print_checks(checks)

    if not ready:
        print("\n[FAIL] Preflight found required failures.")
        print("       Fix the items marked FAIL above, then run the wizard again.")
        input("\nPress Enter to exit...")
        return 1

    # ── Step 5: Start Flask in background, wait, then open browser ──────
    print("\n[LAUNCH] Starting ASTRA Web Studio...")
    for phase, provider in phase_providers.items():
        print(f"         {phase}: {provider}")
    print(f"         URL: {URL}\n")

    server_proc = subprocess.Popen(
        [sys.executable, "web/app.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("Waiting for server to become ready ", end="", flush=True)
    ready = False
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=1):
                ready = True
                break
        except Exception:
            print(".", end="", flush=True)
            time.sleep(1)
    print()

    if ready:
        print(f"[OK]   Server ready. Opening {URL}")
    else:
        print(f"[WARN] Server slow to respond. Opening {URL} anyway.")

    open_browser(URL)

    print("\nASTRA is running. Press Ctrl+C to stop.\n")
    try:
        server_proc.wait()
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down ASTRA...")
        server_proc.terminate()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
