"""What ablation stage 3 costs in tokens, before it is spent.

Stage 3 is 1692 model calls that cannot be moved off the workstation, against a
weekly per-account limit on one of the two providers. The point of this script
is that the cost is measured rather than guessed at, and that the measurement is
reproducible after the models change under it.

Method, in two halves:

  exact      Every reviewer prompt is rebuilt exactly as
             LlmClient.review_validation_code assembles it, with the same
             truncations and the same deterministic smoke block, so the
             character counts are the real ones. This half costs nothing and is
             what `--chars` prints. It also counts the cases a preflight answers
             on its own, which never reach a model and so cost nothing at all.

  calibrated Characters become tokens through least-squares fits against real
             CLI calls that reported their own usage. A chars-per-token ratio
             cannot do this job: Python source runs near 2.4 chars/token, well
             away from the 4 that prose suggests, and each provider adds a fixed
             per-call overhead that no ratio can express. `--calibrate` re-runs
             those calls and prints fresh constants; without it the constants
             below are used, which is free.

Totals are summed case by case rather than evaluated at the mean, because the
fits have an intercept and the size distribution is wide.

Usage (the project venv, not a bare `python` -- see REVIEW_INDEPENDENCE_ABLATION.md):

    .\\venv\\Scripts\\python.exe scripts\\estimate_ablation_tokens.py
    .\\venv\\Scripts\\python.exe scripts\\estimate_ablation_tokens.py --chars
    .\\venv\\Scripts\\python.exe scripts\\estimate_ablation_tokens.py --calibrate
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPEATS = 3

# Arms of the review-independence ablation. Arm D runs the deterministic guard
# and calls no model, so it is free and is still listed, because a table that
# omits the free arm invites someone to add its cost back in later.
ARMS = [
    ("full (arm D)", None, None),
    ("abl-self (opus-4-8)", "claude", "neutral"),
    ("abl-weights (sonnet)", "claude", "neutral"),
    ("abl-cross (gpt-5.6-sol)", "codex", "neutral"),
    ("abl-p-shipped (gpt-5.6-sol)", "codex", "production"),
]

# ---------------------------------------------------------------------------
# Measured 2026-09-12 on this workstation. Each row is (prompt_chars, tokens)
# taken from a real call that reported its own usage: Claude through
# `claude -p --output-format json` (which returns input, cache and output
# counts), Codex through the cumulative "tokens used" line `codex exec` prints.
#
# Two things these numbers carry that a ratio would not. The Claude intercept is
# roughly 4,200 tokens of harness preamble charged on every call before any
# content, which is a fifth of that side of the run. And Codex reports one
# cumulative figure rather than a split, so its fit is a total and its output
# column below is zero by construction, not because it emits nothing.
#
# Re-measure with --calibrate whenever a model or a CLI changes; these will
# drift, and a stale constant presented as a measurement is worse than no
# measurement.
CLAUDE_SAMPLES = [
    # (chars, billed_input_tokens, output_tokens)
    (30, 4272, 4),
    (4816, 6026, 3760),
    (11469, 8746, 10311),
    (13138, 9854, 9416),
    (19062, 12032, 13535),
]
CODEX_SAMPLES = [
    # (chars, total_tokens)
    (4816, 4305),
    (13138, 9024),
    (19062, 9941),
]
# Observed cost proxies on the four full-size Claude calls, in USD as the CLI
# accounts for them. On a subscription this is consumption accounting and not a
# charge; it is recorded because it is the only per-call figure the CLI gives
# that is comparable across models.
CLAUDE_COST_SAMPLES = [0.154, 0.345, 0.334, 0.459]


def fit(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Least squares y = intercept + slope*x, with the worst residual."""
    xs = [float(x) for x, _ in points]
    ys = [float(y) for _, y in points]
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    slope = (sum((a - mean_x) * (b - mean_y) for a, b in zip(xs, ys))
             / sum((a - mean_x) ** 2 for a in xs))
    intercept = mean_y - slope * mean_x
    worst = max(abs(b - (intercept + slope * a)) for a, b in zip(xs, ys))
    return intercept, slope, worst


def build_prompts() -> tuple[dict[str, list[int]], list[tuple[str, str]], int]:
    """Rebuild every stage-3 reviewer prompt; return its size per variant.

    Mirrors LlmClient.review_validation_code. If that function's truncations or
    section headers change, this drifts silently, which is why the assembled
    text is returned for --dump rather than only its length.
    """
    from core.preflight import load_project_env
    load_project_env()
    from core.quality_benchmarks import load_quality_cases, select_quality_cases
    from core.validator_preflight import audit_validation_code, smoke_validation_code
    from agents.reviewer import reviewer_prompt

    vnext = (os.environ.get("ASTRA_VALIDATOR_REPAIR_VNEXT", "0")
             .strip().strip("'\"").lower() in {"1", "true", "on", "yes"})
    systems = {v: reviewer_prompt(vnext, v) for v in ("neutral", "production")}

    cases = select_quality_cases(load_quality_cases(), tier="release",
                                 tracks={"validator_audit"})
    sizes: dict[str, list[int]] = {"neutral": [], "production": []}
    samples: list[tuple[str, str]] = []
    skipped = 0
    for case in cases:
        # With the repair path on, a case the preflight rejects is answered
        # deterministically and never reaches a model. Counting those as calls
        # overstates the bill; this is where the 146 becomes 141.
        if vnext and audit_validation_code(case.code).get("status") != "APPROVED":
            skipped += 1
            continue
        user = (
            f"SHARED FINAL OBJECTIVE:\n{case.objective[:2000]}\n\n"
            f"CONSENSUS CONJECTURE:\n{case.intuition[:5000]}\n\n"
            f"PROPOSED VALIDATION SCRIPT:\n```text\n{case.code[:14000]}\n```"
        )
        if vnext:
            smoke = smoke_validation_code(case.code)
            user += (
                "\n\nDETERMINISTIC COMPILE/IMPORT SMOKE (facts, not model "
                "speculation):\n"
                f"{json.dumps(smoke, ensure_ascii=False)[:3000]}"
            )
        for variant in sizes:
            sizes[variant].append(len(systems[variant]) + len(user))
        samples.append((case.id, systems["neutral"] + "\n\n" + user))
    return sizes, samples, skipped


# ------------------------------------------------------------------ calibrate
def _call_claude(prompt: str) -> tuple[int, int, float]:
    from core.cli_backend import _claude_bin
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(prompt)
        path = handle.name
    argv = [_claude_bin(), "-p", "--output-format", "json", "--tools", "",
            "--strict-mcp-config", "--model", "claude-opus-4-8"]
    with open(path, "rb") as stdin:
        done = subprocess.run(argv, stdin=stdin, capture_output=True,
                              text=True, timeout=900)
    payload = json.loads(done.stdout)
    use = payload.get("usage") or {}
    billed = (use.get("input_tokens", 0)
              + use.get("cache_creation_input_tokens", 0)
              + use.get("cache_read_input_tokens", 0))
    return billed, use.get("output_tokens", 0), payload.get("total_cost_usd", 0.0)


def _call_codex(prompt: str) -> int:
    binary = ((os.environ.get("ASTRA_CODEX_BIN") or "").strip().strip("'\"")
              or "codex")
    effort = (os.environ.get("ASTRA_CODEX_REASONING", "high")
              or "").strip().strip("'\"")
    work = Path(tempfile.mkdtemp())
    promptfile, outfile = work / "prompt.txt", work / "out.txt"
    promptfile.write_text(prompt, encoding="utf-8")
    argv = [binary, "exec", "--dangerously-bypass-approvals-and-sandbox",
            "--ignore-user-config", "--skip-git-repo-check", "-m", "gpt-5.6-sol"]
    if effort:
        argv += ["-c", f'model_reasoning_effort="{effort}"']
    argv += ["-C", str(work), "-o", str(outfile), "-"]
    with open(promptfile, "rb") as stdin:
        done = subprocess.run(argv, stdin=stdin, capture_output=True,
                              text=True, timeout=1800)
    lines = [line.strip() for line in
             ((done.stdout or "") + "\n" + (done.stderr or "")).splitlines()
             if line.strip()]
    # Codex prints the count on the line after the label, not on it.
    for index, line in enumerate(lines[:-1]):
        if re.fullmatch(r"tokens used", line, re.I):
            return int(lines[index + 1].replace(",", ""))
    raise RuntimeError("codex reported no token line")


def calibrate(samples: list[tuple[str, str]]) -> None:
    """Re-measure the fits against live calls. Spends model quota."""
    ordered = sorted(samples, key=lambda item: len(item[1]))
    picks = [ordered[0], ordered[len(ordered) // 2], ordered[-1]]
    print("calibrating against live calls; this spends quota on both accounts")
    print()
    print("CLAUDE_SAMPLES = [")
    print("    (30, ?, ?),  # keep a tiny call to pin the intercept")
    for case_id, prompt in picks:
        billed, out, cost = _call_claude(prompt)
        print(f"    ({len(prompt)}, {billed}, {out}),"
              f"  # {case_id}, ${cost:.3f}")
    print("]")
    print("CODEX_SAMPLES = [")
    for case_id, prompt in picks:
        print(f"    ({len(prompt)}, {_call_codex(prompt)}),  # {case_id}")
    print("]")


# ----------------------------------------------------------------------- main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chars", action="store_true",
                        help="character counts only, no token model")
    parser.add_argument("--calibrate", action="store_true",
                        help="re-measure the fits with live calls (spends quota)")
    args = parser.parse_args()

    sizes, samples, skipped = build_prompts()
    reached = len(sizes["neutral"])
    total_cases = reached + skipped
    print(f"{total_cases} cases at release tier; {skipped} answered by preflight "
          f"with no model call; {reached} reach a reviewer")
    print(f"prompt chars: mean {statistics.fmean(sizes['neutral']):,.0f}  "
          f"min {min(sizes['neutral']):,}  max {max(sizes['neutral']):,}  "
          f"sum {sum(sizes['neutral']):,}")
    print()

    if args.calibrate:
        calibrate(samples)
        return 0
    if args.chars:
        return 0

    claude_in = fit([(c, i) for c, i, _ in CLAUDE_SAMPLES])
    # The tiny call answered one word because it was asked to; that is a valid
    # input point and a meaningless output one, so it is dropped here only.
    claude_out = fit([(c, o) for c, _, o in CLAUDE_SAMPLES if c > 1000])
    codex_total = fit(CODEX_SAMPLES)

    print("fits, y = intercept + slope * prompt_chars")
    print(f"  claude input : {claude_in[0]:8,.0f} + {claude_in[1]:.4f}/char"
          f"   one token per {1 / claude_in[1]:.2f} chars"
          f"   worst residual {claude_in[2]:,.0f}")
    print(f"  claude output: {claude_out[0]:8,.0f} + {claude_out[1]:.4f}/char"
          f"   worst residual {claude_out[2]:,.0f}")
    print(f"  codex total  : {codex_total[0]:8,.0f} + {codex_total[1]:.4f}/char"
          f"   worst residual {codex_total[2]:,.0f}")
    print()

    header = (f"{'arm':29} {'via':7} {'calls':>6} {'input':>12} "
              f"{'output':>12} {'total':>13}")
    print(header)
    grand = claude_side = 0.0
    calls_total = 0
    for name, provider, variant in ARMS:
        if provider is None:
            print(f"{name:29} {'none':7} {0:6,} {0:12,} {0:12,} {0:13,}")
            continue
        chars = sizes[variant]
        calls = len(chars) * REPEATS
        if provider == "claude":
            inp = sum(claude_in[0] + claude_in[1] * c for c in chars) * REPEATS
            out = sum(max(0.0, claude_out[0] + claude_out[1] * c)
                      for c in chars) * REPEATS
        else:
            inp = sum(codex_total[0] + codex_total[1] * c for c in chars) * REPEATS
            out = 0.0
        grand += inp + out
        calls_total += calls
        if provider == "claude":
            claude_side += inp + out
        print(f"{name:29} {provider:7} {calls:6,} {inp:12,.0f} "
              f"{out:12,.0f} {inp + out:13,.0f}")
    print(f"{'':29} {'':7} {calls_total:6,} {'':12} {'':12} {grand:13,.0f}")
    print()
    print(f"TOTAL ~{grand / 1e6:.1f} M tokens over {calls_total:,} model calls")
    print(f"  Claude account: ~{claude_side / 1e6:.1f} M over "
          f"{calls_total // 2:,} calls -- the weekly-limited side")
    print(f"  Codex account : ~{(grand - claude_side) / 1e6:.1f} M over "
          f"{calls_total // 2:,} calls")
    if CLAUDE_COST_SAMPLES:
        mean_cost = statistics.fmean(CLAUDE_COST_SAMPLES)
        print(f"  Claude consumption proxy: ~${mean_cost * calls_total // 2:,.0f} "
              f"at ${mean_cost:.2f} a call; on a subscription this is accounting, "
              "not a charge")
    print()

    mean_call = statistics.fmean(
        [claude_in[0] + claude_in[1] * c + claude_out[0] + claude_out[1] * c
         for c in sizes["neutral"]]
    )
    band = max(claude_out[2], codex_total[2]) / mean_call
    print(f"Error. The worst residual on the fits is {100 * band:.0f} per cent of "
          f"a mean call, so read this as {grand / 1e6:.0f} M give or take "
          f"{grand / 1e6 * band:.0f} M.")
    print("The scatter is in the output term and tracks how much reasoning a case")
    print("provokes, which is not a function of its length, so it will not average")
    print("away as cleanly as a length-driven error would. Two known biases, both")
    print("upward: the sonnet arm is priced with opus measurements, and the Claude")
    print("intercept assumes no cache reuse between calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
