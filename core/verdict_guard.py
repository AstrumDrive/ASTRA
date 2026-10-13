"""
Guardas DETERMINISTAS sobre el veredicto — cero LLM, cero cuota.

El modo de fallo clasico de un traductor debil es el PASS trivial:
`print("VERDICT: PASS")` incondicional al final de un script que no puede
fallar. Este auditor examina el AST del script + su stdout y decide si un
PASS es CREIBLE. La filosofia de ASTRA: la confianza no viene del modelo,
viene de la estructura; este modulo es esa estructura para el veredicto.

Criterios de sospecha (solo se audita cuando el stdout dice VERDICT: PASS):
  * el script no contiene NINGUNA constante de texto con "FAIL"
    -> no existe camino que imprima un fallo: el PASS era inevitable;
  * cero `assert` y cero comparaciones en el AST
    -> no se verifico nada antes de declarar PASS;
  * el protocolo de sub-checks (lineas `CHECK <nombre>: OK|FAIL`) muestra
    algun FAIL pero el veredicto final dice PASS -> contradiccion;
  * el script declara unidades e identidades dimensionales (`# ASTRA_UNITS:`
    / `# ASTRA_DIMENSION:`) y alguna NO cuadra -> el PASS no es creible,
    porque una ecuacion cuyos dos lados tienen dimensiones distintas no
    puede ser ni verdadera ni falsa.

La guarda dimensional es OPT-IN: sin declaracion no se audita nada. Exigirla
convertiria el silencio de la mayoria de validadores -que no son
dimensionales- en sospecha. Y solo una identidad EVALUADA que no cuadra marca
sospecha; una que no se pudo resolver se anota como `unverifiable` sin
penalizar, porque las unidades irresolubles suelen ser prosa legitima
('ratio', 'none') y no defectos. Ver `audit_dimensions`.

Scripts de motores externos (sage/maxima/cadabra) no son Python parseable:
se les salta la auditoria de AST (el conteo de CHECKs del stdout si aplica).
"""
from __future__ import annotations

import ast
import os
import re

# Acepta anotacion tras el marcador: "CHECK nombre: OK  (residuo=1e-14)" —
# los traductores anaden evidencia al final de la linea (visto en produccion).
_CHECK_LINE = re.compile(r"(?im)^\s*CHECK\b[^\n]*?:\s*(OK|PASS|FAIL)\b")

# Declaracion dimensional OPCIONAL del validador, en la forma de los demas
# marcadores de ASTRA (`# ASTRA_ENGINE:`):
#
#   # ASTRA_UNITS: rho=kg/m**3, v=m/s, L=m, mu=Pa*s
#   # ASTRA_DIMENSION: rho*v*L/mu == dimensionless
#   # ASTRA_DIMENSION: F == m*a
#
# Es opt-in a proposito. La mayoria de los validadores no son dimensionales,
# y una guarda que exigiera la declaracion convertiria ese silencio en
# sospecha: falsos positivos sobre la mayoria para atrapar a una minoria.
_UNITS_LINE = re.compile(r"(?im)^\s*#\s*ASTRA_UNITS:\s*(.+?)\s*$")
_DIMENSION_LINE = re.compile(r"(?im)^\s*#\s*ASTRA_DIMENSION:\s*(.+?)\s*$")


def _string_constants(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _declared_units(code: str) -> dict[str, str]:
    """Simbolo -> unidades, unidas sobre todas las lineas ASTRA_UNITS."""
    units: dict[str, str] = {}
    for raw in _UNITS_LINE.findall(code or ""):
        for item in raw.split(","):
            symbol, _, value = item.partition("=")
            symbol, value = symbol.strip(), value.strip()
            if symbol and value:
                units[symbol] = value
    return units


def audit_dimensions(code: str) -> dict:
    """Consistencia dimensional de las identidades que el script declara.

    Devuelve ``{"declared": bool, "checked": int, "inconsistent": [...],
    "unverifiable": [...]}``.

    La distincion entre las dos ultimas listas es la que decide todo, y sale
    de una medicion, no de una preferencia. `inconsistent` es una identidad
    que se evaluo y no cuadra -sumar una masa a una aceleracion, o dos lados
    con dimensiones distintas-: eso hace el veredicto sospechoso.
    `unverifiable` es una declaracion que ni siquiera se pudo resolver, casi
    siempre porque las unidades son prosa legitima.

    Medido contra pint 0.25.3 el 2026-08-30: 'ratio', 'none', 'per second' y
    'arbitrary units' NO parsean aunque son unidades que los cientificos
    escriben, mientras que 'N/A' parsea como newton/amperio y 'a.u.' como
    [time]*[mass]. Tratar lo irresoluble como inconsistente degradaria
    validadores correctos, y no compraria nada a cambio: los placeholders
    peligrosos parsean igual. Por eso solo `inconsistent` marca sospecha.
    """
    out = {
        "declared": False,
        "checked": 0,
        "inconsistent": [],
        "unverifiable": [],
    }
    identities = [item.strip() for item in _DIMENSION_LINE.findall(code or "")]
    units = _declared_units(code or "")
    if not identities and not units:
        return out
    out["declared"] = True

    from core.dimensional_analysis import (
        DimensionalError,
        check_same_dimension,
        expression_dimension,
    )

    for identity in identities:
        left, separator, right = identity.partition("==")
        if not separator:
            out["unverifiable"].append(
                f"{identity!r}: se esperaba 'expresion == expresion'"
            )
            continue
        left, right = left.strip(), right.strip()
        try:
            if right.lower() == "dimensionless":
                dimension = expression_dimension(left, units)
                if dimension != "dimensionless":
                    out["inconsistent"].append(
                        f"{left} no es adimensional: tiene dimension {dimension}"
                    )
            else:
                check_same_dimension(left, right, units)
            out["checked"] += 1
        except DimensionalError as exc:
            message = str(exc)
            # Un desajuste dimensional es un hallazgo; una unidad que no se
            # reconoce es una limitacion de esta guarda, no un defecto del
            # validador.
            if "Unrecognised units" in message or "Unrecognised unit" in message:
                out["unverifiable"].append(f"{identity!r}: {message}")
            else:
                out["inconsistent"].append(f"{identity!r}: {message}")
                out["checked"] += 1
    return out


def assess_verdict(code: str, exec_result: dict) -> dict:
    """Audita un resultado de ejecucion. Devuelve un dict con
    verdict_suspect (bool), reasons (list[str]) y metricas informativas."""
    stdout = (exec_result or {}).get("stdout") or ""
    up = stdout.upper()
    marks = [m.upper() for m in _CHECK_LINE.findall(stdout)]
    n_ok = sum(1 for m in marks if m in ("OK", "PASS"))
    n_fail = len(marks) - n_ok
    out = {
        "verdict_suspect": False,
        "reasons": [],
        "checks_total": len(marks),
        "checks_ok": n_ok,
        "checks_fail": n_fail,
        "asserts": 0,
        "comparisons": 0,
    }

    if "VERDICT: PASS" not in up:
        return out          # FAIL/NONE ya son resultados honestos: nada que auditar

    if n_fail:
        out["verdict_suspect"] = True
        out["reasons"].append(
            f"contradiccion: {n_fail} CHECK en FAIL pero el veredicto final dice PASS")

    # Antes de la auditoria de AST, para que sage/maxima -que tambien usan `#`
    # como comentario- reciban la guarda dimensional aunque su script no sea
    # Python parseable. Lean queda fuera: comenta con `--`, no con `#`. No se
    # anade ese caso hasta que exista un artefacto Lean dimensional real que
    # lo justifique; las pruebas formales rara vez llevan unidades, y
    # soportar una sintaxis sin un caso que la ejercite es superficie sin
    # cobertura.
    # 1.1.11 (from ASTRA 2.0, 87efbe9/8c4b7ef) behind ASTRA_DIMENSIONAL_GUARD:
    # "record" (default) audits and records without touching the verdict, so
    # it can be measured on production cycles first; "1"/"enforce" lets an
    # inconsistent declared identity make the PASS suspect, as in 2.0; "0"
    # skips the audit.
    mode = (os.environ.get("ASTRA_DIMENSIONAL_GUARD") or "record").strip().strip("'\"").lower()
    if mode not in {"0", "off", "false", "no"}:
        dimensions = audit_dimensions(code or "")
        dimensions["mode"] = "enforce" if mode in {"1", "on", "true", "yes", "enforce"} else "record"
        out["dimensions"] = dimensions
        if dimensions["inconsistent"] and dimensions["mode"] == "enforce":
            out["verdict_suspect"] = True
            out["reasons"].append(
                "inconsistencia dimensional en identidades declaradas por el "
                "propio script: " + "; ".join(dimensions["inconsistent"])
            )

    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return out          # sage/maxima/cadabra: sin auditoria de AST

    out["asserts"] = sum(isinstance(n, ast.Assert) for n in ast.walk(tree))
    out["comparisons"] = sum(isinstance(n, ast.Compare) for n in ast.walk(tree))

    if not any("FAIL" in s for s in _string_constants(tree)):
        out["verdict_suspect"] = True
        out["reasons"].append(
            "el script no contiene ningun camino que imprima FAIL "
            "(PASS incondicional: no podia fallar)")

    if out["asserts"] == 0 and out["comparisons"] == 0:
        out["verdict_suspect"] = True
        out["reasons"].append(
            "cero asserts y cero comparaciones en el AST: "
            "no se verifico nada antes de declarar PASS")

    return out
