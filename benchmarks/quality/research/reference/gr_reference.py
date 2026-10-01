"""Ground truth for the general-relativity cases of the research corpus.

Independent SymPy re-derivations of three results of
Dev/warp/energy_identities_ledger/outputs (planar_fast.py, shell_analytic.py,
shell_acceleration_dec.py), G = c = 1, Einstein tensor built from scratch.
Prints the truth value of every claim id.
"""
import sympy as sp


def einstein(g, X):
    ginv = g.inv()
    n = len(X)
    Gam = [[[sp.cancel(sum(ginv[a, d] * (sp.diff(g[d, b], X[c]) + sp.diff(g[d, c], X[b]) - sp.diff(g[b, c], X[d]))
                           for d in range(n)) / 2) for c in range(n)] for b in range(n)] for a in range(n)]

    def riem(a, b, c, d):
        return (sp.diff(Gam[a][b][d], X[c]) - sp.diff(Gam[a][b][c], X[d])
                + sum(Gam[a][c][e] * Gam[e][b][d] - Gam[a][d][e] * Gam[e][b][c] for e in range(n)))

    ric = sp.Matrix(n, n, lambda b, d: sp.simplify(sum(riem(a, b, a, d) for a in range(n))))
    R = sp.simplify(sum(ginv[a, b] * ric[a, b] for a in range(n) for b in range(n)))
    return sp.simplify(ric - R * g / 2), ginv


results = {}

# --- E1/E2: planar shift wall ---------------------------------------------
t, x, y, z = sp.symbols("t x y z", real=True)
b = sp.Function("b")(t, x)
g = sp.zeros(4)
g[0, 0] = -1 + b**2
g[0, 1] = g[1, 0] = -b
g[1, 1] = g[2, 2] = g[3, 3] = 1
G, _ = einstein(g, [t, x, y, z])
nvec = sp.Matrix([1, b, 0, 0])
rho = sp.simplify((nvec.T * G * nvec)[0] / (8 * sp.pi))
p_perp = sp.simplify(G[2, 2] / (8 * sp.pi))
target = -sp.diff(sp.diff(b, t) + b * sp.diff(b, x), x) / (8 * sp.pi)
results["gr_planar_wall_true"] = (rho == 0 and sp.simplify(G[2, 2] - G[3, 3]) == 0
                                  and sp.simplify(p_perp - target) == 0 and sp.simplify(G[1, 1]) == 0)
results["gr_planar_wall_rho_false"] = sp.simplify(rho + sp.diff(b, x)**2 / (16 * sp.pi)) == 0
print("planar: rho =", rho, "| G_xx =", sp.simplify(G[1, 1]), "| p_perp - target =", sp.simplify(p_perp - target))

# --- E3/E4: static spherical shell with p_r = 0 ----------------------------
T, R, th, ph = sp.symbols("T R theta phi", positive=True)
m = sp.Function("m")(R)
N = sp.Function("N")(R)
g = sp.diag(-N**2, 1 / (1 - 2 * m / R), R**2, R**2 * sp.sin(th)**2)
G, ginv = einstein(g, [T, R, th, ph])
Gmix = sp.simplify(ginv * G)
rho = sp.simplify(-Gmix[0, 0] / (8 * sp.pi))
pr = sp.simplify(Gmix[1, 1] / (8 * sp.pi))
pt = sp.simplify(Gmix[2, 2] / (8 * sp.pi))
q = m / (R * (R - 2 * m))
pr0 = sp.simplify(pr.subs(sp.Derivative(N, R), N * q))
pt0 = sp.simplify(pt.subs(sp.Derivative(N, (R, 2)), N * (q**2 + sp.diff(q, R))).subs(sp.Derivative(N, R), N * q))
ratio = sp.simplify(pt0 / rho)
results["gr_static_shell_true"] = (sp.simplify(rho - sp.diff(m, R) / (4 * sp.pi * R**2)) == 0 and pr0 == 0
                                   and sp.simplify(pt0 - rho * m / (2 * (R - 2 * m))) == 0
                                   and sp.simplify(ratio - m / (2 * (R - 2 * m))) == 0)
# DEC p_perp <= rho  <=>  m/(2(R-2m)) <= 1  <=>  2m/R <= 4/5 ; the seeded threshold 2/3 is false.
mu = sp.symbols("mu", positive=True)  # mu = 2m/R
ratio_mu = sp.simplify(ratio.subs(m, mu * R / 2))
results["gr_static_shell_dec_false"] = sp.simplify(sp.solve(sp.Eq(ratio_mu, 1), mu)[0] - sp.Rational(2, 3)) == 0
print("shell: rho =", rho, "| p_perp/rho =", ratio, "| DEC threshold mu =", sp.solve(sp.Eq(ratio_mu, 1), mu))

# --- E5/E6: Kinnersley photon rocket ----------------------------------------
u, r = sp.symbols("u r", real=True)
mm = sp.Function("m")(u)
aa = sp.Function("a")(u)
g = sp.zeros(4)
g[0, 0] = -(1 - 2 * mm / r - 2 * aa * r * sp.cos(th) - aa**2 * r**2 * sp.sin(th)**2)
g[0, 1] = g[1, 0] = -1
g[0, 2] = g[2, 0] = aa * r**2 * sp.sin(th)
g[2, 2] = r**2
g[3, 3] = r**2 * sp.sin(th)**2
G, _ = einstein(g, [u, r, th, ph])
G_uu = sp.simplify(G[0, 0])
others = [sp.simplify(G[i, j]) for i in range(4) for j in range(i, 4) if (i, j) != (0, 0)]
expected = 2 * (3 * mm * aa * sp.cos(th) - sp.diff(mm, u)) / r**2
results["gr_kinnersley_true"] = sp.simplify(G_uu - expected) == 0 and all(o == 0 for o in others)
results["gr_kinnersley_sign_false"] = sp.simplify(G_uu + expected) == 0
print("kinnersley: G_uu =", G_uu, "| others zero:", all(o == 0 for o in others))

# --- H1/H2: unit-lapse static shift (hollow-source construction) ------------
# Dev/warp/hollow-core-energy-conditions-reproducibility/derivations/verify_obstruction.py
tt, rr = sp.symbols("t r", real=True)
beta = sp.Function("beta")(rr)
g = sp.zeros(4)
g[0, 0] = -1 + beta**2
g[0, 1] = g[1, 0] = -beta
g[1, 1] = 1
g[2, 2] = rr**2
g[3, 3] = rr**2 * sp.sin(th)**2
G, ginv = einstein(g, [tt, rr, th, ph])
nvec = sp.Matrix([1, beta, 0, 0])
rho_h = sp.simplify((nvec.T * G * nvec)[0] / (8 * sp.pi))
# radial pressure measured by the Eulerian observer: p_r = G(e_r, e_r)/8pi with e_r = d/dr (unit, orthogonal to n)
e_r = sp.Matrix([0, 1, 0, 0])
pr_h = sp.simplify((e_r.T * G * e_r)[0] / (8 * sp.pi))
flux_h = sp.simplify(-(nvec.T * G * e_r)[0] / (8 * sp.pi))
rho_expected = beta * (2 * rr * sp.diff(beta, rr) + beta) / (8 * sp.pi * rr**2)
results["gr_unit_lapse_shell_true"] = (sp.simplify(rho_h - rho_expected) == 0 and sp.simplify(pr_h + rho_h) == 0 and flux_h == 0)
results["gr_unit_lapse_shell_pr_false"] = sp.simplify(pr_h - rho_h) == 0
print("unit-lapse: rho =", rho_h, "| p_r + rho =", sp.simplify(pr_h + rho_h), "| flux =", flux_h)

for k, v in results.items():
    print(f"{k}: {'TRUE' if v else 'FALSE'}")
