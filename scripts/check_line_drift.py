"""Report code drift between the ASTRA 2.0 line and the production checkout.

The two lines share code lineage but not runtime, which is the right shape
while acceptance is blocked: a shared module would let a defect in the 2.0
line reach production.  The cost of that choice is manual porting, and on
2026-08-13 two fixes were found to have travelled in opposite directions and
were discovered by accident rather than on purpose - a Windows Unicode fix
that had to go up to production, and an ASTRA_CODEX_BIN fix that had to come
down into 2.0.

This script makes that visible on demand.  Every file is compared three ways:
the common base commit the 2.0 line was cloned from, the current 2.0 working
tree, and the current production working tree.  The classification is what
matters:

- ``PRODUCTION ONLY``: production changed it and 2.0 did not.  These are the
  fixes at risk of being missed, exactly like ASTRA_CODEX_BIN.
- ``BOTH CHANGED``: genuine divergence, needing a human decision rather than
  a copy.
- ``2.0 ONLY``: expected evolution of the development line.
- ``IN SYNC``: identical content on both sides.

Line endings are normalized before hashing, so a CRLF checkout does not
report every text file as drifted.  Consumes no model quota and writes
nothing.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The runtime surface both lines execute. Campaign modules, ASTRA 2.0 docs and
# benchmark fixtures are deliberately excluded: they are 2.0-only by design and
# would drown the signal.
TRACKED_PREFIXES = ("core/", "agents/", "mcp_server/")
TRACKED_FILES = ("astra_tool.py", "main.py", ".env.example")
EXCLUDED_SUBSTRINGS = ("campaign_",)


def base_commit(checkout: Path) -> str:
    """The production commit the 2.0 line was cloned from."""
    status = checkout / "ASTRA2_STATUS.json"
    if status.exists():
        try:
            data = json.loads(status.read_text(encoding="utf-8"))
            commit = str(data.get("source", {}).get("commit") or "").strip()
            if commit:
                return commit
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
    raise SystemExit(
        "Cannot determine the common base commit: pass --base explicitly."
    )


def normalized_digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


_DOCSTRING_OWNERS = (
    ast.Module,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
)


def behavior_digest(data: bytes) -> str | None:
    """Hash of the parsed code with comments and docstrings removed.

    Two files whose only difference is prose - a reworded docstring after a
    port, say - are behaviorally identical, and reporting them as drift trains
    the reader to ignore the report.  Comments never reach the AST; docstrings
    are stripped explicitly.  Returns None for anything that will not parse,
    so the caller falls back to the byte comparison.
    """
    try:
        tree = ast.parse(data.decode("utf-8"))
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, _DOCSTRING_OWNERS):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return hashlib.sha256(ast.dump(tree).encode("utf-8")).hexdigest()


def blob_at(checkout: Path, commit: str, path: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=checkout,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def tracked_paths(checkout: Path, commit: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", commit],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if not path.endswith((".py", ".example")):
            continue
        if any(token in path for token in EXCLUDED_SUBSTRINGS):
            continue
        if path.startswith(TRACKED_PREFIXES) or path in TRACKED_FILES:
            paths.append(path)
    return sorted(paths)


def working_bytes(checkout: Path, path: str) -> bytes | None:
    try:
        return (checkout / path).read_bytes()
    except OSError:
        return None


def digests(data: bytes) -> tuple[str, str | None]:
    """(byte digest, behavior digest) - the second is None when unparseable."""
    return normalized_digest(data), behavior_digest(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, default=ROOT,
                        help="the ASTRA 2.0 checkout (default: this one)")
    parser.add_argument(
        "--production",
        type=Path,
        default=Path(os.environ.get("ASTRA_PRODUCTION_ROOT", "")) or None,
        help="the production checkout (or set ASTRA_PRODUCTION_ROOT)",
    )
    parser.add_argument("--base", default=None,
                        help="common base commit (default: from ASTRA2_STATUS)")
    parser.add_argument("--all", action="store_true",
                        help="list in-sync files too")
    args = parser.parse_args(argv)

    if not args.production:
        print(
            "Pass --production <path> or set ASTRA_PRODUCTION_ROOT.",
            file=sys.stderr,
        )
        return 2
    if not (args.production / ".git").exists():
        print(f"Not a checkout: {args.production}", file=sys.stderr)
        return 2

    base = args.base or base_commit(args.dev)
    paths = tracked_paths(args.dev, base)

    buckets: dict[str, list[tuple[str, str]]] = {
        "PRODUCTION ONLY": [],
        "BOTH CHANGED": [],
        "2.0 ONLY": [],
        "PROSE ONLY": [],
        "IN SYNC": [],
        "MISSING": [],
    }
    for path in paths:
        original = blob_at(args.dev, base, path)
        if original is None:
            continue
        base_hash, base_code = digests(original)
        dev_raw = working_bytes(args.dev, path)
        prod_raw = working_bytes(args.production, path)
        if dev_raw is None or prod_raw is None:
            side = "2.0" if dev_raw is None else "production"
            buckets["MISSING"].append((path, f"absent in {side}"))
            continue
        dev_hash, dev_code = digests(dev_raw)
        prod_hash, prod_code = digests(prod_raw)
        if dev_hash == prod_hash:
            buckets["IN SYNC"].append((path, "identical"))
            continue
        if dev_code is not None and dev_code == prod_code:
            buckets["PROSE ONLY"].append(
                (path, "same behavior; comments or docstrings differ")
            )
            continue
        # Compare behavior against the base when the file parses, so a
        # reformatted-but-equivalent side is not reported as a change.
        if None in (base_code, dev_code, prod_code):
            dev_changed = dev_hash != base_hash
            prod_changed = prod_hash != base_hash
        else:
            dev_changed = dev_code != base_code
            prod_changed = prod_code != base_code
        if prod_changed and not dev_changed:
            buckets["PRODUCTION ONLY"].append(
                (path, "production moved; 2.0 still at base")
            )
        elif dev_changed and not prod_changed:
            buckets["2.0 ONLY"].append((path, "development evolution"))
        else:
            buckets["BOTH CHANGED"].append((path, "diverged on both sides"))

    print(f"base commit : {base[:12]}")
    print(f"2.0         : {args.dev}")
    print(f"production  : {args.production}")
    print(f"files compared: {len(paths)}")
    print()

    order = [
        "PRODUCTION ONLY",
        "BOTH CHANGED",
        "2.0 ONLY",
        "PROSE ONLY",
        "MISSING",
        "IN SYNC",
    ]
    for label in order:
        rows = buckets[label]
        if label == "IN SYNC" and not args.all:
            print(f"{label:16s} {len(rows):3d}  (use --all to list)")
            continue
        print(f"{label:16s} {len(rows):3d}")
        for path, note in rows:
            print(f"    {path:44s} {note}")

    attention = buckets["PRODUCTION ONLY"] + buckets["BOTH CHANGED"]
    print()
    if attention:
        print(f"NEEDS A DECISION: {len(attention)} file(s). "
              "Production-only changes are the ones a port would miss.")
    else:
        print("No production change is missing from the 2.0 line.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
