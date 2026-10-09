"""Ask instead of stop: what a cycle says when decisive inputs are missing.

Nelson, 2026-09-09: "si faltan cosas que se necesitan, que ASTRA me pregunte,
para ver si las tengo, si le doy valores, le digo que suponga valores o los
extraiga de algun lugar; no tiene que finalizar el ciclo sin decidir como
unica salida". ASTRA has no channel to the user of its own: it answers the
calling agent. So a NON_DECIDABLE result carries an explicit ``input_request``
the agent must put to the user, with three answers and, for each, the exact
re-run request (``inputs``, ``input_policy``, ``resume_checkpoint``).

Request fields (astra_cycle / astra_cycle_submit)
-------------------------------------------------
* ``inputs``: the values or frozen contents the user supplies (free text, or
  a mapping name -> value). They reach the conjecture engine, the structurer
  and the validator author as an authoritative FROZEN INPUTS block.
* ``input_policy``: ``strict`` (default: a missing input ends the cycle as
  NON_DECIDABLE with the question) or ``assume`` (the user approved
  placeholder values: the validator declares each one in an ``ASSUMED:``
  line and proceeds; the verdict is reported as conditional on them).
* ``resume_checkpoint``: the checkpoint of the cycle that asked; its
  conjecture is reused (it was already paid for) and the new run starts at
  the validator with the inputs in hand.

Convention requests (2026-10-09)
--------------------------------
The 9 October benchmark lost two cases that were decided in all but name:
"a/b=c/b implies a=c for all real a,b,c" (the validator proved it false
under x/0:=0, true under x/0:=x and true with b != 0) and the Hagen-Poiseuille
scaling (proved under the standard assumptions, which the claim never
stated). Both ended VALIDATED with ``original_claim_verdict`` INCONCLUSIVE
and nothing the user could answer. When the analyst says the claim is
undecided ONLY because it leaves a convention, an assumption or a domain
unstated, it names the readings (``convention_request``) and the result
carries an ``input_request`` of kind ``convention``: one re-run per reading,
the reading passed as ``inputs``. ``status`` and ``original_claim_verdict``
are never changed by it; the re-run answers P under the chosen convention.
A re-run of the same case the same day took the other route: the validator
declared ``MISSING: a convention for real division at b = 0`` and the cycle
ended NON_DECIDABLE. There the readings join the missing-input question as
``convention_N`` options, so "assume" is no longer the only way to fix one.
"""
from __future__ import annotations

import json
import re

INPUT_POLICIES = ("strict", "assume")

ASSUME_POLICY_TEXT = (
    "INPUT POLICY: assume. The user approved placeholder values for the inputs "
    "this request does not contain. Do NOT declare non-decidability for them: "
    "choose explicit, physically reasonable values, print one line "
    "`ASSUMED: <input> = <value> -- <reason>` per assumption before the CHECK "
    "lines, and proceed to a PASS/FAIL verdict. The verdict is conditional on "
    "those assumptions and ASTRA reports them as such."
)

_ASSUMED = re.compile(r"^\s*ASSUMED\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_RERUN_KEYS = ("intuition", "objective", "oracle", "exec_timeout", "structure_request",
               "max_mode", "axiomatic_base")
_NONE_WORDS = {"none", "none.", "n/a", "nothing", "-"}
# A pasted table or paper must not blow the CLI prompt (agy passes it as argv,
# ~32 KB ceiling in core/cli_backend.py); the excess is cut and reported.
INPUTS_MAX_CHARS = 20000


def input_policy(req: dict) -> str:
    raw = str((req or {}).get("input_policy") or "strict").strip().strip("'\"").lower()
    return raw if raw in INPUT_POLICIES else "strict"


def inputs_text(req: dict) -> str:
    """The user's inputs as text: a mapping becomes ``name: value`` lines.
    Capped at INPUTS_MAX_CHARS (see ``inputs_truncated``)."""
    raw = (req or {}).get("inputs")
    if not raw:
        return ""
    if isinstance(raw, dict):
        lines = []
        for name, value in raw.items():
            rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            lines.append(f"{name}: {rendered}")
        text = "\n".join(lines)
    else:
        text = str(raw).strip()
    if len(text) > INPUTS_MAX_CHARS:
        text = text[:INPUTS_MAX_CHARS] + "\n[... inputs truncated by ASTRA at 20000 characters ...]"
    return text


def inputs_truncated(req: dict) -> bool:
    raw = (req or {}).get("inputs")
    if not raw:
        return False
    length = len(str(raw)) if not isinstance(raw, dict) else sum(
        len(str(k)) + len(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) + 2
        for k, v in raw.items()
    )
    return length > INPUTS_MAX_CHARS


def inputs_block(req: dict, inputs_limit: int | None = None) -> str:
    """Prompt block for the conjecture engine, the structurer and the author.

    The policy comes FIRST: whoever truncates the block downstream (the
    1500-character auditor block, the structurer's 6000) must lose values
    before losing the one sentence that says placeholders were approved. ``inputs_limit`` caps the values for those auditors. Empty when
    the request supplies nothing and keeps the strict policy, so prompts are
    byte-for-byte what they were.
    """
    parts = []
    if input_policy(req) == "assume":
        parts.append(ASSUME_POLICY_TEXT)
    text = inputs_text(req)
    if text:
        if inputs_limit is not None and len(text) > inputs_limit:
            text = text[:inputs_limit] + "\n[... inputs shortened for this reader ...]"
        parts.append(
            "FROZEN INPUTS (supplied by the user; authoritative, use these exact "
            "values instead of declaring them missing):\n" + text
        )
    return "\n\n".join(parts)


def parse_assumed_inputs(stdout: str) -> list:
    seen = []
    for item in _ASSUMED.findall(str(stdout or "")):
        text = re.sub(r"\s+", " ", item).strip()
        if text and text.lower() not in _NONE_WORDS and text not in seen:
            seen.append(text)
    return seen


SILENT_ASSUME_DEFERRED = (
    "The validator ran under input policy 'assume' but declared no ASSUMED line: "
    "the placeholder values it used are unknown; confirm them before relying on "
    "this verdict."
)


def build_input_request(missing: list, checkpoint_path: str, req: dict,
                        convention_request=None) -> dict:
    """The question the calling agent must put to the user, with the three
    answers and the exact re-run for each.

    When what is missing is a convention (9 October 2026 benchmark: the
    validator itself declared "MISSING: a convention for real division at
    b = 0"), the analyst's ``convention_request`` adds one option per reading;
    those re-run a fresh cycle, as in ``build_convention_request``.
    """
    missing = [str(m) for m in (missing or []) if str(m).strip()]
    base = {key: (req or {})[key] for key in _RERUN_KEYS if (req or {}).get(key)}
    resume = {"resume_checkpoint": checkpoint_path} if checkpoint_path else {}
    already = inputs_text(req)
    placeholder = "<name: value, or the pasted contents, one input per line>"
    extracted = "<the extracted values>"
    if already:
        # Keep what the user already supplied; the cycle still needs more.
        placeholder = already + "\n" + placeholder
        extracted = already + "\n" + extracted
    listed = ", ".join(missing).rstrip(".") if missing else "inputs the request does not contain"
    ask = {
        "action_required": "ASK_USER",
        "kind": "missing_inputs",
        "question": (
            f"ASTRA cannot decide this cycle without: {listed}. Do you have these "
            "values (provide), should ASTRA assume explicit placeholder values and "
            "report the verdict as conditional on them (assume), or should they be "
            "extracted from a file or an earlier result (extract)?"
        ),
        "missing_inputs": missing,
        "options": {
            "provide": {
                "when": "the user has the values or the frozen contents",
                "rerun": {**base, **resume, "inputs": placeholder},
            },
            "assume": {
                "when": "the user lets ASTRA pick explicit placeholder values; the result "
                        "carries assumed_inputs and the verdict is conditional on them",
                "rerun": {**base, **resume, "input_policy": "assume"},
            },
            "extract": {
                "when": "the values live in a file, a paper, or a previous ASTRA result: the "
                        "agent reads them and passes them as inputs",
                "rerun": {**base, **resume, "inputs": extracted},
            },
        },
        "resume_checkpoint": checkpoint_path,
        "note": (
            "resume_checkpoint reuses this cycle's conjecture (already paid for) and "
            "starts the new run at the validator with the inputs in hand."
        ),
    }
    readings = normalize_convention_request(convention_request)
    if readings is not None:
        ask["question"] += (
            f" If what is missing is a convention, the readings that would decide the "
            f"claim are: {_listed(readings)} (options convention_N)."
        )
        ask["conventions"] = readings["conventions"]
        ask["options"].update(_convention_options(readings, base, already, other=False))
        ask["note"] += (
            " The convention_N options re-run a fresh cycle instead: a convention can "
            "change the conjecture itself."
        )
    return ask


# Only a cycle that decided its own conjecture can say the user's claim is
# open because of a convention; after a code error or a missing input the
# INCONCLUSIVE has another cause and the question would be wrong.
CONVENTION_STATUSES = ("VALIDATED", "REFUTED")
CONVENTION_VERDICTS = ("INCONCLUSIVE", "SUBSTITUTED")
CONVENTIONS_MAX = 4
CONVENTION_PREFIX = (
    "CONVENTION (chosen by the user; read the claim in the objective under it "
    "and judge the claim as stated with this convention added):"
)


def _short(value, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def normalize_convention_request(raw) -> dict | None:
    """The analyst's ``convention_request`` reduced to a closed shape, or None.

    Accepts ``{"question": str, "conventions": [{"label", "statement"} | str]}``;
    a convention without a statement is dropped, duplicates are dropped, at
    most CONVENTIONS_MAX are kept. Nothing usable -> None, never a guess.
    """
    if not isinstance(raw, dict):
        return None
    conventions, seen = [], set()
    for item in raw.get("conventions") if isinstance(raw.get("conventions"), list) else []:
        if isinstance(item, dict):
            statement = _short(item.get("statement"), 400)
            label = _short(item.get("label"), 80)
        elif isinstance(item, str):
            statement, label = _short(item, 400), ""
        else:
            continue
        if not statement or statement.casefold() in seen:
            continue
        seen.add(statement.casefold())
        conventions.append({"label": label or _short(statement, 80), "statement": statement})
        if len(conventions) == CONVENTIONS_MAX:
            break
    if not conventions:
        return None
    return {"question": _short(raw.get("question"), 500), "conventions": conventions}


def _listed(request: dict) -> str:
    return "; ".join(
        f"({i}) {c['statement'].rstrip('.')}" for i, c in enumerate(request["conventions"], start=1)
    )


def _convention_options(request: dict, base: dict, already: str, other: bool = True) -> dict:
    """One fresh re-run per reading (the reading as ``inputs``, after any
    inputs the user already gave); ``other`` adds a slot for the user's own."""

    def _inputs(statement: str) -> str:
        line = f"{CONVENTION_PREFIX} {statement}"
        return f"{already}\n{line}" if already else line

    options = {}
    for index, convention in enumerate(request["conventions"], start=1):
        options[f"convention_{index}"] = {
            "label": convention["label"],
            "when": convention["statement"],
            "rerun": {**base, "inputs": _inputs(convention["statement"])},
        }
    if other:
        options["other"] = {
            "label": "another convention",
            "when": "the user states a convention or assumption not listed here",
            "rerun": {**base, "inputs": _inputs("<the user's convention, as one explicit sentence>")},
        }
    return options


def build_convention_request(analysis: dict, req: dict) -> dict | None:
    """The question for a claim left open only by an unstated convention.

    ``analysis`` is the FINAL analysis of the cycle (status and re-anchored
    verdict after every guard). Returns None unless the cycle decided its
    conjecture, the claim stayed INCONCLUSIVE/SUBSTITUTED and the analyst
    named the readings. Each option re-runs a fresh cycle with the reading as
    ``inputs``: no resume_checkpoint, because the convention can change the
    conjecture itself.
    """
    analysis = analysis or {}
    if str(analysis.get("status") or "").upper() not in CONVENTION_STATUSES:
        return None
    if str(analysis.get("original_claim_verdict") or "").upper() not in CONVENTION_VERDICTS:
        return None
    request = normalize_convention_request(analysis.get("convention_request"))
    if request is None:
        return None
    base = {key: (req or {})[key] for key in _RERUN_KEYS if (req or {}).get(key)}
    question = request["question"] or (
        "The claim, as stated, leaves a convention or an assumption open."
    )
    return {
        "action_required": "ASK_USER",
        "kind": "convention",
        "question": (
            f"{question} Which reading did you mean? {_listed(request)}. Or state another one."
        ),
        "conventions": request["conventions"],
        "options": _convention_options(request, base, inputs_text(req)),
        "note": (
            "status and original_claim_verdict of this cycle are unchanged. Each re-run "
            "is a fresh cycle (no resume_checkpoint) and answers the claim under the "
            "chosen convention, not the claim as originally stated."
        ),
    }
