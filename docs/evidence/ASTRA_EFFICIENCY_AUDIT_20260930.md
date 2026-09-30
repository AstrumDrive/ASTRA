# Auditoría de eficiencia de ASTRA frente a su objetivo (2026-09-30)

Pregunta de Nelson: ¿ASTRA es eficiente para lo que se construyó, ayudar en la
investigación y ser más potente que usar los modelos por separado?

Alcance: producción (`Dev/ASTRA`, línea 1.0 con los portes de 2.0) entre julio y
septiembre de 2026. Fuentes: los depósitos de la propia ASTRA (checkpoints de
ciclo, cola de trabajos, autopsias de CLI), la cola compartida de ASTRUM, los
eventos de `project-memory`, y los documentos de evidencia ya existentes de las
dos líneas. Nada de este documento es evidencia publicable
(`PUBLICATION_POLICY.md`); es diagnóstico interno. Cada cifra lleva su fuente en
la sección 8. Las cifras del pool de ciclos se regeneran con
`scripts/audit_cycle_pool.py`.

## 1. Respuesta corta

ASTRA son dos herramientas distintas que comparten nombre, y rinden de forma
muy distinta.

- **El brazo de ejecución** (`astra_execute`, `astra_submit`, la cola de
  ASTRUM, los motores) es el que sostiene la investigación real: 5.049
  trabajos en ASTRUM en dos meses, 86 % con éxito, mediana de 52 s en los
  trabajos locales, ocho motores enrutados, procedencia por manifiesto. Aquí
  ASTRA es claramente más que los modelos sueltos, porque los modelos sueltos
  no ejecutan nada.
- **El ciclo deliberativo** (conjetura, traducción, revisión independiente,
  oráculo, análisis) es caro y poco fiable: de 264 ciclos de investigación
  terminados, 63 dieron veredicto (24 %); en el 72 % el oráculo nunca llegó a
  correr; cuesta 1,5 horas de tubería por veredicto; y de 197 objetivos
  distintos, 49 llegaron a veredicto, 48 de ellos en el primer ciclo. Reintentar
  no convierte.
- **El riesgo mayor no es de eficiencia sino epistémico:** la medición pareada
  del 17 de agosto sobre 23 casos científicos dio en la línea 1.0 una
  aceptación falsa de 0,42 (cinco claims falsos devueltos como VALIDATED) frente
  a 0,0 en 2.0. La diferencia es el eje de re-anclaje al claim original
  (`original_claim_verdict`), que hoy sigue sin existir en producción. Un
  VALIDATED de producción es evidencia sobre la conjetura acotada que ASTRA
  formó, no necesariamente sobre lo que se preguntó.
- **La comparación que motiva la pregunta nunca se ha medido.** No existe un
  brazo base "un solo modelo, sin revisor ni guardas" en ningún benchmark
  congelado. Lo más cercano es que la guarda determinista sola detecta el 36 %
  de los validadores defectuosos burdos y cualquier revisor de modelo el 100 %,
  y que en la evaluación humana ciega de 2.0 la arquitectura lineal puntuó por
  encima de la deliberativa (50,1 frente a 40,8 sobre 100, n = 8).

## 2. Qué se usa de verdad

| Uso | Cifra | Lectura |
|---|---:|---|
| Trabajos en la cola compartida de ASTRUM (ago-sep) | 5.049 | 2.732 en agosto, 2.317 en septiembre; unos 80 al día |
| Resultado | 4.336 éxito, 658 fallo, 32 timeout, 19 cancelados | 86 % de éxito |
| Por cliente | nelson 4.676, astra-2.0-dev 366, codex 7 | casi todo desde los agentes de Nelson |
| Por motor | python 4.315, sci 505, pkgs 124, sage 74, lean4 10, maxima 8, cadabra 8 | los motores CAS y formales se usan poco |
| Por proyecto | general 3.825; high_speed_subluminal_warp 293; document_physics_audit 89; thermodynamic_actuators 72; warp-acceleration 58; orbit-sim 38 | un proyecto consume la mayoría del uso etiquetado |
| Trabajos locales desacoplados (`workspace/jobs`) | 199 | PASS 111, FAIL 43, sin veredicto 40; mediana 52 s, p90 401 s |
| Eventos de proyecto que citan ASTRA | 633 en high-speed warp; 47 QPG; 41 spectral-smarr; 26 Möbius; 14 hollow-core; 11 quenched scalar; 10 Kondo | de 3.975 eventos totales |

El brazo de ejecución se usa mucho y falla poco. Los 658 fallos de la cola son
en su gran mayoría validadores que imprimen FAIL o errores de script, es decir,
información, no averías.

## 3. El ciclo deliberativo, con números

Pool: 301 ciclos no de suite (julio-septiembre), 272 terminados, 29 matados por
el muro externo. De los terminados, 8 son el lote de benchmark del 17 de
agosto (7 de 8 con veredicto) y 264 son de investigación.

| Métrica (264 ciclos de investigación terminados) | Valor |
|---|---:|
| Con veredicto (VALIDATED o REFUTED) | 63 (24 %) |
| VALIDATED / REFUTED / NON_DECIDABLE | 59 / 4 / 7 |
| Sin veredicto ni NON_DECIDABLE | 190 (72 %) |
| El oráculo llegó a ejecutar algo | 74 (28 %) |
| Mediana de duración | 1.314 s (22 min); p75 1.787 s |
| Mediana de duración de los que dieron veredicto | 896 s (15 min) |
| Horas de tubería consumidas | 96,3 h |
| Horas de tubería por veredicto | 1,53 h |
| Objetivos distintos | 197 |
| Objetivos que llegaron a veredicto | 49 (25 %) |
| Ciclo en el que se alcanzó el veredicto | 48 en el primero, 1 en el octavo |

Por qué terminan sin veredicto (194 ciclos: los 190 sin estado más 3
CODE_ERROR y 1 API_ERROR):

| Causa | Ciclos |
|---|---:|
| El revisor independiente no aprobó tras el tope de revisiones | 96 |
| Timeout de un CLI (25 de Claude, 16 de Codex, resto varios) | 46 |
| Otros (fallo de análisis, guardas) | 17 |
| Detector de atasco: misma clase de defecto repetida | 11 |
| Cuota agotada en toda la escalera | 10 |
| Otros API_ERROR | 10 |

Reparto del tiempo de modelo y oráculo: traducción 34 %, conjetura 27 %,
revisión 17 %, parches del traductor 17 %, estructuración 2 %, análisis 2 %,
navegación 1 %, **ejecución 0,6 %**. La tubería gasta el 99 % del tiempo
escribiendo y discutiendo el validador y el 1 % ejecutándolo.

Tendencia por mes (investigación): julio 0 de 12 con veredicto; agosto 33 de
151 (22 %), oráculo en el 23 %, mediana 1.178 s; septiembre 30 de 101 (30 %),
oráculo en el 39 %, mediana 1.435 s. Los cambios de septiembre (estructurador
C3, detector de atasco C2, NON_DECIDABLE) subieron la tasa de veredicto y la
fracción de ciclos que llegan a computar, a costa de ciclos más largos.

Sobre el coste: el checkpoint solo guarda `cli_cost_usd` cuando el ciclo produce
resultado, así que los 190 ciclos fallidos no tienen coste registrado. En los 74
ciclos con telemetría (septiembre), mediana 1,58 USD-equivalente por ciclo y
137 en total. El coste real de los fallidos es invisible hoy; el tiempo (96 h)
es el único indicador completo.

## 4. La calidad de lo que sale

**Cuando el ciclo cierra, cierra bien, con una excepción grave.**

- Gate H1 estándar de 2.0 (2026-08-12, 23 casos científicos decidibles):
  aceptación falsa 0,0, rechazo falso 0,0, exactitud estricta 0,74 (IC95
  0,54-0,88), fallo operativo 0,17. Ningún fallo fue epistémico.
- Medición pareada 1.0 contra 2.0 sobre el mismo tier (2026-08-17): **1.0
  aceptación falsa 0,42** (cinco claims falsos aceptados como VALIDATED),
  exactitud 0,52, fallo operativo 0,26; 2.0 aceptación falsa 0,0, exactitud
  0,70, fallo operativo 0,26. "1.0 falla afirmando falsedades, 2.0 falla
  quedándose sin tiempo." La diferencia es el eje `original_claim_verdict`
  (SUPPORTED, REFUTED, INCONCLUSIVE, SUBSTITUTED), que ancla el veredicto al
  claim del usuario y no a la conjetura formada. Ese eje existe en 2.0
  (`astra_tool.py`, `core/llm_client.py`) y **no aparece ni una vez en
  producción**; `scripts/check_line_drift.py` confirma que producción no tiene
  nada que 2.0 no tenga, no al revés. No se ha vuelto a medir la aceptación
  falsa de producción desde agosto; nada de lo portado después toca ese eje.
- Piloto de independencia del revisor (2026-09-11, 182 auditorías, 14 casos):
  la guarda determinista sola detecta 4 de 11 validadores defectuosos
  (sensibilidad 0,36); cualquier revisor de modelo, 11 de 11, sea el mismo
  modelo, otro modelo del mismo proveedor u otro proveedor. Especificidad sobre
  los 3 casos sanos: 0,33 el mismo modelo, 0,67 los demás. Nada sobrevive a
  Holm. El revisor de modelo se gana el puesto; cuál sea da igual con defectos
  burdos.
- Lectura de cuatro rechazos completos de septiembre (`audit_cycle_pool.py`
  no los imprime; están en los checkpoints del 15 y 16 de septiembre): los
  cuatro son sustantivos y correctos. El revisor rechaza validadores que
  muestrean en vez de probar, que usan cuadratura no certificada con una
  tolerancia que puede esconder la violación, que omiten una rama, o cuyos
  chequeos no pueden fallar. Es decir, el 36 % de ciclos que mueren en el
  revisor no son en general capricho del revisor: son validadores del traductor
  que no prueban el claim decisivo dentro de dos revisiones. Las etiquetas más
  frecuentes lo confirman: `missing_assumption` 321, `wrong_domain` 202,
  `self_comparison` 179, `sampling_as_proof` 143, `wrong_tolerance` 137.
- Evaluación humana ciega (2.0, 2026-08-22, 8 celdas, 2 evaluadores): la
  configuración lineal puntuó 50,1 sobre 100 y la deliberativa completa 40,8.
  n minúsculo y casi toda la diferencia viene de un caso. No es una medida de
  la arquitectura; es la única medida humana que existe.

## 5. ¿Más potente que los modelos por separado?

Lo que sí está medido:

- Sin ASTRA, un modelo que escribe y corre su propio validador no tiene ni
  guarda determinista ni revisor. La guarda sola atrapa el 36 % de los
  defectos burdos; el revisor de modelo, el 100 %. Luego el revisor aporta
  detección real que un modelo solo no tendría.
- El oráculo ejecuta de verdad y deja procedencia (job, cliente, motor, sha,
  veredicto). Un modelo solo puede narrar cálculos que no hizo; aquí no puede.
- NON_DECIDABLE con líneas `MISSING:` (7 en septiembre) es una salida honesta
  que un modelo solo rara vez da.

Lo que no está medido, y es exactamente la pregunta:

- Nunca se ha corrido el brazo base "un solo modelo, un solo pase, sin revisor
  ni guarda" sobre los 23 casos científicos congelados. Sin ese brazo no se
  puede afirmar que la deliberación completa acierte más, ni que la aceptación
  falsa de 0,42 medida en 1.0 sea mejor o peor que la del modelo solo.
- La ablación `full` contra `full-linear` de 2.0 se intentó cuatro veces y
  ninguna fue interpretable (fallo operativo por encima del umbral).

Conclusión condicional: **ASTRA es más potente que los modelos sueltos en lo
que ejecuta y en lo que rechaza; no está demostrado que lo sea en lo que
afirma.** Y en producción, lo que afirma tiene una tasa de aceptación falsa
medida de 0,42 en agosto que nadie ha vuelto a medir.

## 6. Veredicto

1. **Rinde:** el brazo de ejecución y su procedencia; las guardas
   deterministas como filtro barato; el revisor como detector de validadores
   defectuosos; NON_DECIDABLE como salida honesta. Esto es lo que la
   investigación consume de hecho (Kondo, high-speed warp, hollow-core,
   spectral-smarr).
2. **No rinde:** el ciclo deliberativo como productor de veredictos. Un
   veredicto cada 1,5 horas de tubería, tres de cada cuatro ciclos sin
   veredicto, tres de cada cuatro sin cómputo, y el reintento no ayuda.
3. **Compromete el objetivo:** la ausencia del re-anclaje en producción. Sin
   él, un VALIDATED puede ser una respuesta correcta a otra pregunta.

## 7. Recomendaciones, por coste y beneficio

1. **Portar `original_claim_verdict` a producción** (cambio acotado en el
   analista y en el reporte; en 2.0 ya tiene tests y la medición 0,42 → 0,0).
   Es la única acción con efecto epistémico medido. Después, repetir el tier
   estándar en producción para tener la cifra de hoy (unas 2,5 h y cuota).
2. **Medir el brazo base** que responde la pregunta de este documento: los 23
   casos científicos congelados con "un modelo, sin revisor, sin guarda", en
   la misma tabla que producción: aceptación falsa, exactitud, tiempo y coste.
   Sin esto la pregunta seguirá abierta.
3. **No reintentar objetivos.** 48 de 49 veredictos llegaron en el primer
   ciclo; los objetivos con 2 a 5 ciclos no convirtieron. Si un ciclo muere en
   el revisor, la palanca es cambiar la pregunta (acotarla con
   `structure_request`), no volver a lanzarla.
4. **Convertir la muerte en el revisor en NON_DECIDABLE con `MISSING:`.** Hoy
   96 ciclos gastaron conjetura, traducción y dos revisiones y devolvieron un
   error. El revisor ya sabe qué falta (su razonamiento lo dice); devolverlo
   como entradas requeridas convierte el fallo en información reutilizable.
5. **Exigir al traductor pruebas certificadas cuando el claim es universal**
   (Z3 sobre el dominio completo, aritmética de intervalos, no muestreo), que
   es lo que el revisor pide en `sampling_as_proof` y `wrong_tolerance`. O, al
   revés, aceptar en el prompt del revisor una clase "evidencia numérica
   acotada" con veredicto degradado, en vez de rechazo.
6. **Registrar el coste de los ciclos fallidos.** Hoy el 72 % del gasto no
   tiene telemetría de coste. Sin eso no se puede optimizar la cuota.
7. **Usar el brazo de ejecución por defecto y el ciclo solo para claims ya
   acotados.** Es lo que la propia práctica de Nelson y de Codex ya hace: 5.049
   ejecuciones frente a 264 ciclos.

## 8. Libro de cuentas

| Afirmación | Fuente |
|---|---|
| 301 ciclos, 272 terminados, 264 de investigación, 63 con veredicto, 28 % con oráculo, duraciones, causas, fases, rondas, objetivos | `venv/Scripts/python.exe scripts/audit_cycle_pool.py` sobre `workspace/cycle_checkpoints/` (2026-09-30) |
| Cola de ASTRUM: 5.049 trabajos, clientes, motores, proyectos, estados | `ssh astrum`, `~/astra-worker/cluster/state.db`, tabla `jobs` (sqlite3, agrupado por `client_id`, `engine`, `project`, `status`, mes de `created_ts`) |
| 199 trabajos locales, PASS 111 / FAIL 43 / NONE 40, mediana 52 s | `workspace/jobs/*/job.json` y `result.json` |
| Eventos de proyecto que citan ASTRA | `Dev/project-memory/events/*.jsonl`, grep de `astra` en summary, details, evidence |
| Aceptación falsa 0,0, exactitud 0,74, fallo operativo 0,17 (2.0) | `Dev/ASTRA-2.0/docs/evidence/ASTRA2_H1_STANDARD_20260812.md` |
| 1.0 aceptación falsa 0,42 frente a 0,0 en 2.0; cinco VALIDATED falsos | `Dev/ASTRA-2.0/docs/evidence/ASTRA1_VS_ASTRA2_STANDARD_20260817.md` |
| `original_claim_verdict` ausente en producción | `grep -c original_claim_verdict astra_tool.py core/*.py` en `Dev/ASTRA` (0) y en `Dev/ASTRA-2.0` (9); `scripts/check_line_drift.py` de 2.0: PRODUCTION ONLY 0 |
| Piloto del revisor: sensibilidad 0,36 guarda, 1,00 modelos; especificidad 0,33-0,67 | `REVIEW_INDEPENDENCE_PILOT_20260911.md` |
| Evaluación humana ciega 50,1 frente a 40,8 | `Dev/ASTRA-2.0/docs/evidence/ASTRA2_G3_G4_STATUS_20260822.md` §1 y §9 |
| Cuatro rechazos completos del revisor (15 y 16 de septiembre) | checkpoints en `workspace/cycle_checkpoints/` con `error` que empieza por "Independent reviewer did not approve" |
| Snapshot de julio: sin coste por descubrimiento demostrado | `docs/evidence/PRODUCTION_SNAPSHOT_20260726.md` |
| Coste solo registrado en ciclos con resultado | campo `result.cli_cost_usd` en los checkpoints; ausente cuando `stage` es `tool_error` |
