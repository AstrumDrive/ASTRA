"""Control 9 of the review-independence ablation: is length a giveaway?

Every defective case in the ablation corpus is a patch of a sound base, so the
two strata could differ systematically in size. A reviewer could then score well
by reading the line count instead of the mathematics, and the experiment would
be measuring its own construction. This is measured on every corpus extension
rather than argued, and the numbers quoted in REVIEW_INDEPENDENCE_ABLATION.md
section 6 control 9 come from here and are never typed by hand.

Two measurements, because they fail in different ways:

  unpaired  the best accuracy ANY threshold on the line count can reach, against
            the majority baseline. This is a maximum taken over every threshold
            and evaluated on the same data that chose it, so it is biased upward
            and reads as an upper bound on the leak, not an estimate of it;

  paired    each defective case against the sound base it was derived from. The
            between-case variance drops out entirely, which is what makes the
            comparison sensitive, with a two-sided sign test on the direction
            computed exactly from the binomial rather than through a normal
            approximation that 68 pairs would not justify.

    python scripts/check_length_confound.py
"""
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = ROOT / "benchmarks" / "quality" / "validator_audit"


def line_count(case: dict) -> int:
    return case["code"].count("\n") + 1


def unpaired(labelled: list[tuple[int, str]]) -> tuple[float, float, int, str]:
    """The best line-count threshold and what the majority baseline already gets."""
    total = len(labelled)
    counts = {"sound": 0, "flawed": 0}
    for _, label in labelled:
        counts[label] += 1
    baseline = max(counts.values()) / total

    best, best_cut, best_rule = 0.0, 0, "none"
    for cut in sorted({value for value, _ in labelled}):
        for rule in ("shorter_is_flawed", "longer_is_flawed"):
            hits = sum(
                (("flawed" if value < cut else "sound") if rule == "shorter_is_flawed"
                 else ("flawed" if value >= cut else "sound")) == label
                for value, label in labelled
            )
            if hits / total > best:
                best, best_cut, best_rule = hits / total, cut, rule
    return best, baseline, best_cut, best_rule


def sign_test(gaps: list[int]) -> tuple[int, int, float]:
    """Two-sided sign test on the nonzero differences, exact from the binomial."""
    unequal = [gap for gap in gaps if gap != 0]
    longer = sum(1 for gap in unequal if gap > 0)
    shorter = len(unequal) - longer
    n, k = len(unequal), min(longer, shorter)
    if n == 0:
        return longer, shorter, 1.0
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return longer, shorter, min(1.0, 2 * tail)


def main() -> int:
    sound = json.loads((CORPUS / "ablation_sound.json").read_text(encoding="utf-8"))
    flawed = json.loads((CORPUS / "ablation_flawed.json").read_text(encoding="utf-8"))

    sound_lines = {case["id"]: line_count(case) for case in sound}
    pairs = [(case["derived_from"], line_count(case)) for case in flawed]

    orphans = [parent for parent, _ in pairs if parent not in sound_lines]
    if orphans:
        # Without this the paired test would silently run on a subset, which is
        # the failure mode that makes a flat result meaningless.
        print(f"ERROR: {len(orphans)} defective cases name a base that is not in "
              f"the sound corpus, e.g. {orphans[0]!r}")
        return 1

    labelled = ([(value, "sound") for value in sound_lines.values()]
                + [(value, "flawed") for _, value in pairs])
    best, baseline, cut, rule = unpaired(labelled)
    total = len(labelled)

    gaps = [value - sound_lines[parent] for parent, value in pairs]
    longer, shorter, p_value = sign_test(gaps)
    mean_gap = sum(gaps) / len(gaps)
    mean_sound = sum(sound_lines.values()) / len(sound_lines)

    print(f"{len(sound_lines)} sound and {len(pairs)} defective cases, "
          f"mean sound length {mean_sound:.1f} lines")
    print()
    print(f"unpaired: best threshold {cut} lines ({rule}) scores {100 * best:.1f}% "
          f"against a majority baseline of {100 * baseline:.1f}%")
    print(f"          edge = {100 * (best - baseline):.1f} points "
          f"= {round((best - baseline) * total)} of {total} cases, and this is a "
          "maximum over thresholds, so it sits above the baseline on noise alone")
    print()
    print(f"paired:   defective minus its own base = {mean_gap:+.2f} lines")
    print(f"          {longer} longer, {shorter} shorter, "
          f"{len(gaps) - longer - shorter} identical, of {len(gaps)} pairs")
    print(f"          two-sided sign test: p = {p_value:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
