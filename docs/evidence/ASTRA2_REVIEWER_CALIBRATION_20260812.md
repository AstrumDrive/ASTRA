# ASTRA 2.0 — calibración del revisor y bug Unicode de Windows (2026-08-12)

Autorización: Nelson autorizó la opción 1 del informe del gate H1 (calibrar
el revisor para que no bloquee por piernas auxiliares).

## 1. La calibración

`agents/reviewer.py`, addendum vNext (reglas 14–16):

- **Pierna decisiva**: sin ella los claims no pueden establecerse ni
  refutarse. **Pierna auxiliar**: quitarla no debilita esa capacidad — un
  muestreo ilustrativo, una malla finita o un chequeo puntual redundante al
  lado de una pierna exacta que ya decide.
- Si todas las decisivas son sólidas y ninguna auxiliar puede contaminar el
  veredicto → **APPROVED**, con la observación en `auxiliary_notes`.
- **Guardarraíl**: *"la prueba decisiva es si el PASS DEPENDE de la pierna
  débil"*. Si el muestreo es lo que haría imprimir PASS a un claim universal,
  sigue siendo `sampling_as_proof` → REVISE/REJECT. Reglas 2, 3 y 4 intactas.
- `auxiliary_notes` es informativo: los tests fijan que **nunca** cambia el
  estado y que entradas malformadas degradan a lista vacía.

## 2. Verificación viva: la compuerta NO se debilitó

Pista de auditoría completa, 14 casos
(`workspace/quality_benchmark_runs/quality_20260812_215206.json`):

| Métrica | Antes | Después |
|---|---|---|
| Recall de defectos / críticos / etiquetas | 1.0 | **1.0** |
| Falsa alarma sobre validadores sanos | 0.3333 | 0.3333 |

`audit_sampling_as_universal_proof` → **REJECT**; `audit_hardcoded_pass` →
**REJECT**; los dos validadores sanos que ya aprobaban → **APPROVED**. El
único fallo sigue siendo `audit_regression_einsteinpy_list_symbols_supported`,
que **la calibración no toca**: su objeción es de cobertura del claim, no de
pierna auxiliar. Ese fixture mide hoy algo distinto de su intención
documentada en `VALIDATOR_REPAIR_VNEXT.md`; **corregirlo es una decisión de
Nelson**, no se ha tocado.

## 3. Eficacia: 1 de 3 ciclos convertido, y un hallazgo mayor

Re-ejecución de los tres ciclos que morían por no-aprobación
(`quality_20260812_222533.json`):

- `symbolic_polynomial_factorization_sage`: **API_ERROR → VALIDATED**. El
  revisor aplicó exactamente la regla nueva: *"The seeded rational-point test
  is supplemental only; exact symbolic and factorization legs already decide
  the universal identity."* Ciclo muerto convertido en evidencia creíble.
- `quality_gr_schwarzschild_ricci_nonzero_false`: TIMEOUT a 601 s (modo de
  fallo distinto; no informa sobre la calibración).
- `lean_nat_add_comm`: sigue bloqueado — **y el revisor tiene razón**.

## 4. El bug: PowerShell 5.1 destruye todo carácter no-ASCII

El revisor de `lean_nat_add_comm` reportó: *"the submitted Lean source
literally contains `???` where the universal binder must be `∀`"*. El código
almacenado en el informe contiene `∀` correctamente, así que la corrupción
ocurre **al enviar el prompt a la CLI**.

Reproducción determinista (sin cuota), pipeline idéntico al de ASTRA:

```text
powershell.exe 5.1, $OutputEncoding = us-ascii
  entrada: "forall: ∀ nat: ℕ accent: raíz"
  recibido: "forall: ??? nat: ??? accent: ra??"        (un ? por byte UTF-8)

con el arreglo:
  recibido: "forall: ∀ nat: ℕ accent: raíz"            íntegro
```

Causa: Windows PowerShell 5.1 canaliza hacia ejecutables nativos usando
`$OutputEncoding`, cuyo default es **us-ascii**, y `Get-Content` sin
`-Encoding` lee un fichero sin BOM como **ANSI**. ASTRA escribe los prompts
en UTF-8 y los canaliza así hacia `codex` (y `gemini`) en Windows.

Impacto medido y esperable:

- **Lean/Mathlib inutilizable** en revisión: `∀ ∃ → ℕ ℝ` llegan como `???`;
- acentos españoles de las conjeturas de consenso degradados (`raíz` →
  `ra??`);
- símbolos matemáticos Unicode de cualquier conjetura, destruidos.

La ruta POSIX (macOS/Linux) pasa el fichero directo a stdin y **no está
afectada**. El BOM inicial que PowerShell antepone es preexistente y no lo
introduce el arreglo.

Corrección en `core/cli_backend.py`: preámbulo `_PS_UTF8_PREAMBLE`
(`$OutputEncoding` y `[Console]::OutputEncoding` a UTF-8 sin BOM) más
`Get-Content -Raw -Encoding UTF8`, en las dos rutas PowerShell.

Tests: `tests/test_cli_unicode_fidelity.py` — contrato del builder más un
test de integración que **ejecuta el `powershell.exe` real** (el intérprete
que ASTRA lanza, no el PowerShell 7 del shell de desarrollo) y comprueba que
`∀ ℕ ℝ í` sobreviven.

Suite completa: **333 passed, 7 skipped, 54 subtests**.

## 5. Pendiente de decisión de Nelson

1. **Portar el arreglo Unicode a ASTRA de producción.** El defecto vive en
   `core/cli_backend.py`, compartido; producción lo tiene igual. No se ha
   tocado el checkout de producción (`ASTRA2_ACCEPTANCE.md`).
2. Revisar el fixture `audit_regression_einsteinpy_list_symbols_supported`.
3. Re-medir el gate H1 standard completo tras estos dos cambios: la tasa de
   fallo operativo del 17.4% debería bajar, pero **la cifra actual no puede
   compararse** con la anterior hasta correr la suite entera de nuevo.
