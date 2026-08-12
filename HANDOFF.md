# ASTRA 2.0 — handoff de desarrollo

Actualizado: 2026-08-12

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
- prototipo MCTS experimental separado de producción.

### Todavía no existe

- controlador de campañas de ASTRA 2.0;
- ramas como objetos científicos completos con evidencia y decisiones propias;
- ledger append-only de campaña;
- progressive widening y política determinista de promoción/suspensión;
- campaña adversarial posterior a evidencia en milestones;
- herramientas MCP `astra_campaign_*`;
- UI para campañas;
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

El siguiente agente debe implementar solamente la capa de dominio y
persistencia, sin conectarla todavía al runtime de producción:

1. `core/campaign_models.py`
   - `Campaign`, `Branch`, `Episode`, `Claim`, `Evidence`, `Decision`;
   - enums cerrados para estados y tipos de afirmación;
   - validación de ids, timestamps, presupuestos, transiciones y referencias;
   - serialización JSON estable y versionada.
2. `core/campaign_store.py`
   - `events.jsonl` append-only;
   - checkpoints mediante escritura temporal + `os.replace`;
   - recuperación segura tras una última línea truncada;
   - ningún escritor concurrente en la primera versión.
3. `core/campaign_policy.py`
   - hard gates científicos y de presupuesto;
   - transiciones fail-closed;
   - una sola rama activa;
   - sin selección aprendida ni llamadas de modelos.
4. Tests nuevos:
   - round-trip de todos los records;
   - rechazo de estados/transiciones inválidos;
   - inmutabilidad de eventos anteriores;
   - recuperación de log truncado;
   - checkpoint atómico;
   - aislamiento entre campañas.

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

### Criterio de terminación de este bloque

- la suite previa continúa pasando;
- pasan todos los tests nuevos sin modelos, red ni ASTRUM;
- no se modifica la conducta de `astra_cycle`;
- no se registra un MCP nuevo;
- no se cambia producción;
- se actualizan este handoff, `ASTRA2_STATUS.json` y la evidencia de la compuerta.

El contrato exacto de esta capa está congelado en
`docs/architecture/ASTRA2_IMPLEMENTATION_CONTRACT.md`; no inventar una segunda
semántica dentro del código.

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
