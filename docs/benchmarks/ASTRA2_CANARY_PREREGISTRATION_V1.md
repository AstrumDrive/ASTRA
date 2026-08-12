# ASTRA 2.0 — pre-registro del canary de campaña (v1)

Fecha de congelación: 2026-08-12

Este documento se congela ANTES de cualquier ejecución con modelos. Su huella
SHA-256 vive en `ASTRA2_CANARY_PREREGISTRATION_V1.sha256`;
`scripts/run_campaign_canary.py` la verifica y se niega a correr si el
protocolo cambió. Cualquier modificación exige re-congelar explícitamente y
documentar el porqué.

## 1. Pregunta y endpoint primario

**Pregunta del canary**: ¿puede el lazo de campaña de ASTRA 2.0 (etapas 1–5)
completar episodios reales de investigación — síntesis con portafolio,
validador, oráculo, evidencia, decisión determinista — de forma operable y
auditable?

**Endpoint primario (operabilidad, no superioridad)**: el canary PASA si

1. completa ≥ 1 episodio con evidencia transcrita al ledger (claim testeado,
   outcome, artefactos hasheados);
2. el ledger reproduce limpio (`replay` sin errores) y el checkpoint valida;
3. cada episodio termina con una `Decision` determinista registrada;
4. ningún gasto supera los topes de presupuesto declarados abajo.

Un canary exitoso demuestra operabilidad, **no** mejora científica
comparativa (regla del `ASTRA2_ACCEPTANCE.md` G4). El canary FALLA si el lazo
se detiene por un error del propio controlador/ledger; queda INCONCLUSIVE si
se detiene por fallos operativos de proveedores (cuota/red).

## 2. Configuración congelada del canary

- Caso: `gr_invariant_audit` (brief congelado del pilot v1; el fingerprint
  del protocolo de trayectoria `ef119a1e27e51481483ef1166792bec9442a3147c2e5f5436e3918eb2e079054`
  no cambia).
- Semilla: 11. Oráculo: `local` (Python/SymPy; sin ASTRUM).
- Topes por defecto del runner (ver `build_plan` en el script):
  - ciclos: min(presupuesto del programa, 3);
  - model_calls: 12 × ciclos;
  - pared: min(presupuesto del programa, 60 min);
  - ejecución: timeout del programa × ciclos;
  - intervenciones humanas: 1; trabajos remotos: 0.
- Bootstrap determinista: la campaña arranca con UNA rama semilla
  (`method_family = brief_bootstrap`) cuyo claim declara que la primera
  dirección congelada del brief produce una proposición atómica falsable
  testable por un validador compacto. Los claims científicos reales llegan
  con el portafolio de la primera síntesis (etapa 1) y se registran/deduplican
  por fingerprint (etapa 2).
- Criterios de aborto: `budget_exhausted` en el informe de episodio; pared
  agotada; `next_action` ≠ `campaign_step`; o tope de episodios del runner.

## 3. Hipótesis pre-registradas (medición posterior al canary)

| Hipótesis | Estado | Medición congelada |
|---|---|---|
| H1: prompting neutro no aumenta (idealmente reduce) la aceptación falsa | activa | suite de calidad (`run_quality_benchmarks.py`), métrica de aceptación falsa como veto; referencia: snapshot de producción 2026-07-26. Soporte = sin regresión; refutación = aumento. |
| H2: revisor con autocrítica iterativa | **diferida** | R2 no está implementada; pre-registrar al implementarla (gate: `benchmark_validator_repair.py` + casos de regresión de auditoría, sin aumento de bloqueo falso) |
| H3: el lazo de campaña (portafolio + widening R1–R7) mejora preservación de ramas, diversidad de familias y recuperación tras evidencia negativa a presupuesto igualado | activa | pilot comparativo posterior al canary: configuración `campaign` vs `full-vnext1` y `full-linear` sobre los mismos casos/semillas congelados; métricas automáticas de `RESEARCH_TRAJECTORY_BENCHMARK.md` (branch preservation, recovery rate, non-repetition) + expertos ciegos G4. Nunca colapsadas en un solo número. |
| H4: ancla numérica congelada por campaña | **diferida** | R5 no está implementada; pre-registrar al implementarla |

Regla de interpretación: los resultados del canary no cuentan como evidencia
de H1–H4; solo habilitan (o no) el pilot comparativo. La separación
operativo/científico de los cinco ejes se mantiene en todos los informes.

## 4. Disciplina de ejecución

- `scripts/run_campaign_canary.py` es **dry-run por defecto**; `--offline-smoke`
  ejecuta el lazo completo con un runner enlatado (cero modelos) como
  diagnóstico de release; `--live` exige `--yes` explícito y verifica esta
  huella antes de gastar cuota.
- Los ciclos de modelo corren secuenciales (sin confundir cuota con
  arquitectura, regla del benchmark de trayectoria).
- Los resultados viven bajo `workspace/campaign_canary_runs/<run>/`
  (ignorado por Git); las cifras que entren a cualquier documento salen de
  esos logs depositados, nunca de resúmenes de prosa
  (`feedback_cifras_solo_desde_outputs`).
- Auditorías internas no se citan en manuscritos (`PUBLICATION_POLICY.md`).
