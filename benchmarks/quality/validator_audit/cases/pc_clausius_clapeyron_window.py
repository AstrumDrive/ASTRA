"""One exact relation, three approximations, and an enthalpy that depends on the
window you fit.

CLAIM: equality of the chemical potentials along a coexistence line gives
dP/dT = dH / (T dV) with no approximation at all; the familiar straight line in
one over T follows only after three separate assumptions, that the liquid volume
is negligible, that the vapour is ideal, and that the enthalpy of vaporisation
does not depend on temperature; the three are sized against each other and the
third is the largest, by two orders of magnitude over the liquid volume and by
one over the ideal gas, which is the reverse of the order in which they are
usually defended; and fitting the straight line to coexistence
pressures computed with the real enthalpy returns a value that differs by seven
per cent between a low and a high window, each matching the truth at its own
midpoint, with residuals that bend rather than scatter.

The three assumptions arrive together in most presentations and leave together
too. Separating and ranking them is the whole content.

Legs:
  1. exact     -- the relation is derived from the equality of the chemical
                  potentials, with nothing dropped;
  2. rank      -- the three approximations are sized from steam-table volumes and
                  a correlation, and ordered;
  3. integrate -- the straight line is obtained by solving the separable equation
                  under exactly those assumptions;
  4. falsifier -- the enthalpy is not constant: it vanishes at the critical point,
                  so the line cannot hold over a wide range;
  5. window    -- fitting over two windows returns two different enthalpies, each
                  matching the true value at its own midpoint;
  6. control   -- with a constant enthalpy the same pipeline returns one value to
                  a part in a billion, so the spread is the physics, not the fit;
  7. curvature -- the residuals bend rather than scatter, which is what separates
                  a wrong model from a noisy measurement.
"""
import math

import sympy as sp

temperature, pressure = sp.symbols("T P", positive=True)
gas_constant = sp.Symbol("R", positive=True)
enthalpy = sp.Symbol("Delta_H", positive=True)

FAILURES = []


def check(name, ok, detail=""):
    if ok is True:
        print(f"CHECK {name}: OK {detail}".rstrip())
        return True
    FAILURES.append(name)
    print(f"CHECK {name}: FAIL {detail}".rstrip())
    return False


def ratio_of(numerator, denominator):
    """The ratio, or infinity when the denominator has gone to zero.

    The detail strings below are evaluated before check() is entered, so a
    division there raises whatever the verdict would have been. A validator
    reports a failure; it does not crash on its way to describing one.
    """
    return numerator / denominator if denominator else math.inf


# ---------------------------------------------------------------- leg 1
# Along coexistence the two chemical potentials stay equal, so their differentials
# do too: -S dT + V dP is the same on both sides.
entropy_liquid, entropy_vapour = sp.symbols("S_l S_v", positive=True)
volume_liquid, volume_vapour = sp.symbols("V_l V_v", positive=True)
slope = sp.Symbol("slope", positive=True)

balance = sp.Eq(-entropy_liquid + volume_liquid * slope,
                -entropy_vapour + volume_vapour * slope)
solved_slope = sp.solve(balance, slope)
check("the_coexistence_slope_is_the_ratio_of_the_two_jumps",
      len(solved_slope) == 1
      and sp.simplify(solved_slope[0]
                      - (entropy_vapour - entropy_liquid)
                      / (volume_vapour - volume_liquid)) == 0,
      f"equating the two differentials gives dP/dT = {solved_slope[0]}, the "
      "entropy jump over the volume jump, with nothing approximated")

# The transfer at equilibrium is reversible, so the entropy jump is the enthalpy
# over the temperature. Substituted into the vapour entropy rather than pattern
# matched on the difference, which sympy would not recognise.
exact = sp.simplify(
    ((entropy_vapour - entropy_liquid) / (volume_vapour - volume_liquid))
    .subs(entropy_vapour, entropy_liquid + enthalpy / temperature)
)
check("and_the_entropy_jump_is_the_enthalpy_over_the_temperature",
      sp.simplify(exact * temperature * (volume_vapour - volume_liquid)
                  - enthalpy) == 0,
      f"the relation becomes dP/dT = {exact}, which is still exact: it holds at "
      "any pressure, for any substance, and for melting as well as boiling")


# ---------------------------------------------------------------- leg 2
# Saturated water at its normal boiling point, from the specific volumes, so the
# two numbers entering the comparison come from the same table.
MOLAR_MASS = 0.018015           # kilograms per mole
LIQUID_SPECIFIC = 1.0435e-3     # cubic metres per kilogram at 373.15 kelvin
VAPOUR_SPECIFIC = 1.6720        # cubic metres per kilogram at 373.15 kelvin
R_SI = 8.314462618

water_liquid = LIQUID_SPECIFIC * MOLAR_MASS
water_vapour = VAPOUR_SPECIFIC * MOLAR_MASS
volume_error = water_liquid / water_vapour
check("dropping_the_liquid_volume_costs_a_part_in_a_thousand",
      1e-5 < volume_error < 1e-3,
      f"the liquid occupies {volume_error:.2e} of the vapour volume, small but "
      "not zero, so the first assumption is an approximation and not an identity")

ideal_volume = R_SI * 373.15 / 101325.0
ideal_error = abs(ideal_volume - water_vapour) / water_vapour
check("and_treating_the_vapour_as_ideal_costs_under_two_per_cent_here",
      0.005 < ideal_error < 0.05,
      f"the ideal volume is {ideal_volume:.6f} against the saturated "
      f"{water_vapour:.6f}, a gap of {100 * ideal_error:.2f} per cent, which is "
      "the compressibility factor departing from one and grows with pressure")


# ---------------------------------------------------------------- leg 3
approximate = enthalpy * pressure / (gas_constant * temperature ** 2)
curve = sp.Function("P")(temperature)
integrated = sp.dsolve(
    sp.Eq(sp.diff(curve, temperature),
          enthalpy * curve / (gas_constant * temperature ** 2)),
    curve,
)
logarithm = sp.log(integrated.rhs)
check("under_those_assumptions_the_logarithm_is_linear_in_the_reciprocal",
      sp.simplify(sp.diff(logarithm, temperature)
                  + sp.diff(enthalpy / (gas_constant * temperature), temperature)) == 0,
      f"solving the separable equation leaves log P with derivative "
      f"{sp.simplify(sp.diff(logarithm, temperature))}, which is minus that of "
      "the enthalpy over R T, so the plot against one over T is a straight line "
      "whose slope is minus the enthalpy over R")

check("and_the_approximate_slope_is_the_exact_one_with_two_substitutions",
      sp.simplify(approximate
                  - exact.subs({volume_liquid: 0,
                                volume_vapour: gas_constant * temperature / pressure})) == 0,
      "the working equation is the exact relation with the liquid volume set to "
      "zero and the vapour volume replaced by the ideal one, so the first two "
      "assumptions enter here and nowhere else")


# ---------------------------------------------------------------- leg 4
CRITICAL = 647.1
REFERENCE = 56410.0
EXPONENT = 0.38
LOW, MID, HIGH = 333.0, 373.15, 433.0


def vaporisation(kelvin):
    """Watson's correlation: the enthalpy falls to zero at the critical point."""
    return REFERENCE * (1 - kelvin / CRITICAL) ** EXPONENT


enthalpy_error = abs(vaporisation(HIGH) - vaporisation(LOW)) / vaporisation(MID)
check("falsifier_the_enthalpy_is_not_constant_and_vanishes_at_the_critical_point",
      abs(vaporisation(CRITICAL)) < 1e-9 and enthalpy_error > 0.1,
      f"it reads {vaporisation(LOW):,.0f} joules per mole at {LOW:.0f} kelvin and "
      f"{vaporisation(HIGH):,.0f} at {HIGH:.0f}, a swing of "
      f"{100 * enthalpy_error:.0f} per cent across the window, and reaches zero "
      "at the critical point where the two phases stop differing")

check("and_it_is_the_largest_of_the_three_approximations",
      enthalpy_error > 100 * volume_error and enthalpy_error > 5 * ideal_error,
      f"the three cost {100 * volume_error:.3f}, {100 * ideal_error:.2f} and "
      f"{100 * enthalpy_error:.0f} per cent respectively, so the one that is "
      f"never stated dominates the other two by "
      f"{ratio_of(enthalpy_error, volume_error):.0f} and "
      f"{ratio_of(enthalpy_error, ideal_error):.0f} times, and the two that are "
      "defended at length are the two that do not matter here")


# ---------------------------------------------------------------- leg 5
def coexistence(law, start_kelvin, start_pressure, end_kelvin, steps=20000):
    """Integrate the working equation with whatever enthalpy law is supplied."""
    step = (end_kelvin - start_kelvin) / steps
    kelvin, value = start_kelvin, start_pressure
    trail = [(kelvin, value)]

    def rate(t_value, p_value):
        return law(t_value) * p_value / (R_SI * t_value ** 2)

    for _ in range(steps):
        k1 = rate(kelvin, value)
        k2 = rate(kelvin + step / 2, value + step * k1 / 2)
        k3 = rate(kelvin + step / 2, value + step * k2 / 2)
        k4 = rate(kelvin + step, value + step * k3)
        value += step * (k1 + 2 * k2 + 2 * k3 + k4) / 6
        kelvin += step
        trail.append((kelvin, value))
    return trail


def fitted_enthalpy(points):
    """Least squares of log P against one over T, returning minus R times the slope."""
    xs = [1.0 / kelvin for kelvin, _ in points]
    ys = [math.log(value) for _, value in points]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(xs, ys))
    variance = sum((a - mean_x) ** 2 for a in xs)
    fit = covariance / variance
    return -R_SI * fit, fit, xs, ys, mean_x, mean_y


cold, cold_slope, cold_xs, cold_ys, cold_mx, cold_my = fitted_enthalpy(
    coexistence(vaporisation, MID, 101325.0, LOW))
hot = fitted_enthalpy(coexistence(vaporisation, MID, 101325.0, HIGH))[0]

cold_true = vaporisation(0.5 * (LOW + MID))
hot_true = vaporisation(0.5 * (MID + HIGH))
check("each_window_returns_the_true_enthalpy_at_its_own_midpoint",
      abs(cold - cold_true) / cold_true < 0.02
      and abs(hot - hot_true) / hot_true < 0.02,
      f"the cold fit gives {cold:,.0f} against a midpoint truth of "
      f"{cold_true:,.0f} and the hot fit {hot:,.0f} against {hot_true:,.0f}, so "
      "the straight line is not wrong, it is local: it measures the enthalpy in "
      "the middle of whatever range was used")


# ---------------------------------------------------------------- leg 6
# The control. The same integrator and the same fit on a world where the enthalpy
# really is constant, which is what says the spread above is the physics rather
# than the arithmetic. Without this the seven per cent could be anything.
CONSTANT = vaporisation(MID)
control_cold = fitted_enthalpy(
    coexistence(lambda _: CONSTANT, MID, 101325.0, LOW))[0]
control_hot = fitted_enthalpy(
    coexistence(lambda _: CONSTANT, MID, 101325.0, HIGH))[0]
check("with_a_constant_enthalpy_both_windows_recover_it",
      abs(control_cold - CONSTANT) / CONSTANT < 1e-9
      and abs(control_hot - CONSTANT) / CONSTANT < 1e-9,
      f"feeding the pipeline {CONSTANT:,.3f} joules per mole returns "
      f"{control_cold:,.3f} and {control_hot:,.3f}, so neither the integrator "
      "nor the least squares introduces a bias of its own")

resolution = abs(control_cold - control_hot)
spread = abs(cold - hot)
check("falsifier_so_the_window_dependence_is_a_real_effect_not_a_method_artefact",
      resolution > 0 and spread > 1e4 * resolution,
      f"the two real windows differ by {spread:,.0f} joules per mole, "
      f"{100 * ratio_of(spread, hot):.0f} per cent, against a method resolution "
      f"of {resolution:.2e} measured on the constant-enthalpy control, a ratio "
      f"of {ratio_of(spread, resolution):.1e}, so the slope names a window and "
      "not a substance")


# ---------------------------------------------------------------- leg 7
residuals = [b - (cold_my + cold_slope * (a - cold_mx))
             for a, b in zip(cold_xs, cold_ys)]
signs = [1 if value > 0 else -1 for value in residuals]
changes = sum(1 for index in range(len(signs) - 1)
              if signs[index] != signs[index + 1])
check("the_residuals_bend_instead_of_scattering",
      1 <= changes <= 3,
      f"the residuals change sign {changes} times across {len(residuals)} points, "
      "which is a bend and not noise; scatter would cross the axis on the order "
      "of half the points, and the sign pattern is what distinguishes a model "
      "that is wrong from a measurement that is imprecise")

bend = max(abs(value) for value in residuals)
check("and_the_bend_is_larger_than_the_precision_of_a_barometer",
      bend > 1e-3,
      f"the largest residual in the logarithm is {bend:.2e}, which is "
      f"{100 * bend:.2f} per cent in the pressure, so an ordinary measurement "
      "resolves the curvature and the straight line can be rejected rather than "
      "fitted and reported as a number")


print()
print(f"legs_failed={len(FAILURES)} {FAILURES}")
if FAILURES:
    print("VERDICT: FAIL")
    raise SystemExit(1)
print("VERDICT: PASS")
