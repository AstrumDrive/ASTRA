"""ASTRA certified ball arithmetic: the vetted helper validators may call.

A validator that starts a line with ``# ASTRA_CERTIFIED: arb`` gets this file
executed in its own namespace (core/certified/__init__.py replaces that line
with one ``exec`` line, so line numbers do not move). Everything here is built
on python-flint (Arb): a number is a ball [mid +/- rad] that contains the exact
value, every operation returns a ball that contains every exact result, and a
ball that straddles the branch cut of ``log`` comes back wide, never wrong.

Rules the reviewer may rely on (tests/test_certified_arb.py checks each one):

* nothing here returns a decision that the balls do not certify: comparisons
  are True only when certain; ``certify``/``unique_integer``/``branch_index``/
  ``certify_sup_abs_le`` raise ``Undecided`` otherwise;
* ``Undecided`` is not a refutation: raise the precision, subdivide, or let the
  validator end without PASS or FAIL for that leg;
* ``sup_abs_on_sector`` covers the closed polar rectangle
  ``r_min <= |z| <= r_max, t_min <= arg z <= t_max`` (angles in radians, the
  sector may cross the negative real axis) and nothing outside it. A claim on
  ``|z| -> infinity`` also needs the tail ``|z| > r_max``: prove it analytically
  and declare it with ``analytic_tail(...)``; the verdict is then conditional
  on that lemma and ASTRA reports it as such.
"""
from __future__ import annotations

import math as _math
import sys as _sys

try:
    import flint as _flint
    from flint import acb, arb, ctx as _ctx
except ImportError:  # pragma: no cover - exercised on engines without flint
    print(
        "ASTRA_CERTIFIED: python-flint is not installed in this Python. Run the "
        "validator with oracle='astrum' (its Python has python-flint) or "
        "install python-flint.",
        file=_sys.stderr,
    )
    raise SystemExit(4)

ASTRA_CERTIFIED_VERSION = "arb-1"


class Undecided(Exception):
    """The balls could not decide at this precision. Never a FAIL by itself."""


def set_precision(bits: int) -> int:
    """Working precision in bits (53 to 100000). Returns the value set."""
    bits = int(bits)
    if not 53 <= bits <= 100000:
        raise ValueError("precision must be between 53 and 100000 bits")
    _ctx.prec = bits
    return bits


def _as_arb(x) -> arb:
    if isinstance(x, arb):
        return x
    if isinstance(x, acb):
        raise TypeError("expected a real ball, got a complex one; use .real/.imag")
    if isinstance(x, bool):
        raise TypeError("booleans are not numbers here")
    if isinstance(x, (int, str)):
        return arb(x)
    if isinstance(x, float):
        if not _math.isfinite(x):
            raise ValueError("non-finite float")
        return arb(x)  # the exact binary value of the float
    numerator = getattr(x, "numerator", None)
    denominator = getattr(x, "denominator", None)
    if isinstance(numerator, int) and isinstance(denominator, int):
        return arb(numerator) / arb(denominator)
    raise TypeError(f"cannot make a ball from {type(x).__name__}")


def _as_acb(z) -> acb:
    if isinstance(z, acb):
        return z
    if isinstance(z, complex):
        return acb(_as_arb(z.real), _as_arb(z.imag))
    return acb(_as_arb(z))


def ball(value, radius=0) -> arb:
    """A real ball. Pass exact values as int, Fraction or a string ("1/3",
    "0.1"); a float means its exact binary value. ``radius`` widens it."""
    x = _as_arb(value)
    radius = _as_arb(radius)
    if is_certainly_lt(radius, 0):
        raise ValueError("radius must be >= 0")
    if radius != 0:
        x = x + arb(0, upper_float(radius))
    return x


def cball(re, im=0, radius=0) -> acb:
    """A complex ball (a box): ``radius`` widens each part, so the box
    contains the disk of that radius around ``re + i*im``."""
    return acb(ball(re, radius), ball(im, radius))


def _exact(dyadic: arb):
    from fractions import Fraction

    mantissa, exponent = (int(v) for v in dyadic.man_exp())
    if exponent >= 0:
        return Fraction(mantissa * 2 ** exponent)
    return Fraction(mantissa, 2 ** -exponent)


def upper_float(x) -> float:
    """A float that is >= every point of the real ball ``x`` (inf if unbounded).

    The midpoint and radius of a ball are exact dyadic numbers: their sum is
    formed exactly and rounded up, so cancellation cannot lose the bound.
    """
    from fractions import Fraction

    x = _as_arb(x)
    if not x.is_finite():
        return _math.inf
    top = _exact(x.mid()) + _exact(x.rad())
    try:
        value = float(top)
    except OverflowError:
        return _math.inf
    if Fraction(value) < top:
        value = _math.nextafter(value, _math.inf)
    return value


def abs_upper_float(z) -> float:
    """A float that is >= |w| for every w in the (real or complex) ball ``z``."""
    z = _as_acb(z)
    if not z.is_finite():
        return _math.inf
    return upper_float(abs(z))


def is_certainly_lt(a, b) -> bool:
    """True only when every point of a is < every point of b. False means
    "not certified", NEVER "a >= b": do not negate it."""
    return bool(_as_arb(a) < _as_arb(b))


def is_certainly_le(a, b) -> bool:
    """True only when certainly a <= b. False is not a proof of a > b."""
    return bool(_as_arb(a) <= _as_arb(b))


def is_certainly_gt(a, b) -> bool:
    """True only when certainly a > b. False is not a proof of a <= b."""
    return bool(_as_arb(a) > _as_arb(b))


def is_certainly_ge(a, b) -> bool:
    """True only when certainly a >= b. False is not a proof of a < b."""
    return bool(_as_arb(a) >= _as_arb(b))


def is_certainly_nonzero(z) -> bool:
    """True only when the (real or complex) ball excludes 0."""
    z = _as_acb(z)
    return z.is_finite() and not z.contains(acb(0))


def certify(condition, what: str):
    """Pass only on the literal True a certified predicate returns."""
    if condition is not True:
        raise Undecided(f"not certified: {what}")
    return True


def unique_integer(x, what: str) -> int:
    """The integer n when the ball is known (by theory) to hold an integer.

    Certified when the ball has radius < 1/2 and contains exactly one integer;
    the caller must know the exact value IS an integer (for example a branch
    index), because a ball near 3 says nothing about a value that is not one.
    """
    if isinstance(x, acb):
        if not is_certainly_lt(abs_upper_float(x.imag), arb("0.5")):
            raise Undecided(f"{what}: imaginary part not certified near 0")
        x = x.real
    x = _as_arb(x)
    if not (x.is_finite() and is_certainly_lt(x.rad(), arb("0.5"))):
        raise Undecided(f"{what}: ball too wide to isolate an integer")
    n = x.unique_fmpz()
    if n is None:
        raise Undecided(f"{what}: the ball contains no integer")
    return int(n)


def branch_index(lhs, rhs, what: str) -> int:
    """The integer k with lhs - rhs = 2*pi*i*k, certified.

    Valid only when exp(lhs) = exp(rhs) holds exactly by construction, as for
    ``Log(a) + Log(b)`` against ``Log(a*b)`` or ``Log(w)`` against
    ``Log(w/2) + log(2)``. k = 0 certifies the identity on that ball.
    """
    two_pi_i = acb(0, 2 * arb.pi())
    q = (_as_acb(lhs) - _as_acb(rhs)) / two_pi_i
    return unique_integer(q, what)


def polar_box(r0, r1, t0, t1) -> acb:
    """A complex ball containing the polar rectangle r0<=|z|<=r1, t0<=arg<=t1.

    |r e^{it} - c| <= |r - r_m| + r_m |t - t_m| for c = r_m e^{i t_m}, so the
    box around c widened by (r1-r0)/2 + r_m (t1-t0)/2 contains it.
    """
    r0, r1, t0, t1 = (_as_arb(v) for v in (r0, r1, t0, t1))
    certify(is_certainly_ge(r0, 0) and is_certainly_le(r0, r1), "0 <= r0 <= r1")
    certify(is_certainly_le(t0, t1), "t0 <= t1")
    r_mid, t_mid = (r0 + r1) / 2, (t0 + t1) / 2
    center = acb(0, t_mid).exp() * r_mid
    spread = (r1 - r0) / 2 + r_mid * (t1 - t0) / 2
    re_rad = upper_float(center.real.rad() + spread)
    im_rad = upper_float(center.imag.rad() + spread)
    return acb(arb(center.real.mid(), re_rad), arb(center.imag.mid(), im_rad))


def sector_boxes(r_min, r_max, t_min, t_max, n_r: int = 16, n_t: int = 16):
    """The uniform grid of polar rectangles covering the sector, with their
    covering balls: a list of (box, (r0, r1, t0, t1))."""
    r_min, r_max, t_min, t_max = (_as_arb(v) for v in (r_min, r_max, t_min, t_max))
    out = []
    for i in range(int(n_r)):
        r0 = r_min + (r_max - r_min) * i / n_r
        r1 = r_min + (r_max - r_min) * (i + 1) / n_r
        for j in range(int(n_t)):
            t0 = t_min + (t_max - t_min) * j / n_t
            t1 = t_min + (t_max - t_min) * (j + 1) / n_t
            out.append((polar_box(r0, r1, t0, t1), (r0, r1, t0, t1)))
    return out


def sup_abs_on_sector(f, r_min, r_max, t_min, t_max, n_r: int = 16, n_t: int = 16,
                      max_depth: int = 8, target=None) -> dict:
    """A certified upper bound of |f(z)| on the closed sector.

    ``f`` takes and returns balls (acb/arb arithmetic, ``acb.log``, ``.exp``,
    ``.sqrt``...); a float or numpy function is rejected by flint itself. Boxes
    whose enclosure is infinite, or above ``target`` when one is given, are
    split in four up to ``max_depth`` times. ``certified`` is True only when no
    box is left unresolved (and, with a target, every box is <= target).
    """
    target_ball = None if target is None else _as_arb(target)
    stack = [(box, rect, 0) for box, rect in sector_boxes(r_min, r_max, t_min, t_max, n_r, n_t)]
    upper, boxes, unresolved = 0.0, 0, []
    while stack:
        box, (r0, r1, t0, t1), depth = stack.pop()
        boxes += 1
        value = _as_acb(f(box))
        modulus = abs(value) if value.is_finite() else None
        ok = modulus is not None and (target_ball is None or is_certainly_le(modulus, target_ball))
        if ok:
            upper = max(upper, upper_float(modulus))
            continue
        if depth < max_depth:
            rm, tm = (r0 + r1) / 2, (t0 + t1) / 2
            for rect in ((r0, rm, t0, tm), (r0, rm, tm, t1), (rm, r1, t0, tm), (rm, r1, tm, t1)):
                stack.append((polar_box(*rect), rect, depth + 1))
            continue
        unresolved.append(tuple(upper_float(v) for v in (r0, r1, t0, t1)))
        upper = _math.inf if modulus is None else max(upper, upper_float(modulus))
    return {
        "upper": upper,
        "boxes": boxes,
        "unresolved": unresolved,
        "certified": not unresolved and _math.isfinite(upper),
        "precision": _ctx.prec,
    }


def certify_sup_abs_le(f, r_min, r_max, t_min, t_max, bound, what: str, **kw) -> dict:
    """|f(z)| <= bound on the whole closed sector, or raise Undecided."""
    result = sup_abs_on_sector(f, r_min, r_max, t_min, t_max, target=bound, **kw)
    if not result["certified"]:
        raise Undecided(
            f"{what}: {len(result['unresolved'])} box(es) not certified <= bound "
            f"at {result['precision']} bits"
        )
    return result


def analytic_tail(statement: str) -> str:
    """Declare the unproved analytic lemma a sector bound relies on (for
    example the tail |z| > r_max). Printed as ANALYTIC_TAIL; ASTRA reports the
    verdict as conditional on it."""
    line = " ".join(str(statement).split())
    print(f"ANALYTIC_TAIL: {line}")
    return line


print(
    f"CERTIFIED_PRELUDE: {ASTRA_CERTIFIED_VERSION} python-flint {_flint.__version__} "
    f"precision {_ctx.prec} bits"
)
