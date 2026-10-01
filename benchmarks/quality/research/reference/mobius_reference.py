"""Ground truth for the Möbius-strip Nagaoka cases by exact diagonalization.

Independent of Dev/physics/mobius_geometric_spin_transport: one hole in the
infinite-U Hubbard model on the square strip G(N, W, b) with longitudinal
closure (N, m) ~ (0, r_b(m)), r_0(m) = m (cylinder), r_1(m) = W - 1 - m
(Möbius), flat U(1) link variables with Aharonov-Bohm holonomy exp(2 pi i phi)
around one longitudinal winding. The theorem in MOBIUS_NAGAOKA_THEOREM.md
predicts a saturated-spin, unique ground state when 2 phi = N + b (W - 1)
(mod 2). Hilbert space: hole position x electrons' spins, dim = NW * 2^(NW-1).
"""
import itertools

import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import eigsh


def bonds(N, W, b, phi):
    """Directed bonds (x, y, hop phase) of G(N, W, b) with the flux on the seam."""
    out = []
    for n in range(N):
        for m in range(W):
            if m + 1 < W:
                out.append(((n, m), (n, m + 1), 1.0))
            if n + 1 < N:
                out.append(((n, m), (n + 1, m), 1.0))
            else:  # seam (N-1, m) -> (0, r_b(m)) carries the holonomy
                mm = m if b == 0 else W - 1 - m
                out.append(((n, m), (0, mm), np.exp(2j * np.pi * phi)))
    return out


def ground_state_spin(N, W, b, phi):
    sites = [(n, m) for n in range(N) for m in range(W)]
    idx = {s: i for i, s in enumerate(sites)}
    L = len(sites)
    ne = L - 1
    # basis: hole position h, spin configuration of the ne electrons listed in
    # site order skipping h; encode spins as a bitmask over the ne electrons.
    dim = L * 2**ne
    H = lil_matrix((dim, dim), dtype=complex)

    def state(h, spins):
        return h * 2**ne + spins

    def electrons(h):
        return [s for s in range(L) if s != h]

    for h in range(L):
        occ = electrons(h)
        for spins in range(2**ne):
            # hop the hole across every bond touching it: electron at y moves to h
            for (x, y, ph) in bonds(N, W, b, phi):
                xi, yi = idx[x], idx[y]
                for (a, c, phase) in ((xi, yi, ph), (yi, xi, np.conj(ph))):
                    if a != h:
                        continue
                    # electron at c jumps to a (= h); hole moves to c.
                    pos_c = occ.index(c)
                    spin = (spins >> pos_c) & 1
                    new_occ = electrons(c)
                    # rebuild spin mask: remove electron c, insert it at position of a
                    rest = [(s, (spins >> i) & 1) for i, s in enumerate(occ) if s != c]
                    new_spins = 0
                    for i, s in enumerate(new_occ):
                        if s == a:
                            bit = spin
                        else:
                            bit = dict(rest)[s]
                        new_spins |= bit << i
                    # fermion sign: parity of electrons between positions a and c in site order
                    lo, hi = sorted((a, c))
                    crossed = sum(1 for s in occ if lo < s < hi)
                    sign = -1.0 if crossed % 2 else 1.0
                    H[state(c, new_spins), state(h, spins)] += -1.0 * phase * sign
    H = H.tocsr()
    H = (H + H.getH()) / 2  # the construction fills both directions; symmetrize numerically
    vals, vecs = eigsh(H, k=1, which="SA")
    v = vecs[:, 0]
    # total spin from <S^2> = S_z-sector-free expectation: compute S^2 via Sz^2 + (S+S- + S-S+)/2
    Sz = np.zeros(dim)
    for h in range(L):
        for spins in range(2**ne):
            Sz[state(h, spins)] = (bin(spins).count("1") - (ne - bin(spins).count("1"))) / 2
    Splus = lil_matrix((dim, dim))
    for h in range(L):
        for spins in range(2**ne):
            for i in range(ne):
                if not (spins >> i) & 1:
                    Splus[state(h, spins | (1 << i)), state(h, spins)] += 1.0
    Splus = Splus.tocsr()
    S2 = (Splus @ Splus.getH() + Splus.getH() @ Splus) / 2
    s2 = (v.conj() @ (S2 @ v)).real + (v.conj() @ (Sz**2 * v)).real
    S = (-1 + np.sqrt(1 + 4 * s2)) / 2
    return float(vals[0]), float(S)


if __name__ == "__main__":
    N, W = 4, 2
    Smax = (N * W - 1) / 2
    results = {}
    # Möbius (b=1): 2 phi = N + (W-1) = 5 (mod 2) = 1  ->  phi = 1/2 satisfies the theorem.
    e1, s1 = ground_state_spin(N, W, 1, 0.5)
    # Möbius at phi = 0 (condition violated): the theorem makes no promise; measure.
    e0, s0 = ground_state_spin(N, W, 1, 0.0)
    # Cylinder (b=0): 2 phi = N = 4 (mod 2) = 0  -> phi = 0 satisfies it.
    ec, sc = ground_state_spin(N, W, 0, 0.0)
    print(f"mobius N={N} W={W} phi=1/2: E0={e1:.6f} S={s1:.4f} (S_max={Smax})")
    print(f"mobius N={N} W={W} phi=0  : E0={e0:.6f} S={s0:.4f}")
    print(f"cylinder N={N} W={W} phi=0: E0={ec:.6f} S={sc:.4f}")
    results["mobius_nagaoka_saturated_true"] = abs(s1 - Smax) < 1e-6
    results["mobius_nagaoka_wrong_flux_false"] = abs(s0 - Smax) < 1e-6
    for k_, v_ in results.items():
        print(f"{k_}: {'TRUE' if v_ else 'FALSE'}")
