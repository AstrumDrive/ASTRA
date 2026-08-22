# ASTRA 2.0 — handoff de desarrollo

Actualizado: 2026-08-21

Estado: **DEVELOPMENT ONLY — no usar como ASTRA de producción**

## 1. Ubicación y propósito

El proyecto de desarrollo está alojado en:

```text
C:\Users\Nelson\Dev\ASTRA-2.0
```

- Rama de trabajo: `astra-2.0`
- ASTRA de producción, separado: `C:\Users\Nelson\Dev\ASTRA`
- Commit estable desde el cual se creó el clon:
  `e4752eada0dc78b52cc88b98753ae144b6e56041`
- Primer commit propio de la línea 2.0: `a20d807`
- Los remotos permiten `fetch`, pero sus URL de `push` están desactivadas.
- El MCP, los accesos directos, los servicios y el worker de producción continúan
  apuntando a `C:\Users\Nelson\Dev\ASTRA`.

ASTRA 2.0 busca añadir investigación agentica de largo horizonte basada en una
cartera de ramas y evidencia, conservando el ciclo científico probado de ASTRA
como trabajador atómico.

## 2. Protocolo obligatorio al iniciar una sesión

Un agente nuevo debe ejecutar primero:

```powershell
Set-Location -LiteralPath 'C:\Users\Nelson\Dev\ASTRA-2.0'
git status --short --branch
git log -3 --oneline --decorate
Get-Content -LiteralPath 'AGENTS.md'
Get-Content -LiteralPath 'HANDOFF.md'
Get-Content -LiteralPath 'ASTRA2_STATUS.json'
```

Después debe leer completos, en este orden:

1. `ASTRA2_ACCEPTANCE.md` — compuertas que impiden usarlo en producción.
2. `docs/architecture/ASTRA2_ARCHITECTURE_REVIEW.md` — diseño revisado y
   decisiones vigentes.
3. `docs/architecture/ASTRA2_IMPLEMENTATION_CONTRACT.md` — esquema, eventos,
   replay, transiciones y criterios del primer corte.
4. `docs/benchmarks/ASTRA2_BASELINE_2026-08-11.md` — línea base reproducible.
5. `README.md` — capacidades y operación de ASTRA actual.
6. `RESEARCH_TRAJECTORY_BENCHMARK.md` — comparación científica prevista.
7. `VALIDATOR_REPAIR_VNEXT.md` — semántica de revisión y reparación vigente.

Antes de trabajar con artículos también es obligatorio leer
`PUBLICATION_POLICY.md`. Antes de cambiar ejecución remota, leer
`remote/README.md` y `C:\Users\Nelson\REMOTE_CLUSTER_GUIDE.md`.

## 3. Estado comprobado

### Aislamiento

- Checkout y rama separados: completado.
- Entorno Python propio: `venv`, Python `3.12.10`.
- Credenciales, `.env`, tokens, llaves y workspace de producción: no copiados.
- Push a GitHub de Nelson y Astrum Drive: bloqueado hasta aceptación explícita.
- MCP y launchers de producción: sin cambios.
- Lock reproducible: `requirements-workstation-lock.txt`.

### Línea base

Comando:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

Resultado del 2026-08-11:

```text
136 passed, 6 skipped, 2 subtests passed in 30.47s
```

Handoff revalidado el 2026-08-12 con el mismo resultado lógico:
`136 passed, 6 skipped, 2 subtests passed in 26.76s`.

Tras implementar el primer corte (capa de dominio y persistencia de campañas),
el mismo día:

```text
218 passed, 6 skipped, 25 subtests passed in 13.84s
```

Los 82 tests nuevos (más 23 subtests) corren sin modelos, red, MCP ni ASTRUM.
Evidencia: `docs/evidence/ASTRA2_CAMPAIGN_SLICE_20260812.md`.

Comprobaciones locales adicionales del 2026-08-12:

- `scripts/audit_architecture.py`: `PASS`, sin fallos requeridos;
- `scripts/run_research_trajectory_benchmarks.py --dry-run`: `PASS`, ocho
  celdas planificadas sin llamadas de modelos;
- fingerprint del protocolo piloto:
  `ef119a1e27e51481483ef1166792bec9442a3147c2e5f5436e3918eb2e079054`.

La auditoría sólo descubrió rutas/configuración; no ejecutó un smoke test de
cada motor. Lean local y la ruta remota aparecieron sin configurar, por lo que
G2 continúa pendiente.

Los seis skips corresponden a cachés externos opcionales no preparados. No se
consideran evidencia positiva. `h5py 3.16.0` está instalado.

Fingerprint del entorno:

```text
pip freeze SHA-256:
59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5
```

## 4. Qué está implementado y qué no

### Ya existe en el clon

- ciclo atómico multi-modelo Codex + AGY + Claude;
- propuestas paralelas, crítica cruzada y síntesis;
- traducción, revisión y reparación acotada de validadores;
- ejecución local/ASTRUM y múltiples motores científicos;
- separación de error operativo, veredicto de afirmación y cobertura del
  objetivo;
- Research Loop profundidad-primero y registro textual de ramas;
- benchmarks de calidad, diversidad y trayectoria;
- prototipo MCTS experimental separado de producción;
- **primer corte 2.0 (2026-08-12)**: records de dominio de campaña
  (`core/campaign_models.py`), ledger append-only con cadena de hashes,
  cola truncada explícita, checkpoint atómico y escritor único
  (`core/campaign_store.py`), y política determinista con hard gates,
  presupuestos fail-closed y una sola rama activa
  (`core/campaign_policy.py`). Capa pura: sin conexión a `astra_cycle`,
  MCP, GUI ni ASTRUM. Evidencia:
  `docs/evidence/ASTRA2_CAMPAIGN_SLICE_20260812.md`.
- **etapa 1 (2026-08-12, autorizada por Nelson)**: portafolio estructurado
  desde la síntesis del ensemble (`core/campaign_portfolio.py` + wiring en
  `_ensemble_conjecture`, gate `ASTRA_PORTFOLIO_SYNTH` default ON, fail-soft
  en el ciclo). Las propuestas minoritarias sobreviven como candidatos con
  familia de método, delta de supuestos, plan de evidencia discriminante,
  deliverable y crux (R3); familias prohibidas con "DO NOT use" (R4);
  postura neutral en el prompt de conjetura (R1). Conversión determinista a
  `(Claim, Branch)` que pasa los hard gates del primer corte. Evidencia:
  `docs/evidence/ASTRA2_STAGE1_PORTFOLIO_20260812.md`.
- **etapa 2 (2026-08-12, autorizada por Nelson)**: `astra_cycle` envuelto
  como ejecutor de `Episode` (`core/campaign_executor.py`): pre-gates
  fail-closed antes de llamar modelos, contexto R4 vivo desde el estado,
  mapeo determinista del resultado del ciclo a los cinco ejes (un traceback
  jamás refuta), transcripción a eventos (presupuesto real, claim testeado
  deduplicado por fingerprint, evidencia con artefactos hasheados, episodio,
  checkpoint) y promoción de alternativas del portafolio a ramas PROPOSED
  gateadas a ADMISSIBLE/REJECTED. El ciclo en sí no cambió. Evidencia:
  `docs/evidence/ASTRA2_STAGE2_EXECUTOR_20260812.md`.
- **etapa 3 (2026-08-12, autorizada por Nelson)**: política determinista de
  decisión y progressive widening (`core/campaign_decision.py`): tabla de
  reglas R1–R7 (cierre por meta, agotamiento de campaña/rama, refutación,
  racha no informativa, costeabilidad, continuar), selección lexicográfica
  sobre el vector de prioridad con re-validación de gates y familias
  prohibidas, `Decision` records con snapshot exacto y recomendación de
  modelo que no puede anular gates, bootstrap `select_initial_branch` y
  `campaign_step` (episodio → decisión → ledger → checkpoint). El widening
  solo se dispara por evidencia negativa/inconclusa o presión de presupuesto.
  Evidencia: `docs/evidence/ASTRA2_STAGE3_DECISION_20260812.md`.

- **etapa 4 (2026-08-12, autorizada por Nelson)**: resume explícito de
  campaña (`core/campaign_resume.py`): checkpoint como acelerador validado y
  reconstruible (nunca autoridad), bloqueo ante cola truncada hasta archivar,
  recomendación determinista de la siguiente acción, modo solo-lectura sin
  lock, y no-repetición de episodios por construcción. Evidencia:
  `docs/evidence/ASTRA2_STAGE4_RESUME_20260812.md`.

- **etapa 5 (2026-08-12, autorizada por Nelson)**: interfaces de desarrollo
  `astra_campaign_*` (`core/campaign_api.py`): start/status/step/stop/
  reactivate/list sobre `workspace/campaigns`, lock liberado por llamada,
  entradas fail-closed, y garantía probada de que el MCP de producción no
  las registra. Evidencia: `docs/evidence/ASTRA2_STAGE5_DEV_API_20260812.md`.

- **etapa 6 — infraestructura (2026-08-12, autorizada por Nelson)**: canary
  pre-registrado y congelado
  (`docs/benchmarks/ASTRA2_CANARY_PREREGISTRATION_V1.md`, huella
  `9a25c214…` verificada por el runner), `scripts/run_campaign_canary.py`
  con dry-run por defecto, smoke offline completo sin modelos y `--live`
  que exige `--yes` + huella intacta; deduplicación de alternativas
  repetidas en el ejecutor. Evidencia:
  `docs/evidence/ASTRA2_STAGE6_CANARY_INFRA_20260812.md`.

- **canary VIVO (2026-08-12, go explícito de Nelson): PASS en operabilidad.**
  Campaña `cmp_cd11be51fcd34e22`: 2 episodios reales (codex+agy+claude,
  oráculo local), 2 evidencias con artefactos hasheados, decisiones
  R0→R7→R2 y cierre autónomo por presupuesto; 17/36 llamadas, 2384/3600 s.
  Dos hallazgos de integración corregidos con tests de regresión (listas del
  portafolio tolerantes a entradas vacías; forma real del resultado del
  ciclo: `execution`/`cli_models`/`oracle_used`). Evidencia:
  `docs/evidence/ASTRA2_CANARY_LIVE_20260812.md`.

- **H1 smoke limpio (2026-08-12)**: con la configuración íntegra de
  producción, 3/3 auditoría (0 falsas alarmas), 4/4 ejecución, y **cero
  alucinaciones en 5/5 ciclos completados**. La `false_acceptance_rate` de
  0.6667 es un **artefacto de medición**: ASTRA refutó correctamente los
  claims falsos pero reporta el estado de la conjetura formada, no del claim
  original. Evidencia:
  `docs/evidence/ASTRA2_H1_SMOKE_CLEAN_20260812.md`.

- **re-anclaje de veredicto (2026-08-12, autorizado)**: eje separado
  `original_claim_verdict` que responde al claim del usuario, no solo a la
  conjetura formada; verificado en vivo 3/3. Corrige también un defecto de
  producción. Evidencia:
  `docs/evidence/ASTRA2_VERDICT_REANCHORING_20260812.md`.
- **gate H1, tier standard (2026-08-12, autorizado)**: 23 casos científicos,
  **aceptación falsa 0.0 y rechazo falso 0.0**; exactitud estricta 0.739;
  auditoría con recall 1.0; ejecución 6/6. Los seis casos no acertados son
  dos INCONCLUSIVE honestos, tres no-aprobaciones del revisor al tope de una
  revisión, y un timeout: **ningún fallo epistémico**. Evidencia:
  `docs/evidence/ASTRA2_H1_STANDARD_20260812.md`.

- **calibración del revisor (2026-08-12, autorizada)**: distinción decisiva
  vs auxiliar con el guardarraíl "¿el PASS depende de la pierna débil?";
  compuerta verificada intacta (recall 1.0, sampling/hardcoded siguen
  REJECT) y un ciclo muerto convertido en evidencia. Evidencia:
  `docs/evidence/ASTRA2_REVIEWER_CALIBRATION_20260812.md`.
- **bug Unicode de Windows CORREGIDO en 2.0**: PowerShell 5.1 canaliza a
  ejecutables nativos con `$OutputEncoding = us-ascii`, así que `∀` llegaba
  a Codex como `???` y los acentos españoles como `??`. Reproducido sin
  cuota y corregido en `core/cli_backend.py` con test de integración contra
  el `powershell.exe` real. **Producción tiene el mismo defecto y no se ha
  tocado**: portarlo requiere autorización explícita.

- **port del arreglo Unicode a producción (2026-08-13, autorizado)**:
  aplicado y verificado en `C:\Users\Nelson\Dev\ASTRA\core\cli_backend.py`,
  **sin committear** (ese árbol tiene trabajo local vivo, incluido un arreglo
  propio de `ASTRA_CODEX_BIN` que 2.0 aún no tiene). El commit lo decide
  Nelson.
- **fixture EinsteinPy corregido y re-medición hecha (2026-08-13)**: la
  compuerta aguanta (aceptación falsa 0.0 en dos corridas) y la falsa alarma
  de auditoría cayó a 0.0. El cambio en fallo operativo NO es atribuible
  (n=1 por caso, varianza 2× en casos idénticos). Evidencia:
  `docs/evidence/ASTRA2_H1_STANDARD_V2_20260813.md`.

- **`ASTRA_TRANSLATOR_TIMEOUT=480` medido y documentado (2026-08-13)**: 4 de
  7 casos fallidos convirtieron; tres fases de traducción/reparación medidas
  entre 250 y 438 s habrían muerto contra el techo de 240 s. Añadido a
  `.env.example` con su justificación. Evidencia:
  `docs/evidence/ASTRA2_TRANSLATOR_TIMEOUT_20260813.md`.
- **`ASTRA_CODEX_BIN` portado a 2.0** desde producción (f7db415).

- **medición con repeticiones (2026-08-13)**: 12 ciclos, 4 casos × 3. El
  bloqueo del revisor NO es reproducible por caso (2/12, nunca dos veces en
  el mismo caso) ⇒ es varianza y **el cambio estructural queda descartado**.
  El fallo dominante (6/12) es el **presupuesto TOTAL del ciclo**: 1500 s por
  defecto (`astra_tool.py:1090`) − 60 s de buffer = 1440 s útiles, que
  `--cycle-timeout` NO modifica. Evidencia:
  `docs/evidence/ASTRA2_REVIEWER_REPEATS_20260813.md`.

- **distribución por fase medida sin cuota (2026-08-13)**:
  `scripts/analyze_phase_budget.py` sobre 84 ciclos ya depositados, con
  tratamiento explícito de datos censurados. El presupuesto total **no** es
  el problema (p90 de ciclo completo 921 s contra 1440 s útiles: +519 s de
  holgura). El p90 de todas las fases suma 1220 s y cabe — **si ninguna se
  ejecuta dos veces**. La palanca real es la **escalera de modelos**: un
  reintento del traductor duplica la fase (medido: 448/463/481 s con techo
  240) y con techo 480 consume 960 s, más que un ciclo completo entero.
  `translate_patch` era la fase más estrangulada (20 censuras de 64; p90 real
  343 s contra techo 240). Evidencia:
  `docs/evidence/ASTRA2_PHASE_BUDGET_20260813.md`.

- **reparto de presupuesto por fase adoptado (2026-08-13)**: al leer el
  mecanismo, la escalera resultó NO ser la causa (solo avanza ante cuota, no
  ante timeout) y el reintento YA heredaba el restante. El duplicado es el
  reintento deliberado de script mínimo del traductor, no contabilizado. Como
  los techos suman exactamente el presupuesto útil (1440 s), se añadió
  `CycleBudget.phase_timeout(share=)` + `astra_tool.PHASE_BUDGET_SHARE`:
  ninguna llamada puede dejar sin tiempo a las siguientes, y un ciclo normal
  nunca queda recortado. Evidencia:
  `docs/evidence/ASTRA2_PHASE_BUDGET_20260813.md`.

- **inventario de separación y camino a pre-producción (2026-08-13)**:
  `docs/architecture/ASTRA2_SEPARATION_AND_PREPROD.md`. Hallazgo clave:
  `acquire_cycle_slot` crea el candado bajo `<checkout>/workspace/locks`, así
  que **2.0 y producción pueden deliberar a la vez contra la misma cuenta** —
  el candado no cruza checkouts y las credenciales son compartidas por
  diseño. Cuatro decisiones abiertas listadas allí.

- **candado de ciclo compartido ADOPTADO (2026-08-13)**: `cycle_lock_root()`
  usa una raíz de máquina por defecto (`%LOCALAPPDATA%\astra\locks`), con
  `ASTRA_LOCK_ROOT` para aislar líneas con credenciales distintas y caída a
  la ruta histórica si no es escribible. Aplicado en las dos líneas (en
  producción **sin committear**) y verificado cruzando los dos checkouts
  reales. **El MCP de producción necesita reinicio** para cargarlo.

- **chequeo de deriva entre líneas (2026-08-13)**:
  `scripts/check_line_drift.py` compara la superficie de runtime compartida
  contra el commit base y clasifica `PRODUCTION ONLY` / `BOTH CHANGED` /
  `2.0 ONLY` / `PROSE ONLY` (este último por AST, para que una redacción
  distinta tras un port no se reporte como deriva). Primera pasada: 2 cambios
  de producción ausentes en 2.0 (`core/pdf_generator.py`, `main.py`).
- **arreglos portados a producción y COMMITTEADOS** (`9326928` en `main` de
  `Dev/ASTRA`): Unicode de PowerShell + candado de máquina, acotado a esos
  dos ficheros; el resto del trabajo local de Nelson quedó intacto.

- **G2 local CERRADO (2026-08-13)**: `scripts/astra_doctor.py` PASS y
  `scripts/run_engine_smokes.py` **6/6** (python, z3, sage, maxima, cadabra y
  lean4 kernel-checked contra el Mathlib v4.30.0 pineado, `#print axioms`
  limpio). Sin cuota. Se creó un `.env` propio de 2.0 con **solo**
  configuración no secreta (roles de producción + rutas de motores); ninguna
  credencial copiada. Evidencia:
  `docs/evidence/ASTRA2_G2_LOCAL_ENGINES_20260813.md`.
  Trampa anotada: el marcador debe ser `# ASTRA_ENGINE: <motor>`; con otra
  sintaxis de comentario el artefacto se enruta **silenciosamente a Python**.

- **inventario de ASTRUM REGISTRADO (2026-08-13, autorizado)**: 8 motores
  catalogados vía `astra_engine.sh list`, y **verificado** que el oráculo
  formal remoto usa el MISMO toolchain (`v4.30.0`) y el MISMO commit de
  Mathlib (`c5ea0035…`) que el local — condición para que un acuerdo entre
  oráculos signifique algo. Asimetría anotada: la ruta remota llama a `lean`
  sin `lake`, así que artefactos que resuelvan dependencias solo corren en
  local. Evidencia:
  `docs/evidence/ASTRA2_G2_ASTRUM_INVENTORY_20260813.md`.

- **entrada MCP `astra_dev` en los tres clientes (2026-08-14, autorizada)**:
  Codex, Claude Code y Antigravity exponen la línea 2.0 **junto a** producción,
  nunca reemplazándola. `scripts/register_dev_mcp.py` verifica
  programáticamente que la entrada `astra` no cambie y se niega a escribir si
  cambiaría; `--remove --apply` revierte. **`astra` sigue siendo el default de
  hecho** (herramientas namespaceadas por servidor). Las `astra_campaign_*` NO
  se exponen. Evidencia: `docs/evidence/ASTRA2_MCP_DEV_ENTRY_20260814.md`.
  Ojo: NO usar `scripts/configure_antigravity_mcp.py` desde este clon — escribe
  la clave `astra` y sobrescribiría producción.

### Todavía no existe

- **los dos ítems restantes de G2 ENVÍAN TRABAJO REAL al clúster** (acuerdo
  de veredictos entre oráculos con la suite cliente; scheduler, concurrencia,
  timeouts y cancelación): requieren una autorización distinta de la del
  inventario;
- portar a 2.0 los dos cambios `PRODUCTION ONLY` detectados (informe PDF
  enriquecido); no bloquean el lazo de campaña;
- **validación viva del reparto**: los shares están fijados por tests
  deterministas sobre los p90 medidos, pero **no se ha corrido una suite con
  ellos activos**; la comprobación natural es el standard tier;
- `lean_nat_add_comm`: el reparador acotado intenta parchear un defecto
  inexistente (`"No forbidden axiom declaration ... is present"`);
- llevar `ASTRA_TRANSLATOR_TIMEOUT=480` a la configuración de producción
  (hoy corre el traductor con 240 s);
- **pilot comparativo H3** — su adaptador de métricas ya existe
  (`core/campaign_trajectory_metrics.py`); presupuesto pendiente;
- re-verificación viva del flujo de portafolio tras las correcciones
  (1 ciclo, opcional);
- R2 (revisor con autocrítica) y R5 (ancla numérica) del contraste con el
  preprint — H2/H4 diferidas hasta implementarlas;
- campaña adversarial posterior a evidencia en milestones;
- herramientas MCP de producción, UI para campañas, despliegue remoto;
- resultados comparativos que justifiquen promoción.

No describir ASTRA 2.0 como funcional ni validado hasta que estas piezas estén
implementadas y sus compuertas hayan pasado.

## 5. Decisión arquitectónica vigente

No comenzar con un MCTS genérico ni con cientos de ramas. El diseño aprobado
para la primera vertical slice es:

```text
Research brief congelado
        ↓
propuestas Codex + AGY ya existentes
        ↓
portafolio estructurado de 2–4 candidatos
        ↓
una rama activa
        ↓
astra_cycle actual: traducir → revisar → ejecutar → auditar
        ↓
ledger de evidencia + decisión determinista
        ↓
continuar / promover alternativa / suspender / cerrar / pedir revisión humana
```

Las propuestas minoritarias que ASTRA ya paga deben preservarse como ramas. No
añadir una ronda de modelos únicamente para generar más ramas.

Los cinco ejes de estado deben permanecer separados:

1. estado operativo;
2. estado de la afirmación;
3. grado de evidencia;
4. estado de la rama;
5. cobertura del objetivo global.

Una excepción no refuta una afirmación. La inestabilidad numérica no refuta por
sí sola una identidad exacta. El muestreo no prueba una afirmación universal.

## 6. Próximo bloque de implementación autorizado

**El primer corte (capa de dominio y persistencia) está implementado y
verificado el 2026-08-12** — ver §4 y
`docs/evidence/ASTRA2_CAMPAIGN_SLICE_20260812.md`. Cumplió su criterio de
terminación: suite previa intacta, tests nuevos sin modelos/red/ASTRUM,
`astra_cycle` sin cambios, ningún MCP nuevo, producción intacta.

**Las etapas 1, 2 y 3 de §7 fueron autorizadas por Nelson y están
implementadas y verificadas el 2026-08-12** — ver §4 y los tres documentos
`docs/evidence/ASTRA2_STAGE{1,2,3}_*.md`.

**Las etapas 4, 5 y la infraestructura de la 6 están implementadas y
verificadas el 2026-08-12** (ver §4). Lo único pendiente de la etapa 6 es la
ejecución con modelos reales, que consume cuota y requiere el "go" explícito
de Nelson:

```powershell
.\venv\Scripts\python.exe scripts\run_campaign_canary.py --dry-run
.\venv\Scripts\python.exe scripts\run_campaign_canary.py --offline-smoke
.\venv\Scripts\python.exe scripts\run_campaign_canary.py --live --yes
```

Topes congelados del canary vivo: ≤3 ciclos, ≤36 llamadas de modelo, pared
≤60 min, oráculo local, ejecución secuencial. Después del canary operable:
pilot comparativo H3 (`campaign` vs `full-vnext1`/`full-linear`) y gate H1
(suite de calidad), cada uno con su propia decisión de presupuesto. La etapa
7 (UI, MCP de producción, remoto) sigue bloqueada por las compuertas de
`ASTRA2_ACCEPTANCE.md` y la aprobación de promoción de Nelson (G6).

Insumo de diseño para esa decisión:
`docs/architecture/ASTRA2_PREPRINT_2602.03837_CONTRAST.md` contrasta el
preprint de Google (arXiv:2602.03837, "Accelerating Scientific Research with
Gemini") con el diseño congelado: qué valida, qué técnicas se rescatan (R1–R9,
con etapa y coste) y qué se rechaza. Las hipótesis H1–H4 de ese documento son
candidatas a pre-registro en los benchmarks congelados.

Directorio de runtime previsto, siempre ignorado por Git:

```text
workspace/campaigns/<campaign_id>/
  campaign.json
  events.jsonl
  branches/<branch_id>.json
  episodes/<episode_id>.json
  evidence/<evidence_id>/manifest.json
  artifacts/
  checkpoint.json
```

### Criterio de terminación del primer bloque (cumplido el 2026-08-12)

- la suite previa continúa pasando — sí (`218 passed, 6 skipped`);
- pasan todos los tests nuevos sin modelos, red ni ASTRUM — sí (82 + 23 subtests);
- no se modifica la conducta de `astra_cycle` — sí (solo archivos nuevos);
- no se registra un MCP nuevo — sí;
- no se cambia producción — sí;
- este handoff, `ASTRA2_STATUS.json` y la evidencia de la compuerta quedaron
  actualizados en el mismo commit que el código.

El contrato exacto de esta capa está congelado en
`docs/architecture/ASTRA2_IMPLEMENTATION_CONTRACT.md`; la implementación no
introduce una segunda semántica: el store valida sobres y cadena de hashes, la
política valida transiciones y referencias, y los modelos definen los enums y
tablas que ambos comparten.

## 7. Secuencia posterior, todavía no autorizada implícitamente

Después de aceptar la capa anterior:

1. transformar la síntesis del ensemble en un portafolio estructurado;
2. envolver `astra_cycle` como ejecutor de un `Episode`;
3. añadir reglas deterministas de admisibilidad y progressive widening;
4. añadir checkpoint/resume de campaña;
5. exponer interfaces de desarrollo `astra_campaign_*`;
6. ejecutar canary y ablations contra ASTRA actual y `full-linear`;
7. sólo entonces considerar UI, MCP de producción y despliegue remoto.

Cada etapa requiere tests y un commit separado. No avanzar varias etapas en un
único cambio difícil de auditar.

## 8. Archivos clave del ASTRA actual

- `astra_tool.py` — ciclo canónico y acciones de ejecución.
- `core/llm_client.py` — contratos y parseo de respuestas de los agentes.
- `core/architecture_contract.py` — manifiesto/auditoría de roles y controles.
- `core/research_session.py` — Research Loop profundidad-primero existente.
- `core/research_programs.py` — briefs y presupuestos congelados del benchmark.
- `core/research_trajectory_metrics.py` — grafo post-hoc y métricas observables.
- `core/validator_preflight.py` — auditoría/reparación determinista.
- `agents/*.py` — prompts de conjetura, traducción, revisión, análisis y navegación.
- `scripts/run_research_trajectory_benchmarks.py` — runner comparativo congelado.
- `mcp_server/server.py` — MCP vigente; no modificar en la primera vertical slice.
- `scripts/deep_think_mcts.py` — prototipo experimental; no convertir en base de
  2.0 sin una decisión arquitectónica nueva.

La nueva capa debe reutilizar `ResearchProgram` y los artefactos de ciclo cuando
sea posible; no crear una segunda implementación del executor, router, modelos o
benchmarks.

## 9. Límites de seguridad y Git

- No trabajar en `C:\Users\Nelson\Dev\ASTRA` para tareas de ASTRA 2.0.
- El checkout de producción contiene cambios locales ajenos al clon. No hacer
  reset, limpieza ni copia masiva desde allí.
- En particular, producción contiene un test end-to-end todavía no committeado;
  revisarlo y portarlo deliberadamente más adelante, no copiar todo el árbol.
- No habilitar push ni cambiar remotos sin autorización explícita de Nelson.
- No registrar este clon en el MCP o en los launchers de uso diario.
- No ejecutar `install.ps1`, `install_macos.sh` ni
  `scripts/configure_antigravity_mcp.py` desde este clon: pueden registrar o
  reemplazar rutas de uso diario.
- No copiar secretos ni imprimirlos en logs.
- Conservar los archivos y cambios no relacionados que encuentre otro agente.
- Usar `apply_patch` para ediciones manuales.

Los commits locales en `astra-2.0` están permitidos cuando forman una unidad
coherente, los tests correspondientes pasan y el handoff queda actualizado.

### Comandos locales seguros

```powershell
Set-Location -LiteralPath 'C:\Users\Nelson\Dev\ASTRA-2.0'
git status --short --branch
.\venv\Scripts\python.exe --version
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe scripts\audit_architecture.py
.\venv\Scripts\python.exe scripts\run_research_trajectory_benchmarks.py --dry-run
```

No quitar `--dry-run`, ejecutar ciclos MCP, lanzar benchmarks de modelos, usar
`--oracle both` ni contactar ASTRUM sin que la tarea actual lo autorice: esas
acciones pueden consumir cuota o modificar estado remoto.

Los artefactos ignorados existentes bajo `workspace/` no son campañas ASTRA
2.0 válidas. `REMOTE_ORACLE_HANDOFF.md` es documentación histórica de
producción y no reemplaza este handoff.

## 10. Definición de éxito de ASTRA 2.0

ASTRA 2.0 no necesita superar a sistemas frontier en todo. Bajo presupuestos
comparables debe conservar la validez científica y mostrar al menos una mejora
pre-registrada en rendimiento de evidencia, recuperación tras evidencia
negativa, calidad ciega de trayectoria o costo de progreso parcial útil.

Si sólo produce más ramas, más texto o más ciclos sin evidencia más fuerte, la
arquitectura falla y no debe reemplazar al ASTRA actual.

## 11. Concurrencia del MCP de desarrollo (2026-08-21)

Motivación: Nelson reportó que ASTRA 2.0 no se podía usar desde más de un chat
a la vez — una llamada larga (p. ej. `astra_campaign_step`) congelaba el
servidor MCP entero, incluidas llamadas triviales de otra conversación en la
misma conexión.

Causa raíz confirmada leyendo el SDK: el bucle de despliegue de FastMCP
(`mcp/server/lowlevel/server.py`) ya despacha cada mensaje entrante en su
propia tarea de `anyio`, pero `func_metadata.py` invocaba una tool `def`
síncrona directamente sobre el único hilo del event loop
(`else: return fn(**arguments_parsed_dict)`), sin offload. Una tool síncrona
lenta bloqueaba el loop entero, no sólo su propia llamada.

Cambios (`mcp_server/server.py`, sólo este checkout de desarrollo):

- Las 19 tools que hacen trabajo bloqueante (`astra_execute`,
  `astra_client_validate`, `astra_cycle`, `astra_cycle_submit`,
  `astra_submit`, `astra_job`, `astra_capacity`, `astra_cluster_*`,
  `astra_status`, `astra_engines`, y las seis `astra_campaign_*`) pasaron de
  `def` a `async def`, envolviendo su llamada bloqueante en
  `await asyncio.to_thread(...)`. `astra_probe` se dejó deliberadamente
  síncrona (sólo lee heartbeat local, costo cero) — ver el test que lo guarda.
- Nueva tool `astra_campaign_step_submit` + runner
  `astra_campaign_step_job_runner.py`, que reutiliza sin cambios el esquema de
  `workspace/jobs/<job_id>/job.json` y la tool `astra_job` ya existentes
  (mismo patrón que `astra_cycle_submit`/`astra_job`). No se tocó
  `astra_tool.py`.
- `tests/test_mcp_server_concurrency.py` (nuevo): prueba que dos llamadas
  lentas se solapan en vez de serializarse, que `astra_probe` sigue síncrona a
  propósito, y que `astra_campaign_step_submit` escribe un job encuestable y
  lanza el runner correcto.

Verificación: `pytest -q` completo → `505 passed, 7 skipped, 100 subtests
passed`; `scripts\audit_architecture.py` → `required_failures: []`.

Nota sobre §8: esa lista describe `mcp_server/server.py` como "MCP vigente; no
modificar en la primera vertical slice" — una compuerta de la fase inicial de
bootstrap del motor de campañas (ago-12), ya superada por el propio desarrollo
posterior (las tools `astra_campaign_*` que ese slice añadió ya viven en este
archivo). Este cambio fue pedido explícitamente por Nelson y es ortogonal al
motor de campañas: no cambia contratos, esquemas ni la política determinista,
sólo cómo el servidor MCP despacha llamadas bloqueantes.

Empujado el 2026-08-21 (autorizado explícitamente por Nelson, incluyendo el
remoto compartido `company`): rama `astra-2.0` en `company`
(`AstrumDrive/ASTRA`) y `production` (`xys004/ASTRA_Production`) en
`cc549ae`. Los `pushurl` de ambos remotos se reactivaron sólo para ese push y
se devolvieron de inmediato a `DISABLED_UNTIL_ASTRA2_ACCEPTANCE`: la
autorización cubrió este push puntual, no un desbloqueo permanente. Cualquier
push futuro necesita reactivar el `pushurl` de nuevo con autorización
explícita.

## 12. `astra_campaign_start`/`list` colgados 1800 s — subprocess de git (2026-08-22)

Síntoma reportado: `astra_campaign_start` (parámetros mínimos, sin
`initial_portfolio`) se colgó los 1800 s completos del timeout del cliente MCP,
y acto seguido `astra_campaign_list` — de solo lectura — se colgó igual, sin
error ni resultado. NO es el freeze de concurrencia de §11: ese evitaba que UNA
llamada larga congelara a OTRAS; aquí cada llamada se cuelga sola.

Causa raíz: `core/campaign_api.py::_resolve_source_commit` shelleaba
`git rev-parse HEAD` en la ruta caliente de **toda** llamada de campaña, antes
de tocar disco. `astra_campaign_start` pasa por ahí vía `_open_store`;
`astra_campaign_list` también, porque enumera el `cmp_...` existente y llama a
`astra_campaign_status` → `_open_store` → `_resolve_source_commit`. Ese
subprocess puede quedar wedgeado indefinidamente en este entorno Windows: se
encontró **en vivo** un `git rev-parse HEAD` huérfano atascado 30+ minutos
(PID 29800, padre ya muerto, sin hijos), pese al `timeout=10` del código — el
`timeout` de `subprocess.run` no siempre reapea al hijo en Windows cuando hay
handles heredados de por medio. Un subprocess colgado dentro de
`asyncio.to_thread` = tool que nunca responde = el cuelgue de 1800 s.

Fix (`core/campaign_api.py`): se eliminó el subprocess de la ruta caliente. Un
lector en Python puro (`_read_head_commit` + `_git_dir`) resuelve el commit de
HEAD leyendo directamente los ref files de git (`HEAD` → ref suelto →
`packed-refs`; maneja HEAD desprendido, `.git` como archivo de worktree y
`commondir`). Es I/O local puro: no lanza procesos, no hereda handles del
transporte stdio, no puede colgarse. `_resolve_source_commit` ahora hace:
explícito → env `ASTRA_SOURCE_COMMIT` → lectura directa → (último recurso, sólo
para layouts exóticos que la lectura no cubra) un subprocess de git blindado
(`stdin=DEVNULL`, `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=never`,
`timeout=5`) → error. En un checkout normal la lectura directa siempre gana, así
que el subprocess jamás se alcanza.

Verificado: el lector directo devuelve el MISMO commit que `git rev-parse HEAD`
en 1.3 ms; roundtrip real `start`+`list` en 18 ms + 2 ms con **cero** llamadas
a subprocess (probado con un espía). `tests/test_campaign_api_no_git_subprocess.py`
(nuevo, 10 tests) fija: lectura correcta contra el repo real, ref suelto,
`packed-refs`, HEAD desprendido, forma `.git`-archivo de worktree, ausencia de
`.git`, precedencia de `_resolve_source_commit`, y —la regresión central— que
`start`+`list` no lanzan ningún git. `pytest -q` completo → `515 passed, 7
skipped, 100 subtests`; `audit_architecture.py` → `required_failures: []`.

Higiene de procesos: se terminó el `git rev-parse HEAD` huérfano wedgeado
(PID 29800). Sobre los procesos "duplicados" que notó el reporte: cada arranque
del server MCP crea un par por diseño — el intérprete `venv` re-ejecuta un hijo
bajo el Python312 del sistema (que tiene el SDK 3.12); NO son dos servidores
compitiendo. Lo que sí hay es acumulación de pares huérfanos de sesiones
anteriores (varias generaciones con distinto shell padre), inofensivos pero
sucios: se limpian reiniciando el cliente MCP. Nota importante: los servidores
en marcha siguen ejecutando el `campaign_api` viejo hasta que el cliente MCP
reconecte; para USAR este fix hay que reiniciar/reconectar `astra_dev`.

Otros `git rev-parse HEAD` con el mismo patrón frágil vivían fuera de la ruta de
campañas. Blindados en el mismo barrido (2026-08-22): la lógica se centralizó en
un módulo compartido `core/git_head.py` (`read_head_commit`/`git_dir` +
`resolve_head_commit`, con un subprocess de último recurso blindado idéntico) y
ahora los TRES consumidores locales lo usan:

- `core/campaign_api.py::_resolve_source_commit` (antes tenía su copia; ahora
  delega — se eliminó la duplicación introducida el 22-ago);
- `core/client_validation.py::_git_commit` (ruta de `astra_client_validate`);
- `core/external_benchmarks.py::_git_commit` (auditoría de fuentes).

Se quitó `import subprocess` de esos tres (ya sin uso local). Cobertura nueva:
`tests/test_git_head_callers.py` prueba que los dos consumidores adicionales
resuelven HEAD por lectura de archivos sin lanzar git y conservan su centinela
(`""` / `"unknown"`) cuando no hay `.git`.

Los `git rev-parse HEAD` restantes en `core/external_evaluators.py:521` y
`core/formal_validators.py:250` NO son un riesgo local: viven dentro de strings
de script (`inspector = r'''…'''` y `remote_code = f"""…"""`) que se
base64-codifican y se ejecutan en un **proceso/contenedor remoto** (udocker /
Lean remoto), no en el proceso del server MCP, así que no pueden heredar el
transporte stdio ni colgar el servidor. Se dejan como están.

Verificación del barrido: `pytest -q` → `519 passed, 7 skipped, 100 subtests`;
`audit_architecture.py` → `required_failures: []`.

Commits del fix + barrido: `934a8ff` (fix del hot path) y `2da8005`
(consolidación en `git_head.py` + blindaje de los otros dos). Empujados a
`company` y `production` el 2026-08-22 (autorización explícita de Nelson;
`pushurl` reactivados sólo para el push y devueltos a
`DISABLED_UNTIL_ASTRA2_ACCEPTANCE` acto seguido).

Verificación EN VIVO contra el server MCP real (2026-08-22): como no hay
hot-reload de Python, se reinició `astra_dev` matando sus procesos (el par
actual + dos pares huérfanos de sesiones previas) para forzar al cliente a
relanzarlo; el cliente levantó un único par limpio (`42136`→`35552`) con el
código nuevo. Con ese server se ejecutó el repro exacto del reporte:
`astra_campaign_start` (parámetros mínimos, sin `initial_portfolio`) **devolvió
al instante** (antes: 1800 s) creando `cmp_5539745bf8414e86` HEALTHY/ACTIVE, y
`astra_campaign_list` **devolvió al instante** resolviendo el HEAD de ambas
campañas por lectura de archivos. La campaña de prueba se canceló. El cuelgue
queda cerrado y confirmado end-to-end, no sólo en tests.
