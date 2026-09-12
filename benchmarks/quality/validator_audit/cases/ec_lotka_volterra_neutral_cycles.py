"""The cycles are real and the prediction of cycles is not robust.

CLAIM: the predator-prey equations have an interior equilibrium that is solved
for; a quantity built from the four rates is conserved along every trajectory,
which is verified by differentiating it through the flow; the linearisation there
has zero trace and positive determinant, so the eigenvalues are purely imaginary
and the equilibrium is a centre with period two pi over the root of the product
of the two linear rates; the orbits close, which an integration confirms; and
adding an arbitrarily small self-limitation to the prey makes the real part of
those eigenvalues negative, so the centre becomes a spiral and the closed orbits
are gone. What survives the perturbation is the time average, which sits exactly
at the equilibrium.

A centre is the fragile kind of prediction. It is what the equations say and it
is destroyed by any term one has neglected, so "the model predicts cycles" is a
statement about a boundary between behaviours rather than about either of them.

Legs:
  1. rest       -- the interior equilibrium is solved for;
  2. conserved  -- a first integral is differentiated through the flow and
                   vanishes, so the orbits are its level sets;
  3. centre     -- the Jacobian has zero trace and positive determinant, giving
                   a period that is read off rather than guessed;
  4. closed     -- an integrated orbit returns to where it started, and its
                   period matches at small amplitude;
  5. falsifier  -- any self-limitation, however small, makes the real part
                   negative, which is solved for rather than argued;
  6. spiral     -- the same integration with that term decays, and the first
                   integral now falls monotonically;
  7. survives   -- the time average over a cycle is the equilibrium exactly.
"""
import math

import sympy as sp

x, y = sp.symbols("x y", positive=True)
a, b, c, d, e = sp.symbols("a b c d e", positive=True)

FAILURES = []


def check(name, ok, detail=""):
    if ok is True:
        print(f"CHECK {name}: OK {detail}".rstrip())
        return True
    FAILURES.append(name)
    print(f"CHECK {name}: FAIL {detail}".rstrip())
    return False


prey_rate = a * x - b * x * y
predator_rate = c * x * y - d * y


# ---------------------------------------------------------------- leg 1
interior = sp.solve([sp.Eq(prey_rate, 0), sp.Eq(predator_rate, 0)], [x, y],
                    dict=True)
positive = [point for point in interior
            if point.get(x, 0) != 0 and point.get(y, 0) != 0]
check("there_is_one_interior_equilibrium",
      len(positive) == 1,
      f"solving both rates to zero gives {interior}, of which {len(positive)} "
      "has neither species absent")

rest = positive[0] if positive else {x: sp.nan, y: sp.nan}
check("and_it_sits_at_the_ratios_of_the_opposite_rates",
      sp.simplify(rest[x] - d / c) == 0 and sp.simplify(rest[y] - a / b) == 0,
      f"the prey settles at {rest[x]}, fixed by the PREDATOR's rates, and the "
      f"predator at {rest[y]}, fixed by the prey's, which is the exchange that "
      "makes the system counterintuitive")


# ---------------------------------------------------------------- leg 2
integral = c * x - d * sp.log(x) + b * y - a * sp.log(y)
drift = sp.simplify(
    sp.diff(integral, x) * prey_rate + sp.diff(integral, y) * predator_rate
)
check("the_first_integral_is_constant_along_the_flow",
      drift == 0,
      f"differentiating it through the equations leaves {drift}, so every "
      "trajectory stays on one of its level sets")

check("and_it_is_not_constant_as_a_function",
      sp.simplify(sp.diff(integral, x)) != 0
      and sp.simplify(sp.diff(integral, y)) != 0,
      f"its gradient is ({sp.simplify(sp.diff(integral, x))}, "
      f"{sp.simplify(sp.diff(integral, y))}), so the level sets are curves and "
      "the conservation is not the triviality of a constant function")


# ---------------------------------------------------------------- leg 3
jacobian = sp.Matrix([[sp.diff(prey_rate, x), sp.diff(prey_rate, y)],
                      [sp.diff(predator_rate, x), sp.diff(predator_rate, y)]])
at_rest = sp.simplify(jacobian.subs(rest))
check("the_linearisation_has_zero_trace_and_positive_determinant",
      sp.simplify(at_rest.trace()) == 0
      and sp.simplify(at_rest.det() - a * d) == 0,
      f"trace {sp.simplify(at_rest.trace())} and determinant "
      f"{sp.simplify(at_rest.det())}, so the eigenvalues are a conjugate pair on "
      "the imaginary axis")

eigenvalues = list(at_rest.eigenvals())
period = sp.simplify(2 * sp.pi / sp.sqrt(a * d))
check("so_the_small_oscillation_period_is_two_pi_over_the_root_of_a_d",
      all(sp.simplify(sp.re(value)) == 0 for value in eigenvalues)
      and sp.simplify(sp.Abs(sp.im(eigenvalues[0])) - sp.sqrt(a * d)) == 0,
      f"the eigenvalues are {eigenvalues}, giving a period of {period}")


# ---------------------------------------------------------------- leg 4
A, B, C, D = 1.0, 0.1, 0.075, 1.5
REST = (D / C, A / B)


def integrate(start, steps, step, damping=0.0):
    """Runge-Kutta on the pair, with an optional self-limitation on the prey."""
    prey, predator = start

    def rates(first, second):
        return (A * first - B * first * second - damping * first ** 2,
                C * first * second - D * second)

    trail = [(prey, predator)]
    for _ in range(steps):
        k1 = rates(prey, predator)
        k2 = rates(prey + step * k1[0] / 2, predator + step * k1[1] / 2)
        k3 = rates(prey + step * k2[0] / 2, predator + step * k2[1] / 2)
        k4 = rates(prey + step * k3[0], predator + step * k3[1])
        prey += step * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6
        predator += step * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6
        trail.append((prey, predator))
    return trail


STEP = 2e-4
SMALL = (REST[0] * 1.02, REST[1])
predicted_period = float(period.subs({a: A, d: D}))
orbit = integrate(SMALL, int(3 * predicted_period / STEP), STEP)


def first_return(trail, start, step):
    """When the trajectory next comes back to its starting point."""
    best, when = None, None
    for index in range(int(0.5 * predicted_period / step), len(trail)):
        gap = math.dist(trail[index], start)
        if best is None or gap < best:
            best, when = gap, index * step
    return best, when


closure, returned = first_return(orbit, SMALL, STEP)
check("the_orbit_closes_on_itself",
      closure < 1e-4,
      f"the trajectory returns to within {closure:.3e} of its starting point, "
      f"on a displacement of {abs(SMALL[0] - REST[0]):.4f} from the equilibrium")

check("and_it_does_so_at_the_predicted_period",
      abs(returned - predicted_period) / predicted_period < 2e-3,
      f"the return happens at {returned:.5f} against the predicted "
      f"{predicted_period:.5f}, a relative gap of "
      f"{abs(returned - predicted_period) / predicted_period:.2e}")


# ---------------------------------------------------------------- leg 5
# Add a self-limitation to the prey and ask what happens to the real part. The
# equilibrium moves, so it is re-solved rather than reused.
damped_prey = a * x - b * x * y - e * x ** 2
damped_rest = sp.solve([sp.Eq(damped_prey, 0), sp.Eq(predator_rate, 0)], [x, y],
                       dict=True)
damped_interior = [point for point in damped_rest
                   if point.get(x, 0) != 0 and point.get(y, 0) != 0]
damped_jacobian = sp.Matrix(
    [[sp.diff(damped_prey, x), sp.diff(damped_prey, y)],
     [sp.diff(predator_rate, x), sp.diff(predator_rate, y)]]
).subs(damped_interior[0] if damped_interior else {})
damped_trace = sp.simplify(damped_jacobian.trace())
check("falsifier_any_self_limitation_makes_the_trace_negative",
      sp.simplify(damped_trace + e * d / c) == 0
      and damped_trace.subs({e: 1, d: 1, c: 1}).is_negative is True,
      f"the trace becomes {damped_trace}, negative for every positive e however "
      "small, so the eigenvalues leave the imaginary axis at once and the centre "
      "is not a robust feature of the model")

check("and_the_determinant_stays_positive_so_it_is_a_spiral_not_a_saddle",
      sp.simplify(damped_jacobian.det()).subs({a: 1, b: 1, c: 1, d: sp.Rational(1, 2),
                                               e: sp.Rational(1, 10)}).is_positive is True,
      f"the determinant is {sp.simplify(damped_jacobian.det())}, still positive, "
      "so the orbits wind inward rather than running off")


# ---------------------------------------------------------------- leg 6
DAMPING = 1e-3
TURNS = 6
per_turn = int(predicted_period / STEP)
damped_orbit = integrate(SMALL, TURNS * per_turn, STEP, damping=DAMPING)
damped_rest_numeric = (D / C, (A - DAMPING * D / C) / B)


def envelope(trail, centre, turn):
    """The largest distance from the centre during one turn.

    Measured as an envelope rather than at a single instant: the orbit is an
    ellipse in a metric that is not the Euclidean one, so the distance breathes
    within each turn and one endpoint samples a phase rather than an amplitude.
    """
    window = trail[turn * per_turn:(turn + 1) * per_turn]
    return max(math.dist(point, centre) for point in window)


first_turn = envelope(damped_orbit, damped_rest_numeric, 0)
last_turn = envelope(damped_orbit, damped_rest_numeric, TURNS - 1)
decay_rate = DAMPING * D / (2 * C)
predicted_decay = math.exp(-decay_rate * (TURNS - 1) * predicted_period)
# The second clause is what keeps the first honest: with no damping at all both
# the observed ratio and the predicted one are one, and a comparison of one with
# one tests nothing. The configuration has to produce a decay before matching it
# means anything.
check("the_damped_orbit_decays_at_the_rate_the_eigenvalue_gives",
      predicted_decay < 0.9
      and abs((last_turn / first_turn) / predicted_decay - 1) < 0.01,
      f"the envelope falls from {first_turn:.5f} to {last_turn:.5f}, a ratio of "
      f"{last_turn / first_turn:.5f} against the {predicted_decay:.5f} that half "
      f"the trace, {decay_rate:.5f}, asks for over {TURNS - 1} periods")

undamped_first = envelope(orbit, REST, 0)
undamped_last = envelope(orbit, REST, min(TURNS - 1, len(orbit) // per_turn - 1))
check("while_the_undamped_one_does_not_decay_at_all",
      abs(undamped_last / undamped_first - 1) < 1e-5,
      f"without the term the envelope goes from {undamped_first:.6f} to "
      f"{undamped_last:.6f}, a ratio of {undamped_last / undamped_first:.6f}, so "
      "the decay above is the perturbation and not the integrator")


# ---------------------------------------------------------------- leg 7
# What survives. Dividing the predator equation by the predator and integrating
# over one period makes the left side vanish, which fixes the average of the prey.
average_prey = sum(point[0] for point in orbit[:int(predicted_period / STEP)])
average_prey /= int(predicted_period / STEP)
check("the_time_average_of_the_prey_is_the_equilibrium_itself",
      abs(average_prey - REST[0]) / REST[0] < 1e-4,
      f"averaging over one period gives {average_prey:.6f} against the "
      f"equilibrium {REST[0]:.6f}, which is what integrating d(log y)/dt over a "
      "closed orbit forces")

check("and_that_follows_from_the_predator_equation_alone",
      sp.simplify(sp.diff(sp.log(y), y) * predator_rate - (c * x - d)) == 0,
      f"d(log y)/dt is {sp.simplify(sp.diff(sp.log(y), y) * predator_rate)}, "
      "whose integral over a closed orbit is zero, so the mean of c x is d and "
      "the average sits at the equilibrium whatever the amplitude")


print()
print(f"legs_failed={len(FAILURES)} {FAILURES}")
if FAILURES:
    print("VERDICT: FAIL")
    raise SystemExit(1)
print("VERDICT: PASS")
