# Spec corta: ciclos que no se tranquen

Robustez de ASTRA 1.0 frente a su propio traductor. Borrador para decidir
alcance (2026-09-08). Sin implementar.

## Problema (evidencia)

Dos ciclos autonomos sobre la proposicion acotada de Abellan v03 (cache
`6bf68f83`/pid 42724 y `80a8306`/pid 30268) terminaron `tool_error` tras 3
rondas de revision cada uno. En ambos el revisor independiente **acepto la
estrategia analitica** ("sound / repairable / viable") y **rechazo el cableado**
del codigo del traductor. Los defectos forman una clase recurrente:

1. links logicos afirmados solo en comentarios (`wi_ge_mi` no prueba nada);
2. positividad no decidible: simbolos declarados independientes (`wi,wf`) y el
   check hecho sobre un `num` desconectado del `Bq` real;
3. cotas del integral **asumidas** (gate auto-confirmante: asume `IonI<=gmax*meas`);
4. continuidad certificada por proxy (solo denominador>0);
5. dominio incompleto (`L` real pero no `>0`).

El loop traductor-revisor no converge porque el traductor repite la clase y el
sistema no reconoce la repeticion como atasco: gasta el cap de revisiones y
devuelve un `tool_error` opaco. El revisor no es el problema: no debe aflojarse.
Un validador de referencia que evita los cinco defectos paso el oraculo
(`results/abellan_v03_hartree_oracle_result.json` en el proyecto del paper).

## Objetivo / no-objetivo

- **Objetivo:** que un ciclo llegue a veredicto sin que Nelson escriba la
  direccion a mano ni intervenga, y que el progreso sea visible mientras corre.
- **No-objetivo:** relajar el revisor; cambiar la arquitectura sin estampar
  procedencia; tocar los benchmarks de 2.0 (alli arquitectura y direccion son
  variables controladas).

## Componentes, en orden de implementacion

### C0. Contrato del traductor (fix de raiz)

- **Que:** reglas duras en el prompt del traductor de validacion:
  (a) todo link logico es un check **ejecutado** cuyo booleano alimenta el
  veredicto final, nunca un comentario; (b) declarar las **relaciones** entre
  simbolos para que positividad y dominio sean decidibles (`m_f = m_i + d`,
  `d>0`; `L>0`), no simbolos independientes; (c) para integrales estrictas,
  **punto exhibido + continuidad** antes que cotas de medida; (d) nunca asumir
  la conclusion (`assume X<=Y` esta prohibido: derivarla o fallar);
  (e) rama `VERDICT: FAIL` alcanzable y falsable.
- **Donde:** `agents/translator.py` (prompt). No toca al revisor.
- **Prueba:** los cinco defectos como fixtures; el traductor no los produce o el
  preflight determinista los cacha antes del revisor.
- **Costo:** bajo. **Hecho cuando:** la direccion de Abellan converge sola.

### C1. Monitor en vivo + telemetria por ciclo

- **Que:** (a) `astra_progress` (tool MCP + `scripts/astra_progress.py`): lee
  `workspace/progress/cycle_<pid>.json` y muestra fase, ronda de revision,
  tiempo por fase, presupuesto restante, refrescando cada N s;
  (b) agregador sobre `workspace/cycle_checkpoints`: duracion por ciclo,
  ciclos hasta VALIDATED/REFUTED, rondas de revision, causa de parada.
- **Datos:** ya existen (`progress`, `timings`, `code_review_history`,
  `budget`). Es vista + agregacion.
- **Costo:** bajo. **Hecho cuando:** Nelson ve el ciclo avanzar en vivo y un
  resumen "N ciclos, T total, R rondas, parada por X" al final.

### C2. Detector de atasco + re-traduccion con cambio de estrategia

- **Que:** tras cada rechazo, clasificar el defecto con la taxonomia de C0
  (link-en-comentario / positividad-no-decidible / cota-asumida /
  continuidad-proxy / dominio-faltante / otro). La **misma clase dos veces**
  = atasco. Accion escalonada: (i) inyectar una correccion **dirigida** a esa
  clase en la siguiente revision, no solo re-pasar el `reasoning`; (ii) si
  persiste, **una** re-traduccion con estrategia alternativa (p.ej. punto
  exhibido en vez de medida); (iii) si aun persiste, parar limpio con
  diagnostico "atasco en clase X" en vez de `tool_error` opaco.
- **Donde:** `astra_tool.py::_review_or_revise` (ya reinyecta
  `revision_instructions`; agregar clasificador, memoria de clases vistas y la
  estrategia alternativa).
- **Guardas:** acotado a una re-traduccion extra; respeta el presupuesto
  (loop budget-aware ya existe); nunca relaja el revisor.
- **Costo:** medio. **Hecho cuando:** Abellan converge o para con diagnostico
  de clase sin quemar el presupuesto en repeticiones.

### C3. Estructurador de peticiones (pre-ciclo)

- **Que:** paso opcional que convierte la intuicion cruda en direccion
  estructurada: claim acotado, hipotesis explicitas, decisivo vs auxiliar,
  estrategia de certificacion (analitica vs numerica), anti-patrones a evitar.
  La salida es el campo `intuition` del ciclo.
- **Donde:** agente ligero (o reuso del sintetizador) invocado por
  `astra_cycle` con `structure_request=true`.
- **Guardas:** opt-in; se guardan la peticion original y la estructurada.
- **Costo:** medio. **Hecho cuando:** una peticion cruda produce una direccion
  equivalente a la escrita a mano en este caso.

### C4. Escalada autonoma de arquitectura (solo ante atasco)

- **Que:** si C2 declara atasco, ASTRA escala **un** paso: (a) MAX mode
  (modelos top; ya existe) o (b) un perfil de escalada explicito (traductor
  mas fuerte y/o revisor alterno). Luego para.
- **Donde:** `astra_tool.py` sobre `apply_max_mode` y los perfiles de
  `core/architecture_configs.py`. El contrato de produccion debe **conocer** el
  perfil de escalada (como `quota-relief`) para no fallar-cerrado por role drift.
- **Guardas obligatorias:** opt-in (`allow_escalation`); procedencia
  **estampada** en el resultado (arquitectura efectiva por ronda); un solo
  paso; cuota-consciente (no escalar con cuota baja); **nunca** en corridas de
  benchmark.
- **Costo:** medio-alto. **Hecho cuando:** un atasco real se destraba y el
  resultado queda estampado con que arquitectura lo produjo.

## Transversal: procedencia

Todo resultado estampa: arquitectura efectiva (por ronda si escalo), peticion
original vs estructurada, clases de defecto detectadas, rondas, tiempos por
fase. Sin esto, C3 y C4 corrompen cualquier medicion posterior.

## Entrega

`C0 -> C1 -> C2 -> C3 -> C4`. Cada uno en rama, con tests y auditoria
adversarial, sin push. **C0 + C1 es la primera entrega**: bajo costo, ataca la
raiz y da visibilidad inmediata.

## Decisiones tomadas (Nelson, 2026-09-08)

1. **C0:** entra como **overlay opt-in** (como `muse-trial` / `quota-relief`):
   marcador `config/strict_translator.enabled` activa el contrato estricto.
   Se mide antes de considerarlo default. Produccion no cambia sin el marcador.
2. **C4:** **perfil dedicado** de escalada (traductor mas fuerte + revisor
   alterno), registrado en `core/architecture_configs.py` y conocido por el
   contrato de produccion. No solo MAX mode.
3. **C3:** **opt-in** (`structure_request=true`); se guardan peticion original
   y estructurada.
4. **C2:** **reemplazar** una ronda ciega por una dirigida, sin subir el cap
   de revisiones (mismo presupuesto, mas inteligente).

Primera entrega: C0 + C1.

## Estado de implementacion (2026-09-08)

- **C0 implementado** como overlay composable `strict_translator` (no excluye
  a `muse_trial`/`quota_relief`). El flag queda **estampado en el manifest**
  (`controls.translator_strict_contract`, default off): como la clave del cache
  de ciclos embebe el manifest, una re-corrida en modo estricto nunca reproduce
  un veredicto cacheado no-estricto, y cada resultado/checkpoint registra que
  contrato lo produjo -- lo que exige 'Transversal: procedencia' y lo que hace
  medible la decision 1. Un primer intento omitia este estampado y una
  auditoria adversarial lo cazo.
- **C1 implementado**: `core/cycle_telemetry.py` (stdlib), `scripts/astra_progress.py`
  (`--watch`, `--summary`), tool MCP `astra_telemetry`, y `astra_probe`
  corregido. Rondas de revision y presupuesto en vivo salen del heartbeat (el
  checkpoint no se actualiza durante el loop de revision); un checkpoint sin
  estado terminal se reporta `incomplete` (kill/en vuelo), nunca como
  completado; ciclos-hasta-resultado se computa **por objetivo**; `queued`+
  proceso muerto es una salida limpia (BUSY/cache), no un kill; se prefiere el
  `.tmp` hermano mas nuevo (en Windows un lector puede hacer fallar el
  `os.replace` final de astra_tool).
