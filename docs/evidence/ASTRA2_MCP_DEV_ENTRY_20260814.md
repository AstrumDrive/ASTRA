# ASTRA 2.0 — entrada MCP `astra_dev` en los tres clientes (2026-08-14)

Autorización: Nelson pidió explícitamente exponer la línea 2.0 por MCP en
Codex, Claude Code y Antigravity, "para llamar a astra2 o astra desde algún
agente", con producción como comportamiento por defecto.

## La precaución que había que resolver

`HANDOFF.md` §9 y `AGENTS.md` prohíben registrar este clon en el MCP y correr
los instaladores desde aquí. La razón es concreta:
`scripts/configure_antigravity_mcp.py` escribe la clave **`astra`** — la misma
que producción — así que en modo global **sobrescribiría** la ruta de uso
diario. Los tres clientes tenían esa clave apuntando a `Dev\ASTRA`.

La prohibición protege contra romper producción, no contra que ambas líneas
coexistan. Por eso no se usó ningún instalador: se añadió una entrada
**separada y con nombre propio**.

## Por qué `astra_dev` y no `astra2`

"astra2" sugiere un sucesor liberado, y no lo es: la promoción sigue bloqueada
en G6. `astra_dev` dice lo que es cada vez que se lee, y cuando G6 apruebe,
**esta línea se convierte en `astra`** y la entrada de desarrollo desaparece —
en vez de dejar un número de versión heredado que ya no significa nada. El
guion bajo además evita el entrecomillado que un guion exigiría en el TOML de
Codex.

El servidor también se identifica como `astra_dev` en su `serverInfo`
(antes decía `astra`, igual que producción: un cliente listando dos servidores
con el mismo nombre no permite saber cuál respondió). Se deriva del nombre del
checkout y `ASTRA_MCP_SERVER_NAME` lo sobrescribe, precisamente para la
promoción.

## Qué se escribió

`scripts/register_dev_mcp.py`, dry-run por defecto, con copia de seguridad de
cada fichero, idempotente y con `--remove` para revertir:

| Cliente | Fichero |
|---|---|
| Codex | `~/.codex/config.toml` |
| Claude Code | `~/.claude.json` |
| Antigravity | `~/.gemini/config/mcp_config.json` |

La salvaguarda principal es programática: el script calcula la huella de la
entrada `astra` **antes y después**, y si cambiara, se niega a escribir — y si
ya hubiera escrito, restaura la copia. En Codex replica además los diez
bloques de aprobación por herramienta, para que la línea de desarrollo no
herede una política de aprobación distinta por omisión.

Verificado tras aplicar: las tres entradas `astra` siguen apuntando a
`Dev\ASTRA`, las tres `astra_dev` a `Dev\ASTRA-2.0`, ninguna referencia
`astra2` residual, paridad de aprobaciones (10 herramientas), y un **handshake
MCP real por stdio** que devuelve `serverInfo: astra_dev` y las 14
herramientas.

## Comportamiento para el operador

- **`astra` sigue siendo el default de hecho**: las herramientas van
  namespaceadas por servidor (`mcp__astra__astra_cycle` frente a
  `mcp__astra_dev__astra_cycle`), así que el trabajo existente llama a
  producción exactamente igual que antes.
- La línea 2.0 solo se alcanza nombrándola.
- `astra_dev` carga el `.env` de 2.0 con independencia del directorio de
  trabajo del cliente: `core/llm_client.py` lo resuelve desde `__file__`, no
  desde el cwd. Es decir, llega con el mapa de roles de producción, las rutas
  de motores, `ASTRA_TRANSLATOR_TIMEOUT=480` y su `ASTRA_CLIENT_ID` propio.
- Las herramientas `astra_campaign_*` **no** están expuestas: el servidor MCP
  de 2.0 no las registra, conforme a la etapa 5. Exponerlas sería una decisión
  aparte.

Revertir: `python scripts/register_dev_mcp.py --remove --apply`.

## Hallazgo lateral: la suite no era hermética

Al terminar, seis tests fallaron con `BUSY`. No era un defecto del cambio: el
candado de ciclo de máquina —adoptado ayer— estaba en manos de **tu ASTRA de
producción**, corriendo un ciclo real. El candado hizo exactamente su trabajo.

Pero dejó a la vista que la suite dependía de un recurso de máquina: seis
tests parchean el cliente de modelos y no llaman a ninguno, y aun así pedían
el slot. `tests/conftest.py` apunta ahora `ASTRA_LOCK_ROOT` a un directorio
temporal por sesión. La semántica real del candado se sigue probando en
`test_cycle_lock_root.py`, que fija sus propias raíces.

Suite completa tras el cambio: **356 passed, 7 skipped, 66 subtests**.
