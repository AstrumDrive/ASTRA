# ASTRA 2.0 — evidencia del primer corte: dominio y persistencia de campañas

Fecha: 2026-08-12

Base: commit `9903524` (rama `astra-2.0`); el código de este corte entra en el
mismo commit que introduce este documento.

## Alcance implementado

Exactamente el bloque autorizado en `HANDOFF.md` §6 bajo el contrato congelado
`docs/architecture/ASTRA2_IMPLEMENTATION_CONTRACT.md`:

- `core/campaign_models.py` — Campaign, Branch, Episode, Claim, Evidence,
  Decision y EventEnvelope; enums cerrados; tablas de transición; validación
  fail-closed de ids, timestamps UTC, presupuestos, referencias y rutas
  portables; serialización JSON estable `astra-campaign/0.1`.
- `core/campaign_store.py` — `events.jsonl` append-only con cadena de hashes
  canónicos; replay fail-closed; `TRUNCATED_TAIL` explícito que bloquea
  escrituras hasta archivar la cola; checkpoint atómico (temporal + fsync +
  `os.replace`) validado contra el ledger; lock de escritor único.
- `core/campaign_policy.py` — reducer determinista de replay; transiciones
  fail-closed; invariante de una sola rama activa; contabilidad fail-closed de
  las seis dimensiones de presupuesto; seis hard gates de admisibilidad;
  separación estructural entre error operativo y refutación científica.
- Tests: `tests/test_campaign_models.py`, `tests/test_campaign_store.py`,
  `tests/test_campaign_policy.py`.

No se tocó `astra_cycle`, MCP, GUI, ASTRUM, remotos ni producción. Ningún test
nuevo llama a modelos, red o ejecución remota.

## Comandos y resultados

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_campaign_models.py `
  tests\test_campaign_store.py tests\test_campaign_policy.py -q
# 82 passed, 23 subtests passed in 0.60s

.\venv\Scripts\python.exe -m pytest -q
# 218 passed, 6 skipped, 25 subtests passed in 13.84s

.\venv\Scripts\python.exe scripts\audit_architecture.py
# "status": "PASS"; sin fallos requeridos
```

Entorno: Python `3.12.10`, fingerprint `pip freeze` SHA-256
`59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5`
(sin cambios respecto a la línea base del 2026-08-11). Los 6 skips son los
mismos cachés externos opcionales documentados en la línea base.

## Cobertura de los criterios de aceptación del contrato (§9)

| Criterio | Tests |
|---|---|
| Round-trip JSON estable de todos los records | `RoundTripTests` |
| Ids, timestamps, referencias, estados y transiciones inválidos fallan cerrados | `FailClosedValidationTests`, `TransitionTests`, `ReferenceValidationTests`, `TransitionAndInvariantTests` |
| El fingerprint de un Claim cambia con el alcance semántico | `ClaimFingerprintTests` |
| Append/replay determinista e idempotente | `AppendReplayTests` |
| Mutación de la cadena de hashes detectada | `ImmutabilityTests`, `EventEnvelopeTests`, `test_hash_chain_break_is_detected` |
| Recuperación de cola truncada explícita y bloqueo de escrituras | `TruncatedTailTests` |
| Publicación/recuperación de checkpoint sobrevive interrupción simulada | `CheckpointTests` |
| Escritor único forzado | `SingleWriterTests` |
| Presupuestos e invariante de rama activa única | `BudgetTests`, `test_single_active_branch_is_enforced` |
| Aislamiento entre campañas | `CampaignIsolationTests` |
| Suite heredada completa sin modelos/red/MCP/remoto | `pytest -q` completo |

## Interpretación

Esta evidencia cubre únicamente la capa de dominio y persistencia del primer
corte. No valida el controlador de campañas, la integración con `astra_cycle`,
motores, ASTRUM ni calidad científica alguna. G1 sigue `PARTIAL` (test
end-to-end de producción pendiente de portar) y G2–G6 siguen pendientes. No es
un resultado promocional.
