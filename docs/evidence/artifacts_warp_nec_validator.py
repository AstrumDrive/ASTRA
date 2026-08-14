"""NEC test for the traveling-wave warp configuration conjectured by ASTRA.

Cycle cycle_20260814_031010_f2fa formed this consensus conjecture but its
translator phase timed out before writing a validator, so this artifact
implements the protocol the conjecture itself specified.

Configuration (G = c = 1, signature -+++):

    xi = x - v t,  rho^2 = y^2 + z^2,  r^2 = xi^2 + rho^2
    f      = 1 / (1 + (r^2/R^2)^2)
    alpha  = 1 + f/4        beta^x = -f/2        psi = 1 + f/5
    ds^2 = -alpha^2 dt^2 + psi^4 [ (dx + beta^x dt)^2 + dy^2 + dz^2 ]

Decisive claim: the NEC is violated at the wall point p = (0, 0, R, 0),

    m_p = min_{|s|=1} T_uv k^u(s) k^v(s) < 0,
    k^u(s) = n^u + s_i e_i^u   (future null, Eulerian-normalised)

Method. The curvature at a point depends only on g, dg and ddg AT that point,
so every derivative is taken symbolically and evaluated at p immediately, and
the Christoffels, their derivatives and the Ricci tensor are assembled from
those exact rationals. Carrying full symbolic Christoffels instead makes the
rational expressions grow until the process is killed for memory - which is
what happened on the first attempt here. Differentiation still strictly
precedes substitution, which is the requirement that matters.
"""
import sympy as sp

t, x, y, z = sp.symbols("t x y z", real=True)
COORDS = (t, x, y, z)
v = sp.Rational(1, 2)


def metric(Rval):
    xi = x - v * t
    r2 = xi**2 + y**2 + z**2
    f = 1 / (1 + (r2 / Rval**2) ** 2)
    alpha = 1 + f / 4
    betax = -f / 2
    psi4 = (1 + f / 5) ** 4
    g = sp.zeros(4, 4)
    g[0, 0] = -(alpha**2) + psi4 * betax**2
    g[0, 1] = g[1, 0] = psi4 * betax
    g[1, 1] = psi4
    g[2, 2] = psi4
    g[3, 3] = psi4
    return g


def exact_curvature(Rval):
    """Return (g, G) evaluated exactly at p = (0, 0, R, 0)."""
    g_sym = metric(Rval)
    point = {t: 0, x: 0, y: Rval, z: 0}

    def val(expr):
        return sp.nsimplify(sp.together(expr.subs(point)))

    g = sp.Matrix(4, 4, lambda i, j: val(g_sym[i, j]))
    dg = [[[val(sp.diff(g_sym[i, j], COORDS[a])) for a in range(4)]
           for j in range(4)] for i in range(4)]
    ddg = [[[[val(sp.diff(g_sym[i, j], COORDS[a], COORDS[b]))
              for b in range(4)] for a in range(4)]
            for j in range(4)] for i in range(4)]

    ginv = g.inv()
    # d(g^{ij})/dx^a = -g^{im} (d g_{mn}/dx^a) g^{nj}
    dginv = [[[sum(-ginv[i, m] * dg[m][n][a] * ginv[n, j]
                   for m in range(4) for n in range(4))
               for a in range(4)] for j in range(4)] for i in range(4)]

    def Gam(a, b, c):
        return sp.Rational(1, 2) * sum(
            ginv[a, d] * (dg[d][b][c] + dg[d][c][b] - dg[b][c][d])
            for d in range(4)
        )

    def dGam(e, a, b, c):
        first = sp.Rational(1, 2) * sum(
            dginv[a][d][e] * (dg[d][b][c] + dg[d][c][b] - dg[b][c][d])
            for d in range(4)
        )
        second = sp.Rational(1, 2) * sum(
            ginv[a, d] * (ddg[d][b][c][e] + ddg[d][c][b][e] - ddg[b][c][d][e])
            for d in range(4)
        )
        return sp.simplify(first + second)

    G_ = [[[sp.simplify(Gam(a, b, c)) for c in range(4)] for b in range(4)]
          for a in range(4)]
    dG_ = [[[[dGam(e, a, b, c) for c in range(4)] for b in range(4)]
            for a in range(4)] for e in range(4)]

    Ric = sp.zeros(4, 4)
    for b in range(4):
        for c in range(b, 4):
            expr = sum(dG_[a][a][b][c] for a in range(4))
            expr -= sum(dG_[c][a][b][a] for a in range(4))
            expr += sum(G_[a][a][d] * G_[d][b][c]
                        for a in range(4) for d in range(4))
            expr -= sum(G_[a][c][d] * G_[d][b][a]
                        for a in range(4) for d in range(4))
            Ric[b, c] = Ric[c, b] = sp.simplify(expr)

    Rs = sp.simplify(sum(ginv[i, j] * Ric[i, j]
                         for i in range(4) for j in range(4)))
    Gt = sp.Matrix(4, 4, lambda i, j: sp.simplify(Ric[i, j] - g[i, j] * Rs / 2))
    return g, Gt


def run(Rval):
    print(f"--- R = {Rval} ---", flush=True)
    g, Gt = exact_curvature(Rval)

    f_p, alpha_p, psi_p, betax_p = (
        sp.Rational(1, 2), sp.Rational(9, 8),
        sp.Rational(11, 10), sp.Rational(-1, 4),
    )
    n = sp.Matrix([1 / alpha_p, -betax_p / alpha_p, 0, 0])
    e = [sp.Matrix([0, 1 / psi_p**2, 0, 0]),
         sp.Matrix([0, 0, 1 / psi_p**2, 0]),
         sp.Matrix([0, 0, 0, 1 / psi_p**2])]

    def ip(u, w):
        return sp.simplify((u.T * g * w)[0, 0])

    ok_tetrad = (
        sp.simplify(ip(n, n) + 1) == 0
        and all(sp.simplify(ip(n, ei)) == 0 for ei in e)
        and all(sp.simplify(ip(e[i], e[j]) - (1 if i == j else 0)) == 0
                for i in range(3) for j in range(3))
    )
    print(f"CHECK eulerian tetrad orthonormal: {'OK' if ok_tetrad else 'FAIL'}",
          flush=True)
    if not ok_tetrad:
        return None

    s1, s2, s3 = sp.symbols("s1 s2 s3", real=True)
    k = n + s1 * e[0] + s2 * e[1] + s3 * e[2]
    N = sp.expand(sp.simplify((k.T * Gt * k)[0, 0]))
    print(f"8*pi*T contraction N(s) = {N}", flush=True)

    lam = sp.symbols("lam", real=True)
    L = N - lam * (s1**2 + s2**2 + s3**2 - 1)
    sols = sp.solve(
        [sp.diff(L, u) for u in (s1, s2, s3)] + [s1**2 + s2**2 + s3**2 - 1],
        [s1, s2, s3, lam], dict=True,
    )
    values = []
    for sol in sols:
        pt = {u: sol.get(u) for u in (s1, s2, s3) if u in sol}
        if len(pt) < 3 or any(not sp.im(w).is_zero for w in pt.values()):
            continue
        values.append((sp.simplify(N.subs(sol)), pt))
    if not values:
        print("CHECK exact minimisation: FAIL (no real stationary point)")
        return None

    values.sort(key=lambda pair: sp.N(pair[0]))
    m_p, s_star = values[0]
    print(f"CHECK real stationary points: {len(values)}", flush=True)
    print(f"m_p = {m_p}   (~ {sp.N(m_p, 20)})", flush=True)
    print(f"argmin s* = { {str(u): sp.nsimplify(w) for u, w in s_star.items()} }",
          flush=True)
    violated = sp.simplify(m_p) < 0
    print(f"CHECK NEC violated at p: {'YES' if violated else 'NO'}", flush=True)
    return m_p, s_star, bool(violated)


if __name__ == "__main__":
    a = run(sp.Integer(1))
    print(flush=True)
    b = run(sp.Integer(2))
    print(flush=True)
    if a is None or b is None:
        print("VERDICT: FAIL")
    else:
        same = a[2] == b[2]
        print(f"CHECK sign independent of R: {'OK' if same else 'FAIL'}")
        print("RESULT: NEC VIOLATED at p -> conjecture SUPPORTED" if a[2]
              else "RESULT: NEC HOLDS at p -> conjecture REFUTED at p")
        print("VERDICT: PASS" if same else "VERDICT: FAIL")
