# Producción: re-anclaje del veredicto al claim original (2026-09-30)

Primera acción de la auditoría de eficiencia
(`ASTRA_EFFICIENCY_AUDIT_20260930.md`, recomendación 1), autorizada por Nelson
el 2026-09-30 junto con la decisión de arreglar la línea 1.0 y llevar 2.0 a
producción con el tiempo.

## Problema

`astra_tool` reportaba el estado de la **conjetura formada**, no del **claim
que el usuario formuló**. Con la postura neutral del conjeturador (probar o
refutar), ASTRA corrige un claim falso, valida la versión corregida y devuelve
`VALIDATED`, con la refutación enterrada en la prosa. Medido en la línea 1.0 el
2026-08-17 sobre 23 casos científicos: aceptación falsa 0,42, cinco claims
falsos aceptados (`Dev/ASTRA-2.0/docs/evidence/ASTRA1_VS_ASTRA2_STANDARD_20260817.md`).
La corrección existía desde el 2026-08-12 en la línea 2.0
(`ASTRA2_VERDICT_REANCHORING_20260812.md`, commits `a29b9fe` y `673b9d7`) y
nunca se había portado.

## Qué se portó

Eje separado, nunca colapsado con `status`:

- `agents/analyst.py`: regla 3, "VERDICT RE-ANCHORING (mandatory, always
  emitted)". El analista juzga P, la proposición decidible del objetivo
  compartido, no la pista ni la sugerencia de método, y responde en
  `original_claim_verdict` con SUPPORTED, REFUTED, INCONCLUSIVE o SUBSTITUTED,
  más `original_claim_reasoning`. Una conjetura del tipo "X es contraejemplo de
  P" que pasa significa P REFUTED.
- `core/llm_client.py`: `ORIGINAL_CLAIM_VERDICTS`,
  `_normalize_original_claim_verdict` (enum cerrado; ausente o desconocido →
  UNSPECIFIED; sin ancla → UNSPECIFIED; nunca reescribe `status`) y el bloque
  "USER'S CURRENT DIRECTION OR HINT" en el prompt de `analyze_results`. En
  producción convive con la normalización de `missing_inputs` y la regla de que
  solo el validador puede declarar NON_DECIDABLE; la llamada de normalización
  se aplica antes de esa regla, dentro del mismo `if parsed is not None`.
- `astra_tool.py`: la intuición (claim original) viaja al analista en el
  camino lineal y en el ensemble; `_ensemble_report` muestra el veredicto
  re-anclado de cada analista; el resultado del ciclo expone
  `original_claim_verdict` (UNSPECIFIED si falta) y `original_claim_reasoning`.
- `scripts/run_quality_benchmarks.py`: `_reanchored_status` puntúa el claim
  sembrado: SUPPORTED → VALIDATED, REFUTED → REFUTED, SUBSTITUTED e
  INCONCLUSIVE se mantienen distintos de ambos valores de verdad; sin el
  campo, comportamiento histórico.
- `tests/test_verdict_reanchoring.py` (16 tests, 13 subtests): contrato del
  prompt, enum cerrado, no fabricación, llegada del claim al analista, ciclo
  completo con dobles que expone los dos ejes en desacuerdo, puntuación del
  benchmark y la prueba de que los registros medidos el 2026-08-12 pasan de
  aceptación falsa 1,0 a 0,0.
- `scripts/prune_test_cycle_artifacts.py`: la intuición del test nuevo queda
  registrada para que el pruner reconozca sus artefactos.
- `scripts/set_benchmark_priority.ps1` traído de 2.0 para correr el tier
  estándar sin degradar la estación.

Método: `git apply --3way` del diff `a29b9fe^..673b9d7` de 2.0 sobre
producción; dos conflictos resueltos a mano (la firma de `_ensemble_analysis`,
donde el diff arrastraba un helper de campañas que producción no usa, y el
bloque de normalización del analista, que en producción ya contiene
`missing_inputs` y la regla NON_DECIDABLE).

## Verificación sin cuota

- `tests/test_verdict_reanchoring.py`: 16 passed.
- Suite completa: 574 passed (el único fallo fue el registro del pruner,
  corregido).
- `scripts/audit_architecture.py`: PASS; doctor PASS.

## Verificación en vivo

Pendiente de rellenar con los informes de `workspace/quality_benchmark_runs/`.

### Canario: los tres claims falsos sembrados

Comando:

```powershell
.\venv\Scripts\python.exe scripts\run_quality_benchmarks.py --tier standard --oracle local --only quality_logic_sqrt_square_all_reals_false,logic_false_square_claim,quality_ode_harmonic_wrong_initial_solution_false
```

| Caso | Esperado | Observado | `original_claim_verdict` |
|---|---|---|---|
| `quality_logic_sqrt_square_all_reals_false` | REFUTED | pendiente | pendiente |
| `logic_false_square_claim` | REFUTED | pendiente | pendiente |
| `quality_ode_harmonic_wrong_initial_solution_false` | REFUTED | pendiente | pendiente |

### Tier estándar completo (43 casos: 23 científicos, 14 de auditoría, 6 de ejecución)

Pendiente. Referencia a batir: la corrida de producción del 2026-08-17
(aceptación falsa 0,42, exactitud estricta 0,52, fallo operativo 0,26).
