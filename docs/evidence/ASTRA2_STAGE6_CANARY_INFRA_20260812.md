# ASTRA 2.0 — evidencia de la etapa 6 (infraestructura): canary pre-registrado

Fecha: 2026-08-12

Autorización: Nelson autorizó las etapas restantes una a una. La ejecución
VIVA del canary (consumo real de cuota CLI) queda pendiente de su "go"
explícito con el presupuesto a la vista; esta etapa entrega toda la
infraestructura y el protocolo congelado.

Base: commit `763ad9b`; el código entra en el mismo commit que este documento.

## Alcance implementado

- **Pre-registro congelado**:
  `docs/benchmarks/ASTRA2_CANARY_PREREGISTRATION_V1.md`, con huella SHA-256
  `9a25c214a5d2b38d1e8f615518ce9d2f46213b08ae193c1cd1ad7792c321bd92`
  depositada en `ASTRA2_CANARY_PREREGISTRATION_V1.sha256`. Contenido:
  endpoint primario de operabilidad (un canary exitoso NO es mejora
  científica), configuración congelada (caso `gr_invariant_audit`, semilla
  11, oráculo local, topes de presupuesto), semántica del bootstrap
  determinista, criterios de aborto, y las hipótesis H1 (activa, gate de
  no-regresión en aceptación falsa), H3 (activa, pilot comparativo
  `campaign` vs `full-vnext1`/`full-linear` con métricas de trayectoria) y
  H2/H4 explícitamente **diferidas** porque R2/R5 no están implementadas.
- **Runner** `scripts/run_campaign_canary.py`:
  - `--dry-run` (modo por defecto): imprime el plan congelado, no escribe
    nada, no toca modelos;
  - `--offline-smoke`: corre el lazo COMPLETO de campaña con un runner
    enlatado (cero modelos) — diagnóstico de release que ejercita
    start → episodios → portafolio → promoción → decisiones → checkpoint y
    deposita el resumen JSON bajo el directorio de salida;
  - `--live`: exige `--yes` explícito Y que la huella del pre-registro
    coincida; si el protocolo cambió, se niega a arrancar.
- **Endurecimiento del ejecutor** (hallado por el smoke): las alternativas de
  portafolios repetidos ya no acumulan ramas duplicadas — una alternativa
  cuyo (familia de método, fingerprint de claim) ya está rastreado por una
  rama existente se omite con nota en el informe.
- Tests: `tests/test_campaign_canary_runner.py` (5 tests): huella congelada,
  topes del plan, dry-run sin efectos, `--live` sin `--yes` rechaza sin
  gastar, y el smoke completo con replay limpio, checkpoint válido y
  deduplicación de ramas verificada.

## Comandos y resultados

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_campaign_canary_runner.py -q
# 5 passed in 0.59s

.\venv\Scripts\python.exe -m pytest -q
# 299 passed, 6 skipped, 28 subtests passed in 15.96s

.\venv\Scripts\python.exe scripts\audit_architecture.py
# "status": "PASS"

.\venv\Scripts\python.exe scripts\run_research_trajectory_benchmarks.py --dry-run
# fingerprint=ef119a1e27e51481483ef1166792bec9442a3147c2e5f5436e3918eb2e079054

.\venv\Scripts\python.exe scripts\run_campaign_canary.py --dry-run
# preregistration_fingerprint=9a25c214a5d2b38d1e8f615518ce9d2f46213b08ae193c1cd1ad7792c321bd92
```

## Qué falta de la etapa 6 (requiere "go" explícito de Nelson)

1. **Canary vivo**: `run_campaign_canary.py --live --yes` — ≤3 ciclos,
   ≤36 llamadas de modelo, pared ≤60 min, oráculo local, secuencial.
   Consume cuota de las CLIs y tiempo de la máquina de trabajo.
2. **Pilot comparativo (H3)**: tras un canary operable, correr la
   configuración `campaign` contra `full-vnext1` y `full-linear` sobre los
   casos congelados — decisión de presupuesto aparte (horas de pared).
3. **Gate H1**: suite de calidad a tier release contra el snapshot de
   producción — también consume cuota.

Ningún resultado de esta etapa constituye evidencia científica.
