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

## 4. Resultados

Pendientes de la corrida de los dos brazos.
