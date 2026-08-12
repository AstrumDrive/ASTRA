# ASTRA 2.0 — evidencia de la etapa 2: `astra_cycle` como ejecutor de Episode

Fecha: 2026-08-12

Autorización: Nelson autorizó explícitamente la etapa 2 (§7.2 de `HANDOFF.md`).

Base: commit `4170cf3`; el código de esta etapa entra en el mismo commit que
introduce este documento.

## Alcance implementado

- `core/campaign_executor.py` (nuevo): el ciclo atómico envuelto como ejecutor
  de un `Episode`, **sin tocar la conducta del ciclo**:
  - `run_episode(store, branch_id, cycle_runner=...)` — pre-gates fail-closed
    ANTES de cualquier llamada de modelo (campaña ACTIVE, rama ACTIVE,
    presupuesto restante cubre el plan de evidencia de la rama); construye la
    petición del ciclo desde el estado (`build_episode_request`) y ejecuta el
    `cycle_runner` inyectable (el `_do_cycle` real es solo el default).
  - `build_portfolio_context(state)` — el contexto R4 vivo: los deliverables
    no resueltos, las clases de evidencia permitidas y las familias de método
    de ramas EXHAUSTED/REFUTED/CLOSED entran como prohibidas al prompt de
    síntesis.
  - `map_cycle_outcome(result)` — proyección determinista y documentada a los
    cinco ejes: `CODE_ERROR` → evidencia `OPERATIONAL_ERROR` + claim
    `NOT_TESTED` (un traceback jamás refuta); `REFUTED` →
    `SCIENTIFIC_REFUTATION`; `API_ERROR`/`PARTIAL` → operación `FAILED` sin
    evidencia; fuerza `SCOPED` solo con revisión independiente APPROVED.
  - `record_episode_result` — transcripción a eventos del ledger:
    `BUDGET_CHARGED` (4 dimensiones reales del ciclo), `CLAIM_RECORDED` del
    claim realmente testeado (deduplicado por fingerprint contra el estado),
    `EVIDENCE_RECORDED` (actor `oracle`, artefactos `validator.py` +
    `stdout.txt` escritos y hasheados bajo `artifacts/<episode>/`),
    `EPISODE_RECORDED` con los cinco ejes separados, y checkpoint atómico.
  - Promoción viva de las alternativas del portafolio: cada minoritaria queda
    como rama `PROPOSED` con su claim, y los seis hard gates + la regla R4 de
    familias prohibidas deciden `ADMISSIBLE`/`REJECTED` con el resultado de
    los gates registrado en el evento.
  - Contabilidad fail-closed con degradación explícita: un sobregasto real se
    registra hasta el remanente con la cifra real en el `reason` del evento y
    el informe (`EpisodeRunReport`) marca `budget_exhausted`.
- `core/campaign_policy.py`: helper `exhausted_method_families(state)` (R4).
- Tests: `tests/test_campaign_executor.py` (19 tests, 3 subtests), todos con
  `cycle_runner` falso — sin modelos, red, MCP ni ASTRUM.

Lo que NO hace esta etapa (queda para la 3): elegir qué rama se activa,
progressive widening, resolución de deliverables y cierre/agotamiento
automático de campaña. El ejecutor registra; no decide.

## Comandos y resultados

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_campaign_executor.py -q
# 19 passed, 3 subtests passed in 0.82s

.\venv\Scripts\python.exe -m pytest -q
# 264 passed, 6 skipped, 28 subtests passed in 12.69s

.\venv\Scripts\python.exe scripts\audit_architecture.py
# "status": "PASS"

.\venv\Scripts\python.exe scripts\run_research_trajectory_benchmarks.py --dry-run
# fingerprint=ef119a1e27e51481483ef1166792bec9442a3147c2e5f5436e3918eb2e079054
# (idéntico al protocolo congelado; 8 celdas)
```

Entorno sin cambios: Python `3.12.10`, `pip freeze` SHA-256
`59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5`.

## Interpretación

El lazo del preprint (evidencia intermedia por episodio con re-inyección de
contexto) ya tiene su transcripción auditable: cada ciclo deja presupuesto,
evidencia con artefactos hasheados, episodio con cinco ejes y ramas nuevas en
el ledger. Ningún resultado de esta etapa es evidencia científica; el canary
comparativo (etapa 6 de §7) y las hipótesis H1–H4 siguen pendientes de
pre-registro y ejecución bajo protocolo congelado.
