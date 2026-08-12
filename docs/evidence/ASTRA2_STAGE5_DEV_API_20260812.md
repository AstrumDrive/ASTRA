# ASTRA 2.0 — evidencia de la etapa 5: interfaces de desarrollo astra_campaign_*

Fecha: 2026-08-12

Autorización: Nelson autorizó las etapas restantes una a una.

Base: commit `26566d9`; el código entra en el mismo commit que este documento.

## Alcance implementado

`core/campaign_api.py` (nuevo): los verbos de desarrollo previstos por la
revisión de arquitectura, como funciones planas sobre un directorio raíz de
campañas (default `workspace/campaigns`, ignorado por Git):

- `astra_campaign_start` — crea la campaña (DRAFT→ACTIVE opcional), siembra
  ramas desde un portafolio inicial (claims + PROPOSED + gates →
  ADMISSIBLE/REJECTED) y selecciona la primera rama activa;
- `astra_campaign_status` — informe de resume estrictamente de solo lectura
  (sin lock de escritor);
- `astra_campaign_step` — un paso episodio→decisión→ledger, con
  auto-selección de rama inicial cuando procede; `cycle_runner` inyectable
  (el `_do_cycle` real solo por defecto);
- `astra_campaign_stop` — `pause` (reanudable) o `cancel` (terminal);
- `astra_campaign_reactivate` — PAUSED→ACTIVE tras revisión humana;
- `astra_campaign_list` — enumeración read-only tolerante a daños.

Garantías clave:

- **No MCP**: el módulo jamás importa `mcp_server`; un test de regresión fija
  además que `mcp_server/server.py` no contiene ninguna referencia
  `astra_campaign` — el registro en producción sigue prohibido hasta la
  aceptación (`ASTRA2_ACCEPTANCE.md`).
- **Lock liberado por llamada**: cada función abre su store y lo cierra en
  `finally`; probado que `writer.lock` no queda huérfano entre llamadas.
- Entradas JSON-safe validadas fail-closed (presupuesto de seis dimensiones
  exacto, clases de evidencia del enum, portafolio convertible).

Tests: `tests/test_campaign_api.py` (7 tests): ciclo de vida completo
(start→status→step→pause→step-rechazado→reactivate→cancel→terminal),
arranque sin portafolio, entradas inválidas, enumeración, liberación de lock
y la garantía anti-MCP.

## Comandos y resultados

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_campaign_api.py -q
# 7 passed in 0.86s

.\venv\Scripts\python.exe -m pytest -q
# 294 passed, 6 skipped, 28 subtests passed in 15.07s
```

Entorno sin cambios: fingerprint `pip freeze` SHA-256
`59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5`.
