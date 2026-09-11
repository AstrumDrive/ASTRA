"""Second-derivative identities of vector calculus, and the divergence theorem.

CLAIM: for any twice continuously differentiable field, div(curl F) = 0 and
curl(grad phi) = 0 identically, and for F = (x, y, z) the divergence theorem
gives a flux of 4*pi*a^3 through the sphere of radius a.

Legs:
  1. symbolic  -- both identities on generic undefined functions, so nothing is
                  special about a chosen example;
  2. mixed     -- the identities reduce to equality of mixed partials, which is
                  checked directly rather than assumed;
  3. integral  -- the divergence theorem on a sphere, both sides computed
                  independently and compared exactly;
  4. falsifier -- a field whose curl is not divergence free would break leg 1,
                  and a deliberately corrupted curl is shown to be detected.
"""
import sympy as sp

x, y, z, a = sp.symbols("x y z a", real=True)
a_pos = sp.Symbol("a", positive=True)

f = sp.Function("f")(x, y, z)
g = sp.Function("g")(x, y, z)
h = sp.Function("h")(x, y, z)
phi = sp.Function("phi")(x, y, z)

FAILURES = []


def check(name, ok, detail=""):
    if ok is True:
        print(f"CHECK {name}: OK {detail}".rstrip())
        return True
    FAILURES.append(name)
    print(f"CHECK {name}: FAIL {detail}".rstrip())
    return False


def curl(vector):
    p, q, r = vector
    return (
        sp.diff(r, y) - sp.diff(q, z),
        sp.diff(p, z) - sp.diff(r, x),
        sp.diff(q, x) - sp.diff(p, y),
    )


def divergence(vector):
    p, q, r = vector
    return sp.diff(p, x) + sp.diff(q, y) + sp.diff(r, z)


def gradient(scalar):
    return (sp.diff(scalar, x), sp.diff(scalar, y), sp.diff(scalar, z))


# ---------------------------------------------------------------- leg 1
F = (f, g, h)
div_curl = sp.simplify(divergence(curl(F)))
check("div_curl_vanishes_for_generic_field", div_curl == 0,
      f"div(curl F) = {div_curl}")

curl_grad = tuple(sp.simplify(component) for component in curl(gradient(phi)))
check("curl_grad_vanishes_for_generic_scalar",
      all(component == 0 for component in curl_grad),
      f"curl(grad phi) = {curl_grad}")


# ---------------------------------------------------------------- leg 2
# Both identities are the statement that mixed partials commute. Verify that
# directly on a generic function so the identities rest on something checked.
mixed = sp.simplify(sp.diff(phi, x, y) - sp.diff(phi, y, x))
check("mixed_partials_commute", mixed == 0, f"phi_xy - phi_yx = {mixed}")

# And confirm the cancellation is term by term, not an accident of collection.
p_component, q_component, r_component = F
terms = (
    sp.diff(sp.diff(r_component, y), x) - sp.diff(sp.diff(r_component, x), y),
    sp.diff(sp.diff(p_component, z), y) - sp.diff(sp.diff(p_component, y), z),
    sp.diff(sp.diff(q_component, x), z) - sp.diff(sp.diff(q_component, z), x),
)
check("cancellation_is_termwise",
      all(sp.simplify(term) == 0 for term in terms),
      "each of the three pairs cancels on its own")


# ---------------------------------------------------------------- leg 3
# Divergence theorem for F = (x, y, z) on the ball of radius a.
radial = (x, y, z)
div_radial = sp.simplify(divergence(radial))
check("radial_field_divergence_is_three", div_radial == 3,
      f"div(x,y,z) = {div_radial}")

volume_integral = sp.simplify(div_radial * sp.Rational(4, 3) * sp.pi * a_pos**3)

# Surface side, computed independently in spherical coordinates. On the sphere
# F . n = a, and the area element is a^2 sin(theta) dtheta dphi.
theta, varphi = sp.symbols("theta varphi", real=True)
flux_integrand = a_pos * a_pos**2 * sp.sin(theta)
surface_integral = sp.simplify(
    sp.integrate(
        sp.integrate(flux_integrand, (theta, 0, sp.pi)),
        (varphi, 0, 2 * sp.pi),
    )
)
check("divergence_theorem_two_sides_agree",
      sp.simplify(volume_integral - surface_integral) == 0,
      f"volume {volume_integral} vs surface {surface_integral}")

check("flux_has_expected_closed_form",
      sp.simplify(surface_integral - 4 * sp.pi * a_pos**3) == 0,
      f"flux = {surface_integral}")


# ---------------------------------------------------------------- leg 4
# The identity test must be able to fail. Corrupt one component of the curl and
# confirm the divergence no longer vanishes, so leg 1 has real discriminating
# power rather than being true by construction.
corrupted = list(curl(F))
corrupted[0] = corrupted[0] + sp.diff(f, x)
corrupted_divergence = sp.simplify(divergence(tuple(corrupted)))
check("falsifier_detects_corrupted_curl", corrupted_divergence != 0,
      f"corrupted div = {corrupted_divergence}")


print()
print(f"legs_failed={len(FAILURES)} {FAILURES}")
if FAILURES:
    print("VERDICT: FAIL")
    raise SystemExit(1)
print("VERDICT: PASS")
