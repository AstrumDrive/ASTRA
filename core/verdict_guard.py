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
    algun FAIL pero el veredicto final dice PASS -> contradiccion.

Scripts de motores externos (sage/maxima/cadabra) no son Python parseable:
se les salta la auditoria de AST (el conteo de CHECKs del stdout si aplica).
"""
from __future__ import annotations

import ast
import re

# Acepta anotacion tras el marcador: "CHECK nombre: OK  (residuo=1e-14)" —
# los traductores anaden evidencia al final de la linea (visto en produccion).
_CHECK_LINE = re.compile(r"(?im)^\s*CHECK\b[^\n]*?:\s*(OK|PASS|FAIL)\b")


def _string_constants(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _literal_true_legs(tree) -> list:
    """Names of leg()/run_leg() calls whose value is a literal True (or a
    lambda returning one) and whose role is not literally corroborative."""
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("leg", "run_leg")):
            continue
        kwargs = {k.arg: k.value for k in node.keywords if k.arg}
        value = node.args[1] if len(node.args) > 1 else kwargs.get("value", kwargs.get("fn"))
        role = node.args[3] if node.func.id == "leg" and len(node.args) > 3 else (
            node.args[2] if node.func.id == "run_leg" and len(node.args) > 2 else kwargs.get("role"))
        if isinstance(role, ast.Constant) and role.value == "corroborative":
            continue
        if isinstance(value, ast.Lambda):
            value = value.body
        if isinstance(value, ast.Constant) and value.value is True:
            name = node.args[0] if node.args else kwargs.get("name")
            found.append(repr(name.value) if isinstance(name, ast.Constant) else "<leg>")
    return found


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

    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return out          # sage/maxima/cadabra: sin auditoria de AST

    out["asserts"] = sum(isinstance(n, ast.Assert) for n in ast.walk(tree))
    out["comparisons"] = sum(isinstance(n, ast.Compare) for n in ast.walk(tree))

    # Veredicto emitido por el helper verificado (core/certified, decide()):
    # el camino a FAIL vive en el helper, no en el texto del validador, y las
    # comprobaciones suelen ser llamadas certificadas, no comparaciones. Lo
    # que se audita aqui es que ninguna rama decisiva sea un True literal.
    from core.certified import decision_from_stdout

    if (exec_result or {}).get("certified_prelude") and decision_from_stdout(stdout) == "PASS":
        literal = _literal_true_legs(tree)
        if literal:
            out["verdict_suspect"] = True
            out["reasons"].append(
                "rama decisiva con valor True literal en leg()/run_leg(): "
                + ", ".join(literal))
        return out

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
