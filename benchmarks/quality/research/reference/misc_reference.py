"""Ground truth for the quench, rocket, harmonic-gradient and SU(N) cases.

Independent derivations (SymPy / NumPy) of results recorded in
Dev/physics/quenched-scalar-field-keldysh-wigner-wavelet (Bogoliobov
coefficients of a sudden mass quench), Dev/warp/high_speed_subluminal_warp
(outputs/unified_theorem_checks_20260918_local.json, theorems B and D) and
Dev/physics/spectral-smarr-sun/validate_spectral_smarr.py. Prints the truth
value of every claim id.
"""
import numpy as np
import sympy as sp

results = {}

# --- Q1..Q4: sudden mass quench of a free scalar mode ----------------------
k, mi, d = sp.symbols("k m_i d", positive=True)
mf = mi + d
wi = sp.sqrt(k**2 + mi**2)
wf = sp.sqrt(k**2 + mf**2)
alpha = (wf + wi) / (2 * sp.sqrt(wi * wf))
beta = (wf - wi) / (2 * sp.sqrt(wi * wf))
nk = sp.simplify(beta**2)
results["quench_bogoliubov_uv_true"] = (sp.simplify(alpha**2 - beta**2 - 1) == 0
                                        and sp.simplify(sp.limit(nk * k**4, k, sp.oo) - (mf**2 - mi**2)**2 / 16) == 0)
results["quench_uv_coefficient_false"] = sp.simplify(sp.limit(nk * k**4, k, sp.oo) - (mf**2 - mi**2)**2 / 8) == 0
# Q3: n_k > 0 for every real k, strictly decreasing in |k|, limit d^2/(4 m_i m_f) at k -> 0.
dn = sp.simplify(sp.diff(nk, k))
samples = [(float(mi_), float(d_), float(k_)) for mi_ in (0.3, 1.0, 2.5) for d_ in (0.1, 1.0, 3.0) for k_ in (0.01, 0.5, 2.0, 10.0)]
nk_f = sp.lambdify((k, mi, d), nk, "numpy")
dn_f = sp.lambdify((k, mi, d), dn, "numpy")
positive = all(nk_f(k_, mi_, d_) > 0 for mi_, d_, k_ in samples)
decreasing = all(dn_f(k_, mi_, d_) < 0 for mi_, d_, k_ in samples)
limit0 = sp.simplify(sp.limit(nk, k, 0) - d**2 / (4 * mi * mf)) == 0
results["quench_occupation_monotone_true"] = positive and decreasing and limit0
results["quench_occupation_vanishes_at_zero_false"] = sp.simplify(sp.limit(nk, k, 0)) == 0
print("quench: n_k =", nk, "| k^4 n_k ->", sp.limit(nk * k**4, k, sp.oo), "| n_0 ->", sp.limit(nk, k, 0))
# v1.2: one proposition per case. The derivative has the exact closed form
# dn/dk = -k (m_f^2 - m_i^2)^2 / (4 ((k^2+m_i^2)(k^2+m_f^2))^(3/2)), negative for k > 0.
dn_closed = -k * (mf**2 - mi**2)**2 / (4 * ((k**2 + mi**2) * (k**2 + mf**2))**sp.Rational(3, 2))
results["quench_normalization_true"] = sp.simplify(alpha**2 - beta**2 - 1) == 0
results["quench_uv_limit_true"] = sp.simplify(sp.limit(nk * k**4, k, sp.oo) - (mf**2 - mi**2)**2 / 16) == 0
results["quench_occupation_decreasing_true"] = sp.simplify(dn - dn_closed) == 0 and decreasing
results["quench_occupation_limit_true"] = limit0
print("quench: dn/dk - closed form =", sp.simplify(dn - dn_closed))

# --- R1/R2: relativistic rocket mass ratio vs rapidity ----------------------
# Exhaust of speed w (0 < w <= 1, c = 1) ejected backward in the instantaneous
# rest frame: dm/m = -dtheta/w, so m_f/m_0 = exp(-theta/w) <= exp(-theta),
# equality iff w = 1 (null exhaust). Check the closed form against a direct
# numerical integration of energy-momentum conservation.
def mass_ratio_numeric(theta, w, steps=20000):
    m = 1.0
    dth = theta / steps
    for _ in range(steps):
        # In the rest frame: dP = m dtheta (ship momentum), exhaust carries
        # momentum dP backward with energy dE = dP / w (massive exhaust: E = P / v).
        dP = m * dth
        m -= dP / w
    return m


theta = 1.2
ratios = {w: mass_ratio_numeric(theta, w) for w in (0.5, 0.8, 1.0)}
closed = {w: float(np.exp(-theta / w)) for w in ratios}
ok_closed = all(abs(ratios[w] - closed[w]) < 1e-3 for w in ratios)
results["rocket_mass_bound_true"] = ok_closed and all(ratios[w] <= np.exp(-theta) + 1e-9 for w in ratios) and abs(ratios[1.0] - np.exp(-theta)) < 1e-3
results["rocket_mass_bound_reversed_false"] = all(ratios[w] >= np.exp(-theta) - 1e-9 for w in ratios)
print("rocket: m_f/m_0 at theta=1.2:", {w: round(v, 4) for w, v in ratios.items()}, "| e^-theta =", round(float(np.exp(-theta)), 4))
# v1.2: one proposition per case.
results["rocket_bound_true"] = all(ratios[w] <= np.exp(-theta) + 1e-9 for w in ratios) and abs(ratios[1.0] - np.exp(-theta)) < 1e-3
results["rocket_constant_w_true"] = ok_closed
results["rocket_constant_w_false"] = all(abs(ratios[w] - np.exp(-theta * w)) < 1e-3 for w in ratios)   # seeded: exp(-theta w) instead of exp(-theta / w)

# --- D1/D2: gradient of a harmonic function is subharmonic ------------------
x, y, z = sp.symbols("x y z", real=True)
# Generic harmonic test functions: Delta|grad a|^2 == 2 |Hess a|^2 for every harmonic a.
tests = [x**2 - y**2 + 3 * x * z, x**3 - 3 * x * y**2 + z, sp.exp(x) * sp.cos(y) + x * y * z, 1 / sp.sqrt(x**2 + y**2 + z**2)]
lap = lambda f: sp.diff(f, x, 2) + sp.diff(f, y, 2) + sp.diff(f, z, 2)
ident = []
for a in tests:
    assert sp.simplify(lap(a)) == 0
    grad2 = sum(sp.diff(a, v)**2 for v in (x, y, z))
    hess2 = sum(sp.diff(a, v, w)**2 for v in (x, y, z) for w in (x, y, z))
    ident.append(sp.simplify(lap(grad2) - 2 * hess2) == 0)
results["harmonic_gradient_subharmonic_true"] = all(ident)
results["harmonic_gradient_factor_false"] = all(sp.simplify(lap(sum(sp.diff(a, v)**2 for v in (x, y, z))) - sum(sp.diff(a, v, w)**2 for v in (x, y, z) for w in (x, y, z))) == 0 for a in tests)
print("harmonic: Delta|grad a|^2 - 2|Hess a|^2 == 0 on 4 harmonic tests:", all(ident))

# --- S1/S2/S3: Wu-Yang SU(2) curvature and SU(3) charge spectrum -----------
w, thv = sp.symbols("w theta", real=True)
T1 = sp.Matrix([[0, -sp.I / 2], [-sp.I / 2, 0]])
T2 = sp.Matrix([[0, -sp.Rational(1, 2)], [sp.Rational(1, 2), 0]])
T3 = sp.Matrix([[-sp.I / 2, 0], [0, sp.I / 2]])
Ath = w * T1
Aph = w * sp.sin(thv) * T2 + sp.cos(thv) * T3
F = sp.simplify(sp.diff(Aph, thv) + (Ath * Aph - Aph * Ath))
results["su2_wu_yang_curvature_true"] = sp.simplify(F - (w**2 - 1) * sp.sin(thv) * T3) == sp.zeros(2)
results["su2_wu_yang_curvature_sign_false"] = sp.simplify(F - (1 - w**2) * sp.sin(thv) * T3) == sp.zeros(2)
q3, q8 = sp.symbols("q3 q8", real=True)
T3s = -sp.I * sp.diag(1, -1, 0) / 2
T8s = -sp.I * sp.diag(1, 1, -2) / (2 * sp.sqrt(3))
Q = 4 * sp.pi * (q3 * T3s + q8 * T8s)
expected = {-2 * sp.pi * sp.I * (q3 + q8 / sp.sqrt(3)), 2 * sp.pi * sp.I * (q3 - q8 / sp.sqrt(3)), 4 * sp.pi * sp.I * q8 / sp.sqrt(3)}
actual = list(Q.eigenvals().keys())
results["su3_charge_spectrum_true"] = all(any(sp.simplify(a - e) == 0 for e in expected) for a in actual) and sp.simplify(sum(expected)) == 0
# v1.2 seeded false: third eigenvalue with half the coefficient.
expected_false = {-2 * sp.pi * sp.I * (q3 + q8 / sp.sqrt(3)), 2 * sp.pi * sp.I * (q3 - q8 / sp.sqrt(3)), 2 * sp.pi * sp.I * q8 / sp.sqrt(3)}
results["su3_charge_spectrum_false"] = all(any(sp.simplify(a - e) == 0 for e in expected_false) for a in actual)
print("su2 F_theta_phi =", F, "| su3 eigenvalues:", actual)

for key, val in results.items():
    print(f"{key}: {'TRUE' if val else 'FALSE'}")
