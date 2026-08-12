# ASTRA 2.0 — re-anclaje de veredicto al claim original (2026-08-12)

Autorización: Nelson autorizó explícitamente esta corrección tras el hallazgo
del H1 smoke limpio (`docs/evidence/ASTRA2_H1_SMOKE_CLEAN_20260812.md`).

## Problema corregido

`astra_tool` reportaba el estado de la **conjetura formada**, no del **claim
original del usuario**. Con la postura neutral R1 ("prove OR refute"), ASTRA
corrige claims falsos y valida la versión verdadera → el usuario recibe
`VALIDATED` cuando su claim era, de hecho, **falso**. Medido en dos casos
con contraejemplo exacto correcto.

Afecta también a ASTRA de producción: hoy preguntar por algo falso devuelve
"VALIDATED" con la refutación enterrada en la prosa.

## Implementación

Eje **separado**, nunca colapsado con los cinco existentes:

- `agents/analyst.py`: sección obligatoria "VERDICT RE-ANCHORING". El
  analista devuelve `original_claim_verdict` ∈ {SUPPORTED, REFUTED,
  INCONCLUSIVE, SUBSTITUTED} más `original_claim_reasoning`. Regla explícita:
  *una conjetura del tipo "X es contraejemplo del claim" que PASA significa
  que el claim original está REFUTED*.
- `core/llm_client.py`: `analyze_results(..., original_claim=...)` inyecta el
  bloque "ORIGINAL CLAIM AS THE USER STATED IT" y
  `_normalize_original_claim_verdict` valida contra un enum cerrado.
  **Nunca fabrica un veredicto**: ausente, desconocido o sin claim original →
  `UNSPECIFIED`. El estado del ciclo jamás se reescribe desde este campo.
- `astra_tool.py`: `intuition` (el claim original) viaja al analista en el
  camino lineal y en el ensemble; la salida del ciclo expone
  `original_claim_verdict` y `original_claim_reasoning` como campos propios;
  el informe del ensemble muestra el veredicto re-anclado de cada analista.
- `scripts/run_quality_benchmarks.py`: `_reanchored_status` puntúa el claim
  sembrado, no la conjetura elegida. `SUBSTITUTED`/`INCONCLUSIVE` quedan
  distintos de ambos valores de verdad — no responder no es aceptar una
  falsedad. Sin el campo, comportamiento histórico intacto.

## Verificación

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_verdict_reanchoring.py -q
# 14 passed, 13 subtests passed in 1.07s

.\venv\Scripts\python.exe -m pytest -q
# 318 passed, 6 skipped, 41 subtests passed in 55.55s

.\venv\Scripts\python.exe scripts\audit_architecture.py
# "status": "PASS"
```

Cobertura: contrato del prompt; enum cerrado y no-fabricación; el claim
original llega al analista; los dos ejes discrepan sin colapsarse (ciclo
completo con dobles); puntuación del benchmark en los cinco casos; y la
demostración con `_scientific_metrics` de que los registros medidos el
2026-08-12 pasan de `false_acceptance_rate` **1.0 → 0.0** y
`strict_accuracy` **→ 1.0** al puntuar el claim real en vez de la etiqueta
desalineada.

## Verificación VIVA: 3/3 con modelos reales

Ejecutada sobre los tres casos de refutación sembrada
(`--only`, ~4 ciclos, config íntegra de producción). Informes:
`quality_20260812_172156.json` y `quality_20260812_173253.json`.

| Caso | Antes | Después | `original_claim_verdict` |
|---|---|---|---|
| `quality_logic_sqrt_square_all_reals_false` | VALIDATED ✗ | **REFUTED ✓** | REFUTED |
| `logic_false_square_claim` | REFUTED ✓ | **REFUTED ✓** | REFUTED |
| `quality_ode_harmonic_wrong_initial_solution_false` | VALIDATED ✗ | **REFUTED ✓** | REFUTED |

Razonamientos textuales del analista (extraídos de los informes):

- *"The validated conjecture replaces x with |x| and supplies the exact
  counterexample x=-1, for which sqrt((-1)^2)=1 rather than -1."*
- *"The validated conjecture is the negation of the original universal claim:
  … gives x = 0 as an explicit counterexample."*
- *"The proposition P is that y(t)=sin(omega t) satisfies the ODE **and both
  initial conditions**; the validated conjecture proves P false for every
  real omega because y(0)=0, not 1."*

`false_acceptance_rate` sobre estos casos: **0.0**.

## Corrección intermedia: anclar a la proposición, no a la pista

La primera pasada viva dio 2/3. El fallo **no era del modelo**: en los
fixtures sembrados el campo `intuition` contiene una **pista**
("The proposed function solves the differential equation but may fail the
initial conditions" — enunciado **verdadero**) mientras la proposición
decidible vive en `objective`. El analista juzgó la pista correctamente; el
instrumento anclaba al campo equivocado.

Corregido: el prompt identifica P (la proposición del objetivo cuando lo
enuncia; la dirección si no) con la orden explícita *"Judge P itself. Never
judge the hint, the method suggestion, or the framing remark"*; la dirección
viaja etiquetada como pista; y el ancla acepta el objetivo por sí solo.
Regresión: `test_prompt_judges_the_proposition_not_the_hint` y
`test_an_objective_alone_is_a_valid_anchor`.

Suite completa tras la corrección: **320 passed, 6 skipped, 41 subtests**.

## Estado del instrumento H1

**Validado.** El tier standard (43 casos) ya mide aceptación falsa real y no
desajuste de etiquetas.
