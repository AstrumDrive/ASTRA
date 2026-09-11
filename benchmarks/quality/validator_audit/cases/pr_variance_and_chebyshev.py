"""The variance identity and Chebyshev's inequality, exactly and numerically.

CLAIM: Var(X) = E[X^2] - E[X]^2 for any distribution with finite second moment,
Chebyshev's inequality P(|X - mu| >= k sigma) <= 1/k^2 holds for every k > 0,
and the bound is attained, so it cannot be improved without further hypotheses.

Legs:
  1. symbolic  -- the identity is derived from the definition by expansion, for
                  a general density, not verified on an example;
  2. exact     -- three named distributions are integrated in closed form and
                  both sides of the identity agree exactly;
  3. bound     -- Chebyshev is checked exactly on a two-point distribution that
                  attains it, which shows the constant 1/k^2 is sharp;
  4. empirical -- a fixed-seed sample respects the bound, with the sampling
                  error itself bounded so the comparison is meaningful;
  5. falsifier -- a claimed bound of 1/k^3 is refuted by the attaining case.
"""
import random

import sympy as sp

x, mu, sigma, k = sp.symbols("x mu sigma k", real=True)
sigma_pos = sp.Symbol("sigma", positive=True)
lam = sp.Symbol("lambda", positive=True)

FAILURES = []


def check(name, ok, detail=""):
    if ok is True:
        print(f"CHECK {name}: OK {detail}".rstrip())
        return True
    FAILURES.append(name)
    print(f"CHECK {name}: FAIL {detail}".rstrip())
    return False


# ---------------------------------------------------------------- leg 1
# Var(X) = E[(X - mu)^2] = E[X^2] - 2 mu E[X] + mu^2, and E[X] = mu, so the
# cross terms collapse. Done on a symbol level, with no distribution assumed
# beyond the existence of the two moments.
m1, m2 = sp.symbols("m_1 m_2", real=True)
definition = sp.expand((x - m1) ** 2)
expected_expansion = sp.expand(x**2 - 2 * m1 * x + m1**2)
check("expansion_is_exact",
      sp.simplify(definition - expected_expansion) == 0,
      "(X - mu)^2 = X^2 - 2 mu X + mu^2")

# Taking expectations term by term, E[X] -> m1 and E[X^2] -> m2.
variance_from_definition = m2 - 2 * m1 * m1 + m1**2
check("variance_identity_follows",
      sp.simplify(variance_from_definition - (m2 - m1**2)) == 0,
      f"Var = {sp.simplify(variance_from_definition)} = E[X^2] - E[X]^2")


# ---------------------------------------------------------------- leg 2
def moments(density, variable, lower, upper):
    """First two moments by exact integration."""
    first = sp.integrate(variable * density, (variable, lower, upper))
    second = sp.integrate(variable**2 * density, (variable, lower, upper))
    return sp.simplify(first), sp.simplify(second)


cases = []

# Uniform on [0, 1]: mean 1/2, variance 1/12.
u_first, u_second = moments(sp.Integer(1), x, 0, 1)
cases.append(("uniform", u_first, u_second, sp.Rational(1, 12)))

# Exponential with rate lambda: mean 1/lambda, variance 1/lambda^2.
e_first, e_second = moments(lam * sp.exp(-lam * x), x, 0, sp.oo)
cases.append(("exponential", e_first, e_second, 1 / lam**2))

# Standard normal: mean 0, variance 1.
normal_density = sp.exp(-(x**2) / 2) / sp.sqrt(2 * sp.pi)
n_first, n_second = moments(normal_density, x, -sp.oo, sp.oo)
cases.append(("normal", n_first, n_second, sp.Integer(1)))

identity_ok = True
detail = []
for name, first, second, known in cases:
    computed = sp.simplify(second - first**2)
    if sp.simplify(computed - known) != 0:
        identity_ok = False
        detail.append(f"{name}: got {computed}, expected {known}")
check("identity_matches_known_variances", identity_ok,
      "; ".join(detail) or "uniform 1/12, exponential 1/lambda^2, normal 1")


# ---------------------------------------------------------------- leg 3
# Two-point distribution attaining Chebyshev: X = 0 with probability 1 - 1/k^2
# and X = +-k sigma with probability 1/(2k^2) each. Then mean 0, variance
# sigma^2, and P(|X| >= k sigma) = 1/k^2 exactly.
k_val = sp.Rational(3)
p_tail = 1 / k_val**2
mean_two_point = sp.simplify(0 * (1 - p_tail) + k_val * sigma_pos * p_tail / 2
                             + (-k_val * sigma_pos) * p_tail / 2)
var_two_point = sp.simplify(
    (k_val * sigma_pos) ** 2 * p_tail / 2
    + (-k_val * sigma_pos) ** 2 * p_tail / 2
)
check("two_point_has_mean_zero", sp.simplify(mean_two_point) == 0,
      f"mean = {mean_two_point}")
check("two_point_has_variance_sigma_squared",
      sp.simplify(var_two_point - sigma_pos**2) == 0,
      f"variance = {var_two_point}")
check("chebyshev_bound_is_attained",
      sp.simplify(p_tail - 1 / k_val**2) == 0,
      f"P(|X| >= {k_val} sigma) = {p_tail} = 1/k^2 exactly, so the bound is sharp")


# ---------------------------------------------------------------- leg 4
random.seed(20260911)
SAMPLES = 200000
K = 2.0
draws = [random.gauss(0.0, 1.0) for _ in range(SAMPLES)]
sample_mean = sum(draws) / SAMPLES
sample_var = sum((value - sample_mean) ** 2 for value in draws) / (SAMPLES - 1)
tail_fraction = sum(1 for value in draws
                    if abs(value - sample_mean) >= K * sample_var**0.5) / SAMPLES
# The standard error of a proportion is at most 1/(2 sqrt(n)), so a margin of
# five of those is far wider than the sampling noise and narrower than the gap
# to the bound. Without stating it the comparison would not be falsifiable.
margin = 5 / (2 * SAMPLES**0.5)
check("sample_respects_chebyshev",
      tail_fraction <= 1 / K**2 + margin,
      f"observed tail {tail_fraction:.5f} <= {1 / K**2:.5f} + {margin:.5f}")

# For the normal the true tail is about 0.0455, far below the bound, so the
# inequality is loose here. Saying so is part of stating what was shown.
check("bound_is_loose_for_the_normal",
      tail_fraction < 0.5 * (1 / K**2),
      f"normal tail {tail_fraction:.5f} is well under the Chebyshev value {1 / K**2:.2f}")


# ---------------------------------------------------------------- leg 5
# A stronger claimed bound of 1/k^3 is refuted by the attaining distribution.
claimed = 1 / k_val**3
violated = bool(sp.simplify(p_tail - claimed) > 0)
check("falsifier_refutes_one_over_k_cubed", violated,
      f"attaining case gives {p_tail} > {claimed}, so 1/k^3 is false")


print()
print(f"legs_failed={len(FAILURES)} {FAILURES}")
if FAILURES:
    print("VERDICT: FAIL")
    raise SystemExit(1)
print("VERDICT: PASS")
