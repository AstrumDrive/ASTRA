# ASTRA 2.0 — separación de producción y camino a pre-producción

Fecha: 2026-08-13

Dirección fijada por Nelson: *"toda la estructura ASTRA 2 separada de ASTRA,
con nuevos backends independientes de producción pero las mismas
credenciales… y vemos cuándo podemos hacer las primeras pruebas en
pre-producción"*.

Este documento inventaría qué está realmente separado hoy, señala el
acoplamiento que **no** se resuelve con checkouts distintos, y propone el
camino a pre-producción anclado a `ASTRA2_ACCEPTANCE.md`. No adopta nada.

## 1. Qué ya está separado (verificado)

| Recurso | Estado |
|---|---|
| Checkout y rama | `Dev/ASTRA-2.0`, rama `astra-2.0` |
| Entorno Python | `venv` propio, fingerprint registrado |
| Workspace de runtime | `<checkout>/workspace/**`, ignorado por Git |
| Candado de ciclo | `<checkout>/workspace/locks` — **por checkout** |
| Campañas 2.0 | `workspace/campaigns/<id>/`, formato propio |
| Registro MCP, accesos directos, servicio | intactos, apuntan a producción |
| Push a remotos | desactivado |

## 2. El acoplamiento que queda, y no lo arregla la separación de ficheros

**Las credenciales son las mismas por decisión de diseño**, y de ahí se
derivan dos recursos compartidos que ningún checkout separado divide:

1. **La cuota de las suscripciones** (Codex, Claude, Antigravity). Cada ciclo
   de 2.0 consume la misma cuota que usaría producción.
2. **La exclusión mutua entre ciclos.** `acquire_cycle_slot` crea el candado
   bajo `Path(root)/workspace/locks`, es decir **relativo al checkout**. Dos
   líneas con checkouts distintos tienen candados distintos: **pueden
   deliberar simultáneamente contra la misma cuenta**, que es precisamente lo
   que el candado existe para evitar. Su docstring dice "across MCP
   processes"; el supuesto implícito era un único checkout.

Consecuencia práctica y medible: durante esta sesión, correr la suite de
tests mientras corría un benchmark produjo `BUSY` **dentro del mismo
checkout** (el candado funcionó). Entre 2.0 y producción no habría habido
`BUSY`: habría habido dos deliberaciones compitiendo por la misma cuenta, con
fallos de cuota que se presentan como error operativo y contaminan cualquier
medición.

Opciones, **ninguna adoptada**:

- **(a) Candado de máquina**: raíz de candados configurable
  (`ASTRA_LOCK_ROOT`, por defecto algo como `%LOCALAPPDATA%\astra\locks`)
  compartida por ambas líneas. Preserva el invariante real —una deliberación
  por cuenta— sin unir nada más. Cambio pequeño y testeable.
- **(b) Cuentas separadas** para la línea 2.0. Contradice "las mismas
  credenciales" y multiplica coste.
- **(c) Disciplina manual**: no correr 2.0 mientras se usa producción.
  Gratis, frágil, y ya sabemos que las mediciones largas duran horas.

### Decidido y adoptado (2026-08-13): opción (a)

Nelson eligió el candado compartido ("no queremos contaminación").
`cycle_lock_root()` calcula ahora una raíz **de máquina** por defecto
(`%LOCALAPPDATA%\astra\locks` en Windows, `~/.cache/astra/locks` fuera),
con `ASTRA_LOCK_ROOT` para forzar otra — que es además la forma correcta de
aislar a propósito una línea que corra con **credenciales distintas**. Si la
raíz de máquina no es escribible, cae a la ubicación histórica por checkout
en vez de quedarse sin candado.

Aplicado en **ambas líneas** (en producción sin committear) y verificado
cruzando los dos checkouts reales:

```text
production lock root : C:\Users\Nelson\AppData\Local\astra\locks
2.0 line lock root   : C:\Users\Nelson\AppData\Local\astra\locks
production acquired  : True  | holders seen: 0
2.0 acquired         : False | holders seen: 1   <- bloqueado, como debe
2.0 tras release     : True  | holders: 0
```

Nota operativa: **el MCP de producción, si está corriendo, tiene el código
viejo en memoria**; hasta reiniciarlo seguirá usando su candado por checkout.

Tests: `tests/test_cycle_lock_root.py` (6), incluido el de dos checkouts
contendiendo por un mismo slot y el de degradación ante raíz no escribible.

## 3. "Backends independientes": qué significaría en concreto

Hoy ambas líneas comparten **linaje de código**, no runtime: `cli_backend.py`
es un fichero por checkout. El coste de eso se vio hoy dos veces — el arreglo
Unicode tuvo que portarse hacia producción y el de `ASTRA_CODEX_BIN` hacia
2.0. Alternativas:

- **Divergencia deliberada**: 2.0 evoluciona su backend libremente y se
  aceptan los ports manuales como precio. Es el estado actual.
- **Backend versionado**: extraer el contrato de invocación de CLIs a un
  módulo con versión propia, que ambas líneas consuman. Elimina los ports,
  pero crea una dependencia común — justo lo que la aceptación quería evitar
  antes de la promoción.

Mientras la aceptación siga bloqueada, la divergencia deliberada es lo
coherente; el backend compartido tiene sentido **después** de G6, como parte
de la promoción y no antes.

### Adoptado (2026-08-13): chequeo de deriva, no fusión de código

El problema real no era arquitectónico sino de **visibilidad**: los dos ports
de hoy se descubrieron por accidente. `scripts/check_line_drift.py` compara
cada fichero de la superficie de runtime compartida en tres puntos —el commit
base del clon, el árbol de 2.0 y el de producción— y clasifica:

- `PRODUCTION ONLY`: producción avanzó y 2.0 no. **Es la clase de cambio que
  un port se pierde**, exactamente como pasó con `ASTRA_CODEX_BIN`.
- `BOTH CHANGED`: divergencia real, decisión humana.
- `2.0 ONLY`: evolución esperada de la línea de desarrollo.
- `PROSE ONLY`: mismo comportamiento, distinta redacción.

La última categoría importa: compara el **AST con docstrings eliminados**, así
que una redacción distinta tras un port no se reporta como deriva. Sin eso, el
primer informe marcaba `cli_backend.py` y `runtime_resources.py` como
divergentes cuando su código es idéntico — y un informe con ruido se deja de
leer, que es justo cómo se pierde el siguiente arreglo de verdad.

Primera ejecución (2026-08-13), 41 ficheros comparados:

```text
PRODUCTION ONLY    2   core/pdf_generator.py, main.py
BOTH CHANGED       0
2.0 ONLY           7
PROSE ONLY         2   core/cli_backend.py, core/runtime_resources.py
IN SYNC           30
```

Encontró en su primera pasada dos cambios de producción ausentes en 2.0:
`generate_pdf_report(...)` pasa ahora `code` y `execution_result` para
enriquecer el informe PDF. No es crítico para el lazo de campaña, pero ya no
depende de que alguien se acuerde.

Uso: `python scripts/check_line_drift.py --production <ruta>` (o
`ASTRA_PRODUCTION_ROOT`). Sin cuota, sin escrituras.

## 4. Camino a pre-producción

"Pre-producción" aquí = ejecutar el lazo de campaña 2.0 con modelos reales,
de forma repetida y observable, **sin** que nada de producción apunte a este
checkout. Estado contra `ASTRA2_ACCEPTANCE.md`:

| Compuerta | Estado | Qué falta |
|---|---|---|
| G0 aislamiento | PASS | — |
| G1 regresión | PARTIAL | portar/committear el test end-to-end que vive suelto en producción |
| G2 motores y oráculos | PENDIENTE | Lean local y ruta remota sin configurar; sin smoke por motor |
| G3 calidad científica | PARCIAL | aceptación falsa 0.0 medida dos veces; faltan suite cliente y subconjunto externo |
| G4 trayectoria | PENDIENTE | canary de campaña operable hecho; falta el pilot comparativo H3 |
| G5 portabilidad | PENDIENTE | instalación limpia, macOS, secretos |
| G6 promoción | BLOQUEADA | decisión de Nelson |

Secuencia mínima propuesta para "primeras pruebas en pre-producción",
en orden de dependencia y coste:

1. **Candado compartido (a)** — sin cuota, elimina la contención silenciosa
   entre líneas. Prerrequisito real de cualquier medición fiable.
2. **Validar el reparto de presupuesto en vivo** — standard tier con
   `PHASE_BUDGET_SHARE` activo; los shares están fijados por tests pero nunca
   han corrido contra modelos.
3. **G2 acotado**: configurar Lean local y correr un smoke por motor. Es lo
   que hoy impide llamar "científica" a cualquier campaña con obligaciones
   formales, y el bug Unicode lo tenía enmascarado.
4. **Pilot comparativo H3** (`campaign` vs `full-vnext1` vs `full-linear`) con
   el arnés ya construido. Es la primera medición que responde "¿investiga
   mejor?" y la más cara: presupuesto propio, decisión aparte.

## 5. Decisiones que corresponden a Nelson

1. ¿Candado compartido de máquina (opción a) o disciplina manual?
2. ¿Committear en producción el arreglo Unicode ya aplicado y verificado?
3. ¿Divergencia deliberada de backends hasta G6, o extracción de un backend
   versionado ahora?
4. Orden y presupuesto de los pasos 2–4 del camino.
