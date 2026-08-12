# ASTRA 2.0 — evidencia de la etapa 3: política de decisión y widening

Fecha: 2026-08-12

Autorización: Nelson autorizó explícitamente la etapa 3 (§7.3 de `HANDOFF.md`).

Base: commit `961a838`; el código de esta etapa entra en el mismo commit que
introduce este documento.

## Alcance implementado

`core/campaign_decision.py` (nuevo, puro — sin modelos, red, MCP ni ASTRUM):

- **Tabla de reglas ordenada, primera coincidencia gana**, derivada solo del
  ledger reproducido:
  - `R1-goal-complete`: deliverables resueltos → `CLOSE` + `COMPLETED`;
  - `R2-campaign-exhausted`: el remanente no cubre ningún plan → `CLOSE` +
    `EXHAUSTED`;
  - `R3-refutation`: refutación científica del claim de la rama → rama
    `REFUTED` + `PROMOTE` de la mejor alternativa (widening tras evidencia
    negativa) o `REQUEST_HUMAN_REVIEW` + `PAUSED`;
  - `R4-branch-exhausted`: la rama consumió su presupuesto propio de ciclos
    (derivado de sus episodios) → `EXHAUSTED` + promover;
  - `R5-uninformative`: ≥2 episodios consecutivos `NOT_TESTED`/`INCONCLUSIVE`
    → `SUSPEND` + promover; uno solo reintenta (`CONTINUE`);
  - `R6-affordability`: el activo no puede costear su plan pero una
    alternativa sí → `SUSPEND` + `PROMOTE`;
  - `R7-continue`: default cuando la evidencia es informativa.
- **Selección lexicográfica** sobre el vector de prioridad visible
  (información ↓, independencia ↓, avance ↓, coste ↑, riesgo ↑, id de rama
  como desempate), re-ejecutando los seis hard gates, la regla R4 de familias
  prohibidas (incluida la familia de la rama recién refutada/agotada) y la
  costeabilidad del plan en el momento de promover.
- **`Decision` records completos**: acción, regla aplicada, traza por
  candidato (gates/prohibición/costeabilidad), alternativas consideradas,
  razones, snapshot exacto de presupuesto (validado por el reducer), y la
  recomendación de modelo almacenada aparte — con test de que **no puede
  anular un hard gate fallido** (se anota "cannot override" y la política
  elige por sí misma).
- **`select_initial_branch`**: bootstrap `SELECT` de la primera rama activa.
- **`campaign_step`**: el átomo del lazo — episodio → decisión → eventos →
  checkpoint. El test de dos pasos cierra el círculo completo: un ciclo
  VALIDATED promueve la alternativa del portafolio a ADMISSIBLE; el ciclo
  siguiente refuta la rama activa y la política activa esa alternativa.
- Helpers deterministas: `branch_spent` (gasto por rama derivado de sus
  episodios) y `uninformative_streak`.

El widening nunca es gratuito: solo se dispara por evidencia negativa o
inconclusa, agotamiento de presupuesto (de campaña o de rama) o
incosteabilidad — exactamente las condiciones de la revisión de arquitectura.
Saturación de evidencia y "alternativa independiente de alto valor" quedan
documentadas como disparadores diferidos (requieren métricas aún no
definidas).

Tests: `tests/test_campaign_decision.py` (14 tests), todos con resultados de
ciclo enlatados y sin llamadas de modelo.

## Comandos y resultados

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_campaign_decision.py -q
# 14 passed in 1.18s

.\venv\Scripts\python.exe -m pytest -q
# 278 passed, 6 skipped, 28 subtests passed in 13.81s

.\venv\Scripts\python.exe scripts\audit_architecture.py
# "status": "PASS"

.\venv\Scripts\python.exe scripts\run_research_trajectory_benchmarks.py --dry-run
# fingerprint=ef119a1e27e51481483ef1166792bec9442a3147c2e5f5436e3918eb2e079054
# (idéntico al protocolo congelado; 8 celdas)
```

Entorno sin cambios: Python `3.12.10`, `pip freeze` SHA-256
`59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5`.

## Interpretación

Con las etapas 1–3, el lazo de campaña de ASTRA 2.0 está completo en
desarrollo: síntesis → portafolio → episodio → evidencia → decisión
determinista → siguiente rama, todo append-only y reproducible. Faltan las
etapas 4–7 de §7 (resume de campaña sobre el checkpoint existente,
interfaces `astra_campaign_*` de desarrollo, canary y ablations comparativas,
y solo entonces UI/MCP/remoto). Ningún resultado de esta etapa es evidencia
científica; H1–H4 siguen pendientes de pre-registro.
