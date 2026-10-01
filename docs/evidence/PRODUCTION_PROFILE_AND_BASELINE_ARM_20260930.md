# Perfil de producción `no-ensemble` y brazo base "un modelo solo" (2026-09-30)

Segunda tanda de acciones de la auditoría de eficiencia
(`ASTRA_EFFICIENCY_AUDIT_20260930.md`), decididas por Nelson el mismo día:
ciclos más baratos con la misma ruta de veredicto, y la medición que la
auditoría señaló como nunca hecha, la del modelo sin ayuda.

## 1. Perfil de producción: `no-ensemble`

En el canario del re-anclaje (`PRODUCTION_VERDICT_REANCHORING_20260930.md`)
cada ciclo de 18 minutos gastó 650-815 s en la conjetura en ensemble Codex +
agy y 241 s en la navegación posterior con agy: el 80 % del tiempo en dos
fases que no tocan la ruta del veredicto (traductor, revisor, oráculo,
analista).

Cambio aplicado en el `.env` vivo (respaldo `.env.bak_20260930`):

| Variable | Antes | Ahora |
|---|---|---|
| `ASTRA_ARCHITECTURE_PROFILE` | `full` (con la prueba de Muse activa por overlay) | `no-ensemble` |
| `ASTRA_CONJECTURE_PROVIDER` | `codex_cli,agy_cli` | `codex_cli` |
| `ASTRA_NAVIGATE_AFTER_CYCLE` | `1` | `0` |

La prueba de Muse (`config/muse_trial.enabled`, 30 días desde el 2026-09-03)
se apagó el mismo día: su overlay forzaba tres proponentes y el perfil
`muse-trial`.

Contrato (`core/architecture_contract.py`): `no-ensemble` pasa a ser un
perfil de producción reconocido, con id propio `astra-single-proposer-v1`,
un proponente, navegación esperada apagada, y el mismo traductor (Opus 5.5
primero), revisor, analista y reparador que `full`. Un `no-ensemble` con
navegación encendida o con dos proponentes falla cerrado. La topología del
manifiesto ya no anuncia `agy_research_navigation` cuando la navegación está
apagada. `full` sigue disponible para un ciclo profundo a mano.

Verificado: `audit_architecture.py` PASS con el `.env` vivo (perfil
`no-ensemble`, id `astra-single-proposer-v1`, topología
`single_frontier_proposal`), doctor PASS, tests del contrato.

## 2. Brazo base "un modelo solo"

Configuración `single-model` (`core/architecture_configs.py`): un solo
proponente Codex, el mismo Codex escribe el validador y lee la salida del
oráculo, sin revisor independiente (`ASTRA_CODE_REVIEW=0`), sin reparación
(`ASTRA_VALIDATOR_REPAIR_VNEXT=0`), sin guarda determinista
(`ASTRA_VERDICT_GUARD=0`, interruptor nuevo en `astra_tool._apply_guard`),
sin reintentos, sin detector de atasco y sin navegación. Se conserva solo la
ejecución en el oráculo, porque un modelo solo también puede correr código.
A diferencia de `codex-only`, no duplica la llamada de propuesta: mide al
modelo sin ayuda, no un control emparejado por número de llamadas.

Comparación prevista, sobre los 23 casos científicos congelados del tier
estándar (12 claims falsos, 11 verdaderos), con el oráculo local y la
puntuación re-anclada:

```powershell
.\venv\Scripts\python.exe scripts\run_quality_benchmarks.py --tier standard --tracks cycle --oracle local --config single-model
.\venv\Scripts\python.exe scripts\run_quality_benchmarks.py --tier standard --tracks cycle --oracle local --config no-ensemble
```

Métricas a comparar: aceptación falsa, rechazo falso, exactitud estricta,
fallo operativo, latencia y coste registrado. La referencia histórica es la
corrida de producción del 2026-08-17 (aceptación falsa 0,42 antes del
re-anclaje).

## 3. Prueba periódica

Tarea programada de la app (`astra-smoke-semanal`, lunes 08:00 local): doctor
sin cuota primero (si un CLI no tiene sesión, no corre), tier smoke con
prioridad baja, comparación con la corrida anterior, línea del eje re-anclado
de `audit_cycle_pool.py`, registro en `project-memory` y aviso. Solo mide;
no cambia nada.

## 4. Resultados de los dos brazos (2026-09-30, 19:26 a 22:35)

Informes: `workspace/quality_benchmark_runs/quality_20260930_202535.json`
(`single-model`) y `quality_20260930_223541.json` (`no-ensemble`, la
producción vigente). Mismos 23 casos científicos, oráculo local, puntuación
re-anclada, una repetición por caso.

| Métrica | Modelo solo | Producción `no-ensemble` |
|---|---:|---:|
| Exactitud estricta | 0,739 (17/23) | 0,739 (17/23) |
| Exactitud balanceada | 0,735 | 0,739 |
| Aceptación falsa | 0,0 (0/12) | 0,083 (1/12) |
| Rechazo falso | 0,0 | 0,0 |
| Fallo operativo | 0,130 (3/23) | 0,087 (2/23) |
| Latencia p50 / p95 | 131 s / 248 s | 251 s / 642 s |
| Reloj total de los 23 casos | 59 min | 130 min |

Casos discordantes: 3 que solo acertó el modelo solo (Minkowski plano, donde
producción estructuró una conjetura parcial y respondió INCONCLUSIVE; la
solución errónea del oscilador, ver abajo; la factorización en Sage, donde el
validador de producción cayó en un `TypeError` de la pila Sage 9.2) y 3 que
solo acertó producción (equilibrio logístico, Lean 4 y la traza de la
evolución unitaria, los tres CODE_ERROR o INCONCLUSIVE en el modelo solo).
Tres fallaron en ambos. Con 3 pares discordantes por lado no hay diferencia
estadística posible (McNemar exacto p = 1).

**Lectura honesta.** Sobre este benchmark, la deliberación de producción
(revisor independiente, guarda, reparación, reintento) no acierta más que un
modelo de frontera que escribe, ejecuta y lee su propio validador: misma
exactitud, 2,2 veces más lenta, y en esta corrida una aceptación falsa que el
modelo solo no cometió. Lo que producción sí compra aquí es fiabilidad
operativa (rescató el caso de Lean y dos CODE_ERROR). La pregunta "¿ASTRA es
más potente que los modelos sueltos?" queda respondida para este corpus:
**no en exactitud**. El corpus es pequeño y fácil para un modelo de frontera
(la misma saturación que mostró el piloto del revisor); los claims de
investigación real son otra cosa y ahí no hay medición comparable todavía.

Dos salvedades a favor de la arquitectura: el brazo "modelo solo" no es un
modelo desnudo, usa el oráculo de ASTRA y el prompt del analista con
re-anclaje, es decir, las dos piezas que la auditoría señaló como las que sí
rinden; y la aceptación falsa de producción no fue un juicio equivocado sino
un agujero de ingeniería, descrito a continuación y cerrado el mismo día.

**La aceptación falsa de producción, trazada.** Caso
`quality_ode_harmonic_wrong_initial_solution_false` (que el canario de las
19:04 había refutado bien). Primera pasada del analista: CODE_ERROR con
`original_claim_verdict: REFUTED` y la razón correcta (y(0)=0≠1), pidiendo
comprobar también y'(0). Reintento: parche del traductor, revisión aprobada,
ejecución PASS, y la respuesta final del analista no se pudo parsear. El
fallback de `analyze_results` devolvía entonces `VALIDATED` con "the final
analyst response was not parseable" y SIN eje re-anclado, así que el
benchmark (y cualquier lector) lo tomó como claim sostenido. Corrección:
ante una respuesta no parseable tras un PASS limpio, el analista se llama
una segunda vez; si tampoco parsea, el fallback mantiene `VALIDATED` para la
conjetura probada pero declara `original_claim_verdict: INCONCLUSIVE` con su
razón, que el benchmark puntúa como no respondido y nunca como aceptación.
Tests en `tests/test_verdict_reanchoring.py` (`UnparseableAnalystTests`).
