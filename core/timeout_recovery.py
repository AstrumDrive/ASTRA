"""Preserve evidence and guide bounded recovery; elapsed time is not a refutation."""
import hashlib


def output_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def timed_out(result):
    return result.get("exit_code") == 124 or result.get("timed_out") is True


def attempt_record(code, result, timeout, number):
    return {"attempt": number, "timeout_s": timeout,
            "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
            "exit_code": result.get("exit_code"), "timed_out": timed_out(result),
            "stdout_tail": output_text(result.get("stdout"))[-4000:],
            "stderr_tail": output_text(result.get("stderr"))[-2000:]}


def recovery_instructions(result, timeout):
    if not timed_out(result):
        return ""
    return (
        f"EXECUTION DEADLINE: {timeout}s elapsed without completing the validator. "
        "This is an operational timeout, not a mathematical counterexample. "
        "Use the partial stdout to identify the last completed proof obligation. "
        "Change the blocked computational strategy before the next attempt: "
        "isolate smaller identities, use explicit symbols instead of expensive "
        "generic-function simplification, or supply a complete analytic proof "
        "with independently checked decisive identities. Preserve the original "
        "claim and every proof obligation. Print flushed PROGRESS lines before "
        "and after each bounded stage. Do not merely rerun unchanged code, "
        "increase the deadline, or replace verification by printing PASS. "
        "If the proof cannot close, report the original claim INCONCLUSIVE.\n"
    )
