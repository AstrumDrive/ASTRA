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

## Límite honesto

Los tests son deterministas y con dobles: prueban el contrato, el cableado y
la puntuación. **Falta confirmar en vivo** que los modelos reales rellenan el
campo correctamente (el prompt es nuevo). Verificación barata propuesta: los
tres casos de refutación sembrada (~3 ciclos, ~30 min) antes de gastar el
tier standard de 43 casos.
