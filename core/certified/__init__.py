"""Certified ball arithmetic for validators (``# ASTRA_CERTIFIED: arb``).

Motivation (Kondo, 6 and 9 October 2026): two cycles on a complex-branch
asymptotic stopped at review, because the validator had to certify logarithm
branches and a remainder bound uniform in a cone with floats, and the reviewer
rightly would not accept it (it also caught a missing ln 2 in log(u-2) that
would have produced a false refutation). Writing certified numerics from
scratch inside every validator is where those cycles died.

So the validator author gets a vetted helper instead: ``arb_prelude.py``
(python-flint, tested in tests/test_certified_arb.py). A Python validator asks
for it with a line ``# ASTRA_CERTIFIED: arb``. ``expand_certified`` writes the
prelude as plain text first and then runs the validator, unchanged, compiled
under the name ``validator.py``: tracebacks cite the validator's own lines, a
``from __future__`` import at its top stays valid, and the same text runs
locally and on ASTRUM without redeploying the worker. Reviewer and analyst
read the validator, not the prelude; the result records the prelude version
and hash.

Why plain text: the first version carried the prelude as one base64 ``exec``
line. On a workstation the antivirus deleted that script from workspace/
the moment Python launched it (the launcher failed with "Unable to
create process", the file was gone), while plain text ran. A pattern that
looks like obfuscated malware has no place on a collaborator's machine.

Guards: the marker only works on the Python engine (Sage has its own
ComplexBallField); a validator may not define or assign the helper names,
because the reviewer trusts them as vetted.

``# ASTRA_CERTIFIED: verdict`` (9 October 2026) loads only the pure-Python
leg/decide helper (verdict_prelude.py): decisive legs decide, corroborative
legs can never print FAIL. ``arb`` always includes it.
"""
from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

MARKER = re.compile(r"^#[ \t]*ASTRA_CERTIFIED:[ \t]*(arb|verdict)[ \t]*$", re.I | re.M)
_ANY_MARKER = re.compile(r"^[ \t]*#[ \t]*ASTRA_CERTIFIED:[ \t]*(\S*)", re.I | re.M)
_TAIL = re.compile(r"^\s*ANALYTIC_TAIL\s*:\s*(.+?)\s*$", re.M)
_DECISION = re.compile(r"^DECISION:\s*(PASS|FAIL|UNDECIDED|CORROBORATION_MISMATCH)\b", re.M)
_HERE = Path(__file__).parent

# `verdict` is the pure-Python leg/decide helper (verdict_prelude.py, 9 October
# 2026); `arb` adds the python-flint ball arithmetic and always includes it.
KINDS = {
    "verdict": ("verdict_prelude.py",),
    "arb": ("verdict_prelude.py", "arb_prelude.py"),
}

# The names the reviewer may trust as vetted; a validator must not rebind them.
VERDICT_API = ("leg", "run_leg", "decide", "ASTRA_VERDICT_VERSION")
PRELUDE_API = VERDICT_API + (
    "Undecided", "set_precision", "ball", "cball", "upper_float", "abs_upper_float",
    "is_certainly_lt", "is_certainly_le", "is_certainly_gt", "is_certainly_ge",
    "is_certainly_nonzero", "certify", "unique_integer", "branch_index", "polar_box",
    "sector_boxes", "sup_abs_on_sector", "certify_sup_abs_le", "analytic_tail",
    "ASTRA_CERTIFIED_VERSION",
)


def prelude_source(kind: str = "arb") -> str:
    return "\n\n".join(
        (_HERE / name).read_text(encoding="utf-8").rstrip("\n") for name in KINDS[kind]
    ) + "\n"


def prelude_info(kind: str = "arb") -> dict:
    source = prelude_source(kind)
    versions = re.findall(r'^ASTRA_(?:CERTIFIED|VERDICT)_VERSION = "([^"]+)"', source, re.M)
    return {
        "kind": kind,
        "version": "+".join(versions) or "unknown",
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
    }


def decision_from_stdout(stdout: str) -> str:
    """The verdict helper's DECISION (PASS/FAIL/UNDECIDED/
    CORROBORATION_MISMATCH), or "" when the validator did not use it."""
    found = _DECISION.findall(str(stdout or ""))
    return found[-1] if found else ""


def requested(code: str) -> bool:
    return bool(_ANY_MARKER.search(code or ""))


def shadowed_names(code: str) -> list:
    """Helper names the validator defines, assigns, imports as, or deletes."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []  # the interpreter reports the syntax error itself
    api, found = set(PRELUDE_API), []

    def note(name):
        if name in api and name not in found:
            found.append(name)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            note(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            note(node.id)
        elif isinstance(node, ast.alias):
            note(node.asname or node.name.split(".")[0])
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                note(name)
    return found


VALIDATOR_FILENAME = "validator.py"


def _wrap(code: str, kind: str) -> str:
    name = repr(VALIDATOR_FILENAME)
    return "\n".join([
        prelude_source(kind).rstrip("\n"),
        "",
        "",
        f"# ---- the validator, unchanged; tracebacks cite {VALIDATOR_FILENAME} lines ----",
        "import linecache as _astra_linecache",
        "import sys as _astra_sys",
        "import traceback as _astra_traceback",
        # The C-level hook of CPython <= 3.12 reads source from disk and would
        # print validator.py lines without their text; this one uses linecache.
        "_astra_sys.excepthook = _astra_traceback.print_exception",
        f"_astra_validator = {code!r}",
        f"_astra_linecache.cache[{name}] = (len(_astra_validator), None, "
        f"_astra_validator.splitlines(True), {name})",
        f'exec(compile(_astra_validator, {name}, "exec"))',
        "",
    ])


def expand_certified(code: str, engine: str) -> tuple:
    """(code_to_run, info, error). ``error`` is a message when the request
    cannot be honored; then nothing must run. Without a marker the code is
    returned unchanged and info is None."""
    if not requested(code):
        return code, None, None
    kinds = {m.group(1).lower() for m in _ANY_MARKER.finditer(code)}
    unknown = kinds - set(KINDS)
    if unknown:
        return code, None, (
            "ASTRA_CERTIFIED: unknown kind " + ", ".join(sorted(unknown) or ["''"])
            + "; use `# ASTRA_CERTIFIED: verdict` (leg/decide) or "
            "`# ASTRA_CERTIFIED: arb` (ball arithmetic plus leg/decide)."
        )
    kind = "arb" if "arb" in kinds else "verdict"
    if engine != "python":
        return code, None, (
            f"ASTRA_CERTIFIED: {kind} runs on the Python engine only (this validator "
            f"routes to {engine}). In Sage use ComplexBallField/RealBallField directly."
        )
    if not MARKER.search(code):
        return code, None, "ASTRA_CERTIFIED: the marker must be a top-level line."
    clash = shadowed_names(code)
    if clash:
        return code, None, (
            "ASTRA_CERTIFIED: the validator rebinds vetted helper name(s) "
            + ", ".join(clash)
            + "; call the prelude's functions instead of redefining them."
        )
    return _wrap(code, kind), prelude_info(kind), None


def parse_analytic_tails(stdout: str) -> list:
    """The ANALYTIC_TAIL lemmas a validator declared, in order, once each."""
    seen = []
    for item in _TAIL.findall(str(stdout or "")):
        text = re.sub(r"\s+", " ", item).strip()
        if text and text not in seen:
            seen.append(text)
    return seen
