"""Ground truth for the Kondo two-orbital cases of the research corpus.

Independent re-implementation (not a copy) of the exact finite-matrix model of
Dev/physics/kondo_eom_minimal_hierarchy_codex/04_tests/verify_two_orbital_algebra.py:
impurity spin-1/2 x four Jordan-Wigner fermion modes (0up, 0dn, 1up, 1dn),
dimension 32, infinite-temperature metric (A|B) = Tr{A, B^dagger} / 32.
Prints the truth value of every claim id; the corpus only keeps claims whose
printed value matches its `expected` field.
"""
import numpy as np

sx = np.array([[0, 1], [1, 0]], complex)
sy = np.array([[0, -1j], [1j, 0]], complex)
sz = np.array([[1, 0], [0, -1]], complex)
PAULI = [sx, sy, sz]
I2 = np.eye(2)
ANNIH = np.array([[0, 1], [0, 0]], complex)  # |0><1| in the (empty, filled) basis


def kron(*ops):
    out = np.eye(1, dtype=complex)
    for op in ops:
        out = np.kron(out, op)
    return out


# Jordan-Wigner on four modes, impurity spin as the leftmost factor.
modes = []
for j in range(4):
    factors = [sz] * j + [ANNIH] + [I2] * (3 - j)
    modes.append(kron(I2, *factors))
f = modes
fd = [m.conj().T for m in modes]
S = [kron(p / 2, np.eye(16)) for p in PAULI]
DIM = 32


def comm(a, b):
    return a @ b - b @ a


def metric(a, b):
    return np.trace(a @ b.conj().T + b.conj().T @ a) / DIM


def spin_density(orb):
    idx = [2 * orb, 2 * orb + 1]
    return [sum(0.5 * p[a, b] * fd[idx[a]] @ f[idx[b]] for a in range(2) for b in range(2)) for p in PAULI]


def cross(u, v):
    return [u[1] @ v[2] - u[2] @ v[1], u[2] @ v[0] - u[0] @ v[2], u[0] @ v[1] - u[1] @ v[0]]


def vec_sigma_f(vec, orb):
    """[(vec . sigma f_orb)]_sigma for sigma = up, dn."""
    idx = [2 * orb, 2 * orb + 1]
    return [sum(p[s, b] * vec[a] @ f[idx[b]] for a, p in enumerate(PAULI) for b in range(2)) for s in range(2)]


s0 = spin_density(0)
J = 1.0
HJ = J * sum(S[a] @ s0[a] for a in range(3))
B0 = vec_sigma_f(S, 0)
B1 = vec_sigma_f(S, 1)
C0 = vec_sigma_f(cross(S, s0), 0)
C1 = vec_sigma_f(cross(S, s0), 1)
n = [fd[i] @ f[i] for i in range(4)]
P2 = n[0] @ n[1]
P1 = n[0] + n[1] - 2 * P2
U1 = [B1[s] @ P1 for s in range(2)]
F1 = vec_sigma_f(s0, 1)
X1 = [U1[s] + F1[s] for s in range(2)]
Y1 = [U1[s] - F1[s] for s in range(2)]


def close(a, b, tol=1e-10):
    return np.max(np.abs(a - b)) < tol


def L(op):  # Liouvillian: L O = [O, H]
    return comm(op, HJ)


results = {}
# K1 (true): per-component infinite-temperature norms.
norms = {"B0": metric(B0[0], B0[0]).real, "B1": metric(B1[0], B1[0]).real,
         "C0": metric(C0[0], C0[0]).real, "C1": metric(C1[0], C1[0]).real}
results["kondo_norms_true"] = all(abs(norms[k] - v) < 1e-12 for k, v in
                                  {"B0": 3 / 4, "B1": 3 / 4, "C0": 3 / 8, "C1": 3 / 16}.items())
# K2 (seeded false): (C1|C1) = 3/8.
results["kondo_c1_norm_false"] = abs(norms["C1"] - 3 / 8) < 1e-12
# K3 (true): [B1, H_J] = -iJ C1, both spin components.
results["kondo_b1_commutator_true"] = all(close(L(B1[s]), -1j * J * C1[s]) for s in range(2))
# K4 (seeded false): [B1, H_J] = +iJ C1.
results["kondo_b1_commutator_sign_false"] = all(close(L(B1[s]), 1j * J * C1[s]) for s in range(2))
# K5 (true): [X1, H_J] = 0, [Y1, H_J] = -2iJ C1, [C1, H_J] = (iJ/2) Y1.
results["kondo_exchange_block_true"] = all(
    close(L(X1[s]), 0 * X1[s]) and close(L(Y1[s]), -2j * J * C1[s]) and close(L(C1[s]), 0.5j * J * Y1[s])
    for s in range(2))
# K6 (seeded false): [C1, H_J] = (iJ/2) X1.
results["kondo_c1_commutator_x1_false"] = all(close(L(C1[s]), 0.5j * J * X1[s]) for s in range(2))

print("norms:", {k: round(v, 6) for k, v in norms.items()})
for k, v in results.items():
    print(f"{k}: {'TRUE' if v else 'FALSE'}")
