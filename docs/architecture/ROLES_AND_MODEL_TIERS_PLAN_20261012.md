# Plan: roles distintos y modelos por subtarea

12 de octubre de 2026 · base: ASTRA 1.1.8 (`0e0fa98`) · estado: **plan, sin código**

## 0. Por qué

En la charla del 12 de octubre, la analogía del grupo de postdocs funcionó. La
crítica que recibió: si todos los postdocs tienen la misma formación, la
discusión pierde diversidad, justo en temas de frontera. Este plan responde a
esa crítica y a una segunda idea de Nelson: usar el modelo más fuerte donde
rinde (planificar, razonar la lógica) y uno más barato donde basta (escribir el
código).

## 1. Lo que ya está medido

| Hecho | Fuente | Qué implica |
|---|---|---|
| Proponentes de dos compañías (Codex + Gemini) contra dos Codex: **16 contra 17 aciertos en 40 casos pareados**; discordantes 0 contra 1 | experimento preregistrado `benchmarks/external/diversity_frozen_v1.json`, corrido el 24-25 jul; logs en `workspace/external_comparison_runs/diversity_*` | La diversidad **de compañía** en la conjetura no dio ganancia medible. Apoya la crítica. Salvedad: benchmarks externos (SciCode, FrontierScience) y versión de julio |
| En los últimos 200 ciclos, **123** tienen más de una entrada en el historial de revisión | `workspace/cycle_checkpoints` (`code_review_history`) | Rehacer el test es lo normal, no la excepción |
| Clases de defecto que más devuelve el revisor: `sampling_as_proof` en **52** de 104 ciclos con defectos, `missing_domain` en **37** | `review_defect_trace` de los mismos checkpoints | Son defectos **de estrategia**, no de código: se verían en un plan de una página, antes de escribir 200 líneas |
| Reparto del tiempo en 80 ciclos: traducir 31 %, revisar 25 %, conjetura 18 %, analizar 13 %, parchear 11 %, ejecutar 3 % | `astra_telemetry` | El coste está en escribir y revisar el test |
| Producción usa un solo proponente (`no-ensemble`) desde el 30-sep, porque el ensemble y la navegación se comían el 80 % del ciclo | `docs/evidence/PRODUCTION_PROFILE_AND_BASELINE_ARM_20260930.md` | Hoy la diversidad en la exploración es mínima |

Conclusión de partida: la diversidad útil probablemente viene **del rol y del
método**, no de la marca del modelo. Y el mayor ahorro está en separar el plan
del código.

## 2. Hipótesis

- **H1, modelos por subtarea.** El autor del test se parte en dos: un
  *planificador* con el modelo más fuerte escribe un plan corto (lógica,
  pseudocódigo, dominio, ruta de FAIL); un *programador* con un modelo medio lo
  implementa. Con una revisión del plan antes del código, bajan las rondas de
  revisión y el coste, sin perder aciertos.
- **H2, roles distintos.** Un escéptico que busca el contraejemplo y una
  segunda ruta por otro método encuentran errores que un segundo proponente
  igual no encuentra, sobre todo en afirmaciones donde la versión "de libro"
  está mal.
- **H3, correlación.** Los errores de Claude, Codex y Gemini están
  correlacionados. Hay que medir cuánto, para saber cuánto vale mezclar
  compañías.

## 3. Fases

### F0. Medir antes de construir (sin cambiar código)

1. **¿Fable 5.1 está disponible?** Una llamada de prueba con
   `claude --model claude-fable-5-1` en la cuenta Max de Astrum Drive. Medir
   también cómo consume la ventana de cuota. Si no está disponible, el
   planificador usa Opus 5.5 y el plan sigue igual.
2. **Correlación de errores (H3).** Correr el brazo `single-model` (una
   llamada, sin revisor) con cada compañía sobre los 50 claims del corpus de
   investigación. Hoy ese brazo es solo de Codex
   (`core/architecture_configs.py`), así que hay que añadir dos entradas,
   `single-model-claude` y `single-model-agy`. Es un cambio pequeño, con su
   test. Medir:
   - aciertos de cada una;
   - fallos simultáneos por pares;
   - coeficiente phi.

   Son unos 150 ciclos baratos, de 2 a 3 minutos cada uno.
3. **Corpus de trampas.** Unos 10 a 15 claims donde la versión popular o
   publicada está mal y la verdad la tenemos medida. Es el caso exacto de la
   crítica: un grupo con la misma formación cae en la misma trampa. Hay
   material propio:
   - los dos signos de la ecuación impresa de BGG22/23 y BCGG24 (L3);
   - el umbral DEC con m' = 0;
   - el índice repetido de Kondo;
   - convenciones de signatura.

   Cada claim lleva su script de referencia y su salida depositada en `reference/outputs/`.

**Entregable:** un informe en `docs/evidence/` con la correlación medida y la
disponibilidad de Fable. **Decisión de Nelson:** si sigue F1 tal cual.

### F1. Plan y código con modelos distintos (H1)

Cambios en el ciclo, todos detrás de `ASTRA_AUTHOR_SPLIT` (apagado por
defecto hasta medir):

1. **Planificador** (fase nueva `PLAN`, modelo `ASTRA_PLANNER_MODELS`, por
   defecto `claude-fable-5-1,claude-opus-5-5`). Devuelve un plan estructurado:
   - proposición tal cual;
   - objetos y definiciones tomados de la intuición;
   - dominio y cuantificadores;
   - patas decisivas;
   - ruta de FAIL alcanzable;
   - método (exacto, certificado o numérico, con el piso numérico);
   - motor;
   - tiempo estimado.

   Sin código.
2. **Revisión del plan.** El revisor (Codex) lo juzga con las mismas clases de
   defecto de `core/review_defects.py`: `sampling_as_proof`,
   `missing_domain`, `unreachable_failure`, `wrong_tolerance`. Máximo dos
   rondas, y ninguna línea de código antes de aprobar.
3. **Programador** (fase `CODE`, `ASTRA_CODER_MODELS`, por defecto
   `sonnet,claude-opus-5-5`). Implementa el plan aprobado, que va dentro del
   prompt.
4. **Revisión del código.** Pasa a ser sobre todo de fidelidad al plan. Las
   reglas actuales siguen vigentes.
5. **Reparación de barato a fuerte.** El reparador arranca en Sonnet. La
   escalada por calidad que ya existe (`_escalate_agent_models`) sube a
   Opus o Fable si el arreglo vuelve a fallar. Hoy está inactiva porque el
   autor arranca en Opus.
6. **Contrato y registro:**
   - `core/architecture_contract.py` declara los modelos por rol;
   - el manifiesto y el checkpoint registran qué modelo hizo cada subtarea;
   - la telemetría separa `plan`, `plan_review` y `code`;
   - `ASTRA_TRANSLATOR_MODELS` sigue funcionando como alias cuando el
     corte está apagado.
7. **Tests** del flujo nuevo con el arnés de ciclo falso (`tests/test_input_request_cycle.py`).

**Puerta de medición**, A/B pareado contra 1.1.8 sobre los 50 claims, después del tier smoke:

| Medida | Criterio para activarlo por defecto |
|---|---|
| Veredictos falsos | **0**, obligatorio |
| Aciertos | no peor que 1.1.8 en más de 1 de 50 |
| Rondas de revisión del test | menos que 1.1.8 |
| Duración mediana y cuota por ciclo | igual o menor |

Los criterios se fijan antes de correr, para no ajustarlos al resultado.

### F2. Roles distintos (H2)

Los roles se distinguen por **obligación**, no por tono. Cada uno tiene una
salida verificable:

| Rol | Obligación | Salida |
|---|---|---|
| Proponente | una proposición decidible | la conjetura actual |
| **Escéptico** | buscar dónde falla: bordes del dominio, signos, convenciones, el caso degenerado | una pata de contraejemplo dentro del test, o "no encontré" con lo que probó |
| **Formalista** | escribir la afirmación tipada y señalar símbolos sin definir | alimenta las preguntas de convención y, más adelante, la spec certificada y el lenguaje tipado en Lean |
| **Segunda ruta** | decidir lo mismo **por otro método**: simbólico contra certificado, o contra Lean | un segundo validador independiente |

**Regla de veredicto con dos rutas.** SUPPORTED exige que las dos rutas
coincidan. Si no coinciden, el resultado es INCONCLUSIVE, con los dos
programas y la discrepancia, nunca un voto. Lleva su propio guardia
determinista y sus tests.

**Dónde corre.** En el perfil profundo y en las campañas de ASTRA 2.0, no en
cada ciclo de producción: cuesta más llamadas. El escéptico es el candidato a
entrar en producción si el corpus de trampas lo justifica.

**Diversidad de compañía, solo donde F0 la justifique.** Por ejemplo, el
escéptico en una compañía distinta de la del proponente si la correlación
medida es baja.

**Puerta:** corpus de trampas más los 50 claims. El escéptico o la segunda
ruta tienen que atrapar trampas que el ciclo actual deja pasar, con 0
veredictos falsos y un coste extra declarado.

### F3. ASTRA 2.0, campañas de frontera

Hasta F3 se llega solo si F2 funciona. Diseño a pasar a `ASTRA-2.0/HANDOFF.md`:

- dos proponentes con roles distintos;
- el desacuerdo se registra antes de elegir dirección (`core/diversity_metrics.py` ya mide distancia entre propuestas);
- el navegador ve las dos líneas, no solo la ganadora.

ASTRA 2.0 entra en producción solo después de pasar su propia puerta de aceptación.

## 4. Cuota y calendario

| Fase | Ciclos aprox. | Ventanas de Codex (unos 25 ciclos por ventana de 5 h) |
|---|---|---|
| F0 correlación | ~150 baratos | 2 o 3 |
| F1 A/B | ~100 completos | 4, repartidas en dos días |
| F2 | ~60 a 80 | 3 |

Cada corrida se pide a Nelson antes de lanzarla. Nada se dispara solo.

## 5. Riesgos

- **Fable puede no estar en la CLI o gastar la ventana rápido.** Lo cubre la
  escalera `fable,opus` y el chequeo de F0.
- **Separar plan y código añade una llamada.** Solo compensa si bajan las
  rondas de revisión, y eso es lo que mide la puerta de F1.
- **El programador puede desviarse del plan.** La revisión de fidelidad lo
  vigila, y el plan viaja completo en el prompt.
- **La regla de dos rutas puede volver a ASTRA más indecisa.** Por eso va
  primero en el perfil profundo y con su propia medición.
- **Puede no haber trampas suficientes.** El corpus se construye solo con
  casos verificados; si salen menos de 10, F2 se mide sobre el corpus de 50
  con un margen más modesto.

## 6. Decisiones de Nelson

1. **Lanzar F0:** la llamada de prueba a Fable, la corrida de correlación
   (unos 150 ciclos baratos) y armar el corpus de trampas.
2. **Margen de no inferioridad de F1:** se propone "no más de 1 acierto
   menos de 50, y 0 veredictos falsos".
3. **Dónde vive el escéptico:** se propone el perfil profundo primero.
