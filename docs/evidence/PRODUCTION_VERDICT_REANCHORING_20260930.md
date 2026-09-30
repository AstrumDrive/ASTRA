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

Informe: `workspace/quality_benchmark_runs/quality_20260930_175755.json`.

| Caso | Esperado | Observado | Fase | Conjetura (s) |
|---|---|---|---|---:|
| `quality_logic_sqrt_square_all_reals_false` | REFUTED | API_ERROR | translator | 632 |
| `logic_false_square_claim` | REFUTED | API_ERROR | translator | 1045 |
| `quality_ode_harmonic_wrong_initial_solution_false` | REFUTED | API_ERROR | translator | 838 |

Los tres ciclos murieron en el traductor a los 4-6 s con
`'claude-opus-5-5': Failed to authenticate: OAuth session expired and could
not be refreshed`. `claude auth status` del CLI npm que ASTRA invoca devolvió
`loggedIn: false` (la app de escritorio usa su propia sesión y seguía
funcionando). **El canario no probó el porte**: ningún ciclo llegó al
analista. Sí midió el coste de no comprobar la sesión antes de conjeturar:
2.515 s de conjetura en Codex y agy gastados para nada. De ahí el chequeo de
autenticación previo al ciclo (`core/preflight.py::cli_auth_state`, fase
`preflight`, `ASTRA_CLI_AUTH_PREFLIGHT`, commit `61fc184`).

**Segunda corrida, con la sesión restaurada** (`claude auth login` por
Nelson; informe `workspace/quality_benchmark_runs/quality_20260930_190417.json`):

| Caso | Esperado | Observado | `status` | `original_claim_verdict` | s |
|---|---|---|---|---|---:|
| `quality_logic_sqrt_square_all_reals_false` | REFUTED | **REFUTED** | VALIDATED | REFUTED | 1.062 |
| `logic_false_square_claim` | REFUTED | **REFUTED** | VALIDATED | REFUTED | 1.164 |
| `quality_ode_harmonic_wrong_initial_solution_false` | REFUTED | **REFUTED** | VALIDATED | REFUTED | 1.144 |

Razonamientos del analista, textuales:

- "The objective's proposition that sqrt(x^2) = x for every real x is refuted
  by the validated counterexample x = -1."
- "The original proposition says x^2 + 1 < 1 for every real x; the validated
  counterexample x = 0 gives equality, so the proposition is false."
- "P is that the proposed function solves the specified IVP; the exact check
  shows it satisfies the ODE but violates y(0) = 1 for every real omega."

Los tres ciclos validaron la conjetura contraria (el contraejemplo) y
respondieron REFUTED sobre el claim pedido: exactamente el patrón que la
producción anterior devolvía como `VALIDATED` a secas. 3 de 3, igual que la
verificación viva de 2.0 del 2026-08-12. Modelos: conjetura `gpt-6-luna` +
`gemini-3.1-pro-high`, traductor `claude-opus-5-5`, revisor y analista
`gpt-6-luna`.

Dos observaciones de coste que salen de las cifras de fase, sin cambiar nada:
la conjetura en ensemble Codex + agy costó 650, 806 y 815 s por ciclo (el
`.env` vivo tiene `ASTRA_CONJECTURE_PROVIDER=codex_cli,agy_cli`), y la
navegación posterior al ciclo, 241 s de agy en cada uno
(`ASTRA_NAVIGATE_AFTER_CYCLE=1`). Entre las dos son el 80 % del tiempo de
cada ciclo del canario.

### Tier estándar completo: aplazado por cuota

Decisión de Nelson (2026-09-30): la cuota de modelos no da para el tier
estándar (43 casos, unas 2,5 h) ahora. El porte sale a producción con los
tests sin cuota en verde, la verificación en vivo de 2.0 de agosto sobre el
mismo cambio y el canario de tres casos de arriba. Referencia a batir cuando
se corra: la corrida de producción del 2026-08-17 (aceptación falsa 0,42,
exactitud estricta 0,52, fallo operativo 0,26).

### Plan de pruebas mientras se usa

Solo Nelson usa ASTRA de momento, así que el uso real es el banco de pruebas:

1. **Cada ciclo real** trae ahora `original_claim_verdict` y
   `original_claim_reasoning` en su resultado. Un `VALIDATED` con veredicto
   re-anclado distinto de SUPPORTED es exactamente el caso que antes engañaba:
   leer siempre los dos campos, no solo `status`.
2. **`scripts/audit_cycle_pool.py`** cuenta, sobre el pool de checkpoints, los
   ciclos que llevan el eje, la distribución de veredictos re-anclados y los
   VALIDATED que no sostienen el claim pedido. Correrlo sin cuota cuando se
   quiera saber cómo va.
3. **Tier smoke periódico** (13 casos: 6 ciclos, 4 ejecuciones, 3 auditorías;
   incluye los tres claims falsos sembrados):

   ```powershell
   .\venv\Scripts\python.exe scripts\run_quality_benchmarks.py --tier smoke --oracle local
   ```

   Cadencia sugerida: tras cada cambio en analista, traductor, revisor o
   escaleras de modelos, y como mínimo una vez por semana de uso.
4. **Tier estándar** antes de compartir ASTRA con otros usuarios: es la única
   corrida que da la cifra de aceptación falsa comparable con agosto.
