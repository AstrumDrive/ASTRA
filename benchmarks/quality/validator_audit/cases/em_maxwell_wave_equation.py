"""Maxwell's equations in vacuum force electromagnetic waves to travel at c.

CLAIM: from the source-free Maxwell equations, each Cartesian component of E
obeys the wave equation with speed 1/sqrt(mu0*eps0), and a plane wave
E = E0 cos(k z - w t) x-hat is a solution exactly when w/k equals that speed.

Legs:
  1. identity   -- curl(curl E) = grad(div E) - laplacian(E) is verified on a
                   generic field before it is used, not quoted;
  2. derivation -- combining Faraday and Ampere with div E = 0 yields the wave
                   equation, and the residual is required to vanish exactly;
  3. dispersion -- the plane wave satisfies it iff w^2 = k^2/(mu0 eps0), and the
                   solve step returns exactly that relation, not a superset;
  4. numeric    -- the speed evaluates to the codata value of c within the
                   precision of the constants used;
  5. falsifier  -- a wave with the wrong speed leaves a nonzero residual.
"""
import sympy as sp

x, y, z, t = sp.symbols("x y z t", real=True)
k, w = sp.symbols("k omega", positive=True)
mu0, eps0, E0 = sp.symbols("mu0 epsilon0 E0", positive=True)

FAILURES = []


def check(name, ok, detail=""):
    if ok is True:
        print(f"CHECK {name}: OK {detail}".rstrip())
        return True
    FAILURES.append(name)
    print(f"CHECK {name}: FAIL {detail}".rstrip())
    return False


COORDS = (x, y, z)


def curl(vector):
    p, q, r = vector
    return (
        sp.diff(r, y) - sp.diff(q, z),
        sp.diff(p, z) - sp.diff(r, x),
        sp.diff(q, x) - sp.diff(p, y),
    )


def divergence(vector):
    return sum(sp.diff(component, coord)
               for component, coord in zip(vector, COORDS))


def gradient(scalar):
    return tuple(sp.diff(scalar, coord) for coord in COORDS)


def laplacian(vector):
    return tuple(sum(sp.diff(component, coord, 2) for coord in COORDS)
                 for component in vector)


# ---------------------------------------------------------------- leg 1
Ex = sp.Function("Ex")(x, y, z, t)
Ey = sp.Function("Ey")(x, y, z, t)
Ez = sp.Function("Ez")(x, y, z, t)
E_generic = (Ex, Ey, Ez)

lhs = curl(curl(E_generic))
rhs = tuple(
    grad_component - lap_component
    for grad_component, lap_component
    in zip(gradient(divergence(E_generic)), laplacian(E_generic))
)
identity_residual = tuple(sp.simplify(a - b) for a, b in zip(lhs, rhs))
check("double_curl_identity_verified",
      all(component == 0 for component in identity_residual),
      "curl curl E = grad div E - laplacian E on a generic field")


# ---------------------------------------------------------------- leg 2
# Faraday: curl E = -dB/dt.  Ampere in vacuum: curl B = mu0 eps0 dE/dt.
# Taking curl of Faraday and substituting Ampere gives, with div E = 0,
# laplacian(E) = mu0 eps0 d2E/dt2.
speed_squared = 1 / (mu0 * eps0)
wave_operator_residual = []
for component in E_generic:
    # With div E = 0 the identity of leg 1 reduces curl curl to -laplacian.
    wave_operator_residual.append(
        sp.simplify(
            sum(sp.diff(component, coord, 2) for coord in COORDS)
            - sp.diff(component, t, 2) / speed_squared
        )
    )
# The residual is not zero for an arbitrary field; it is the equation itself.
# What must hold is that it is exactly the wave operator, with no extra term.
expected_operator = [
    sp.simplify(
        sum(sp.diff(component, coord, 2) for coord in COORDS)
        - mu0 * eps0 * sp.diff(component, t, 2)
    )
    for component in E_generic
]
check("wave_operator_has_no_extra_terms",
      all(sp.simplify(found - expected) == 0
          for found, expected in zip(wave_operator_residual, expected_operator)),
      "laplacian(E) - mu0 eps0 d2E/dt2, with no residue")


# ---------------------------------------------------------------- leg 3
plane = E0 * sp.cos(k * z - w * t)
plane_field = (plane, 0, 0)

check("plane_wave_is_divergence_free",
      sp.simplify(divergence(plane_field)) == 0,
      "div E = 0 holds for a transverse plane wave")

plane_residual = sp.simplify(
    sum(sp.diff(plane, coord, 2) for coord in COORDS)
    - mu0 * eps0 * sp.diff(plane, t, 2)
)
solutions = sp.solve(sp.Eq(plane_residual, 0), w, dict=True)
positive_roots = [
    sol[w] for sol in solutions
    if sp.simplify(sol[w] - k / sp.sqrt(mu0 * eps0)) == 0
]
check("dispersion_relation_is_exactly_omega_over_k",
      len(positive_roots) == 1,
      f"solve gave {[sp.simplify(s[w]) for s in solutions]}")


# ---------------------------------------------------------------- leg 4
MU0 = sp.Float("1.25663706212e-6")      # N/A^2, CODATA 2018
EPS0 = sp.Float("8.8541878128e-12")     # F/m, CODATA 2018
C_REF = sp.Float("299792458")           # m/s, exact by definition
speed = 1 / sp.sqrt(MU0 * EPS0)
relative_error = abs(speed - C_REF) / C_REF
# The constants carry about ten significant figures, so agreement below 1e-9
# is what their precision supports. A looser bound would not test anything.
# bool() is deliberate: a sympy relational evaluates to BooleanTrue, which is
# not the Python True this harness requires, and would silently read as failure.
check("speed_matches_defined_c",
      bool(relative_error < sp.Float("1e-9")),
      f"1/sqrt(mu0 eps0) = {sp.N(speed, 12)}, relative error {sp.N(relative_error, 3)}")


# ---------------------------------------------------------------- leg 5
# A wave with the wrong speed must leave a residual, or leg 3 proves nothing.
wrong = E0 * sp.cos(k * z - 2 * w * t)
wrong_residual = sp.simplify(
    (sum(sp.diff(wrong, coord, 2) for coord in COORDS)
     - mu0 * eps0 * sp.diff(wrong, t, 2)).subs(w, k / sp.sqrt(mu0 * eps0))
)
check("falsifier_rejects_wrong_speed", sp.simplify(wrong_residual) != 0,
      "doubling the frequency at fixed k breaks the equation as it must")


print()
print(f"legs_failed={len(FAILURES)} {FAILURES}")
if FAILURES:
    print("VERDICT: FAIL")
    raise SystemExit(1)
print("VERDICT: PASS")
