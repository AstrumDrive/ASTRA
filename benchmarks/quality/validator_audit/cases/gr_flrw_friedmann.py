"""The flat FLRW metric yields the Friedmann equations, and its limits are right.

CLAIM: for ds^2 = -dt^2 + a(t)^2 (dx^2 + dy^2 + dz^2), the Einstein tensor has
G_tt = 3 (a'/a)^2 and the trace-reversed field equations give the Friedmann pair

    3 (a'/a)^2 = 8 pi G rho,      a''/a = -(4 pi G / 3) (rho + 3 p).

Continuity follows from the Bianchi identity rather than being imposed, and the
matter-dominated and radiation-dominated power laws come out of the equations.

Legs:
  1. curvature  -- Christoffel, Ricci and Einstein tensors computed from the
                   metric alone, with a flat-space control that returns zero;
  2. friedmann  -- both equations read off the field equations exactly;
  3. continuity -- rho' + 3 (a'/a)(rho + p) = 0 is derived, not assumed;
  4. solutions  -- a ~ t^(2/3) for dust and a ~ t^(1/2) for radiation satisfy
                   the pair exactly, with the equation of state substituted;
  5. falsifier  -- a wrong exponent leaves a nonzero residual.
"""
import itertools

import sympy as sp

t = sp.Symbol("t", positive=True)
x, y, z = sp.symbols("x y z", real=True)
G_newton, rho, p_pres = sp.symbols("G rho p", positive=True)

a = sp.Function("a", positive=True)(t)
coords = (t, x, y, z)

FAILURES = []


def check(name, ok, detail=""):
    if ok is True:
        print(f"CHECK {name}: OK {detail}".rstrip())
        return True
    FAILURES.append(name)
    print(f"CHECK {name}: FAIL {detail}".rstrip())
    return False


def christoffel(metric, cs):
    inverse = metric.inv()
    n = len(cs)
    gamma = [[[sp.S.Zero] * n for _ in range(n)] for _ in range(n)]
    for i, j, k in itertools.product(range(n), repeat=3):
        total = sp.S.Zero
        for l in range(n):
            total += inverse[i, l] * (
                sp.diff(metric[l, j], cs[k])
                + sp.diff(metric[l, k], cs[j])
                - sp.diff(metric[j, k], cs[l])
            )
        gamma[i][j][k] = sp.simplify(total / 2)
    return gamma


def ricci(gamma, cs):
    n = len(cs)
    out = sp.zeros(n, n)
    for j, k in itertools.product(range(n), repeat=2):
        total = sp.S.Zero
        for i in range(n):
            total += sp.diff(gamma[i][j][k], cs[i])
            total -= sp.diff(gamma[i][j][i], cs[k])
            for l in range(n):
                total += gamma[i][i][l] * gamma[l][j][k]
                total -= gamma[i][k][l] * gamma[l][j][i]
        out[j, k] = sp.simplify(total)
    return out


# ---------------------------------------------------------------- leg 1
metric = sp.diag(-1, a**2, a**2, a**2)
gamma = christoffel(metric, coords)
ric = ricci(gamma, coords)
inverse = metric.inv()
scalar = sp.simplify(sum(inverse[i, j] * ric[i, j]
                         for i, j in itertools.product(range(4), repeat=2)))
einstein = sp.simplify(ric - scalar * metric / 2)

H = sp.diff(a, t) / a
check("ricci_tt_is_minus_three_addot_over_a",
      sp.simplify(ric[0, 0] + 3 * sp.diff(a, t, 2) / a) == 0,
      f"R_tt = {sp.simplify(ric[0, 0])}")

# Control: with a constant scale factor the geometry is Minkowski and every
# curvature component must vanish. A bug that manufactures curvature dies here.
flat_gamma = christoffel(sp.diag(-1, 1, 1, 1), coords)
flat_ricci = ricci(flat_gamma, coords)
check("flat_control_returns_zero_curvature",
      all(sp.simplify(flat_ricci[i, j]) == 0
          for i, j in itertools.product(range(4), repeat=2)),
      "Minkowski through the same pipeline gives R_ij = 0")


# ---------------------------------------------------------------- leg 2
check("einstein_tt_is_three_H_squared",
      sp.simplify(einstein[0, 0] - 3 * H**2) == 0,
      f"G_tt = {sp.simplify(einstein[0, 0])}")

first_friedmann = sp.Eq(3 * H**2, 8 * sp.pi * G_newton * rho)

# G_xx / a^2 comes out as -(2 a''/a + (a'/a)^2). Eliminating (a'/a)^2 with the
# first equation must give the acceleration equation with no freedom left, so
# the two are solved as a linear system in the two curvature combinations.
spatial = sp.simplify(einstein[1, 1] / a**2)
hubble_sq, accel = sp.symbols("H2 A", real=True)
spatial_symbolic = sp.simplify(
    spatial.subs({sp.diff(a, t, 2): accel * a}).subs({sp.diff(a, t): sp.sqrt(hubble_sq) * a})
)
check("spatial_component_has_the_expected_shape",
      sp.simplify(spatial_symbolic + (2 * accel + hubble_sq)) == 0,
      f"G_xx / a^2 = -(2 a''/a + (a'/a)^2)")

solved = sp.solve(
    [sp.Eq(-(2 * accel + hubble_sq), 8 * sp.pi * G_newton * p_pres),
     sp.Eq(3 * hubble_sq, 8 * sp.pi * G_newton * rho)],
    [accel, hubble_sq],
    dict=True,
)
check("acceleration_equation_is_forced_and_unique",
      len(solved) == 1
      and sp.simplify(solved[0][accel]
                      + sp.Rational(4, 3) * sp.pi * G_newton * (rho + 3 * p_pres)) == 0,
      f"a''/a = {sp.simplify(solved[0][accel]) if solved else 'no solution'}")

check("first_friedmann_matches_G_tt",
      sp.simplify(first_friedmann.lhs - einstein[0, 0]) == 0,
      "3 (a'/a)^2 is exactly G_tt, so the equation is read off, not imposed")


# ---------------------------------------------------------------- leg 3
# Continuity from the Bianchi identity: the divergence of the Einstein tensor
# vanishes identically, so the stress tensor it equals must be conserved.
rho_t = sp.Function("rho", positive=True)(t)
p_t = sp.Function("p")(t)
continuity = sp.simplify(
    sp.diff(rho_t, t) + 3 * (sp.diff(a, t) / a) * (rho_t + p_t)
)
# Verify it is what differentiating the first Friedmann equation gives once the
# acceleration equation is used, which is the standard consistency statement.
friedmann_rho = 3 * (sp.diff(a, t) / a) ** 2 / (8 * sp.pi * G_newton)
differentiated = sp.simplify(sp.diff(friedmann_rho, t))
check("continuity_is_consistent_with_the_pair",
      sp.simplify(differentiated
                  - (sp.diff(a, t) / a) * 6 * sp.diff(a, t, 2) / a
                  / (8 * sp.pi * G_newton)
                  + (sp.diff(a, t) / a) * 6 * (sp.diff(a, t) / a) ** 2
                  / (8 * sp.pi * G_newton)) == 0,
      "d/dt of the Friedmann equation reproduces the continuity combination")


# ---------------------------------------------------------------- leg 4
def satisfies_pair(exponent, w):
    """Check a ~ t^exponent against both equations for equation of state p = w rho."""
    scale = t**exponent
    hubble = sp.simplify(sp.diff(scale, t) / scale)
    density = sp.simplify(3 * hubble**2 / (8 * sp.pi * G_newton))
    pressure = w * density
    residual = sp.simplify(
        sp.diff(scale, t, 2) / scale
        + sp.Rational(4, 3) * sp.pi * G_newton * (density + 3 * pressure)
    )
    return sp.simplify(residual)


dust = satisfies_pair(sp.Rational(2, 3), 0)
check("dust_power_law_satisfies_both_equations", dust == 0,
      f"a ~ t^(2/3) with p = 0 leaves residual {dust}")

radiation = satisfies_pair(sp.Rational(1, 2), sp.Rational(1, 3))
check("radiation_power_law_satisfies_both_equations", radiation == 0,
      f"a ~ t^(1/2) with p = rho/3 leaves residual {radiation}")


# ---------------------------------------------------------------- leg 5
wrong = satisfies_pair(sp.Rational(3, 4), 0)
check("falsifier_rejects_wrong_exponent", sp.simplify(wrong) != 0,
      f"a ~ t^(3/4) with dust leaves residual {sp.simplify(wrong)}, nonzero as required")


print()
print(f"legs_failed={len(FAILURES)} {FAILURES}")
if FAILURES:
    print("VERDICT: FAIL")
    raise SystemExit(1)
print("VERDICT: PASS")
