# ASTRA 2.0 — evidencia de la etapa 1: portafolio estructurado de la síntesis

Fecha: 2026-08-12

Autorización: Nelson autorizó explícitamente la etapa 1 (§7.1 de `HANDOFF.md`)
con la recomendación del documento de contraste
`docs/architecture/ASTRA2_PREPRINT_2602.03837_CONTRAST.md`: R3 + R4 en el
diseño del portafolio y R1 como auditoría de prompts.

Base: commit `47687bd`; el código de esta etapa entra en el mismo commit que
introduce este documento.

## Alcance implementado

- `core/campaign_portfolio.py` (nuevo, puro, sin llamadas de modelo):
  - bloque cercado ```` ```astra-portfolio ```` con JSON `astra-portfolio/0.1`;
  - `Portfolio`/`PortfolioCandidate` fail-closed: crux obligatorio en el
    seleccionado (**R3**), familias de método únicas entre candidatos
    ("materially different"), tope de 4 candidatos (progressive widening),
    campos portables, enums cerrados reutilizados del primer corte;
  - parsing **fail-soft** para el ciclo (`parse_portfolio`): bloque ausente o
    inválido se registra como error y el texto de la conjetura queda limpio;
  - `forbidden_family_violations` + `negative_prompt_block` ("DO NOT use…")
    (**R4**), `portfolio_instruction_block` con deliverables y clases de
    evidencia permitidas;
  - `portfolio_to_records`: conversión determinista y fail-closed a pares
    `(Claim, Branch)` del primer corte; crux → `unresolved_obligations`;
    deliverable validado contra la campaña.
- `astra_tool.py`:
  - `_ensemble_conjecture` acepta `portfolio_context` y, con
    `ASTRA_PORTFOLIO_SYNTH` ≠ "0" (default ON), añade el addendum al prompt
    del merge, extrae el bloque del texto mergeado (el traductor recibe la
    conjetura limpia) y publica `deliberation["portfolio"]`,
    `portfolio_error` y `portfolio_forbidden_violations`;
  - la síntesis degradada a concatenación reporta explícitamente la ausencia
    de portafolio;
  - `ASTRA_PORTFOLIO_SYNTH` y `portfolio_context` entran al payload de caché
    del ciclo (sin replay obsoleto entre configuraciones).
- `agents/conjecture.py`: regla 7 "NEUTRAL STANCE — prove OR refute, never a
  fact to confirm" (**R1**). Auditoría del resto: `analyst.py` ("free of
  confirmation bias"), `reviewer.py` (honest failure over false validation),
  `navigator.py` y `_MERGE_SYSTEM` ("prueba y refutacion") ya eran neutros;
  se fijan con tests de contrato.
- `core/campaign_models.py`: helper público `validate_method_family`
  (fuente única de la regla; `Branch` lo reutiliza). Sin cambios semánticos
  del contrato congelado.
- Tests: `tests/test_campaign_portfolio.py` (27 tests).

Las propuestas minoritarias ya no se borran: sobreviven como candidatos
estructurados listos para ser promovidos a ramas del ledger en la etapa 2.

## Comandos y resultados

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_campaign_portfolio.py -q
# 27 passed in 0.42s

.\venv\Scripts\python.exe -m pytest -q
# 245 passed, 6 skipped, 25 subtests passed in 12.52s

.\venv\Scripts\python.exe scripts\audit_architecture.py
# "status": "PASS"

.\venv\Scripts\python.exe scripts\run_research_trajectory_benchmarks.py --dry-run
# fingerprint=ef119a1e27e51481483ef1166792bec9442a3147c2e5f5436e3918eb2e079054
# (idéntico al protocolo congelado; 8 celdas)
```

Entorno sin cambios: Python `3.12.10`, `pip freeze` SHA-256
`59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5`.

## Límites de la etapa

- El ciclo **no** falla nunca por el portafolio (fail-soft): la conexión
  fail-closed con campañas llega con el controlador (etapa 2).
- Los candidatos convertidos usan un `PriorityVector` neutro documentado como
  placeholder; el Navigator aportará estimaciones en una etapa posterior.
- Nada se conecta a MCP, GUI, ASTRUM ni producción. Ningún resultado de esta
  etapa es evidencia científica ni de las hipótesis H1–H4, que siguen
  pendientes de pre-registro y ejecución bajo protocolo congelado.
