# Ablación `full` vs `full-linear`: el presupuesto se come el experimento (2026-08-14)

Etapa 6 del HANDOFF, tier canary: 2 casos × 2 configuraciones × 2 semillas,
≤3 ciclos por celda, oráculo local. 8 celdas completas, **18 ciclos**, 5 h 23 min.
Run `research_trajectory_20260814_132846`.

## La respuesta corta

**No decide nada sobre la arquitectura.** El 83 % de los ciclos falló por causas
operativas, y con 3 éxitos sobre 18 cualquier diferencia entre brazos es ruido.

**Pero sí decide otra cosa, con datos duros:** el presupuesto de ciclo acotado
está mal repartido, y la fase que paga la factura es la **reparación del
validador**.

## Lo que se midió

| | `full` | `full-linear` |
|---|---|---|
| celdas | 4 | 4 |
| ciclos VALIDATED | 1 | 2 |
| ciclos PARTIAL | 7 | 5 |
| ciclos TOOL_ERROR | 1 | 2 |
| tasa de fallo operativo | 0.92 | 0.83 |
| `autonomous_loop_yield` | 0.083 | 0.167 |
| `independent_evidence_rate` | 0.083 | 0.083 |
| `credible_evidence_per_model_call` | 0.011 | 0.016 |
| trazabilidad cruzada (proxy) | **0.436** | 0.369 |
| wall time medio por celda | 2445 s | 2422 s |
| `blind_research_quality_0_to_100` | — | — |

`autonomous_loop_yield` 0.083 vs 0.167 es **1 éxito contra 2 sobre 12 ciclos**.
No es una diferencia; es un ciclo. El único número donde `full` va por delante
—trazabilidad cruzada, que mide precisamente lo que el ensemble aporta— tiene el
mismo problema de n.

La calidad ciega sigue vacía por diseño: exige dos evaluadores humanos por celda,
ciegos a la arquitectura. No se rellena con una estimación.

## Lo que sí quedó demostrado: la reparación muere de hambre

Fases culpables de los 15 fallos: **`translator_repair` 8, `reviewer` 7**.

Los 12 timeouts medidos, con el presupuesto que quedaba al morir:

| restante al fallar (s) | 124 | 150 | 168 | 180 | 181 | 184 | 202 | 251 | 278 | 325 | 428 | 454 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **muerto a los (s)** | 94 | 136 | 162 | 178 | 181 | 186 | 213 | 287 | 93 | 114 | 157 | 169 |

Mediana: **165 s**. Ninguna de estas llamadas tuvo cerca de los 480 s
configurados: el techo efectivo no es la variable, es *la fracción de lo que
queda*, y cuando la reparación arranca ya no queda casi nada.

La separación entre éxito y fallo es limpia y es temporal:

| | mediana `total` | rango |
|---|---|---|
| ciclos VALIDATED (3) | **882 s** | 464-1031 |
| ciclos fallidos (15) | **1249 s** | 584-1376 |

Con 1440 s utilizables, **un ciclo que necesita reparación ya se gastó el
presupuesto llegando hasta ahí**. La conjetura sola tiene mediana de 276 s
—frente al p90 de 197 s medido el 13-ago— y la traducción acumulada se lleva
otros ~460 s.

## Por qué esto se ve hoy y no antes

La etiqueta `translator_repair` se introdujo esta misma mañana. Antes, esos
**8 fallos se archivaban como `reviewer`**, y la lectura habría sido «el revisor
falla 15 de 15» en lugar de «la reparación falla 8 de 15 por falta de
presupuesto». La contabilidad de fases no era cosmética: sin ella este
diagnóstico no existe.

## Qué hacer con esto

1. **No repetir el pilot completo con este presupuesto.** Tres semillas y seis
   casos multiplicarían el coste sin arreglar la causa: seguiríamos midiendo el
   reparto del presupuesto, no la arquitectura.
2. **Arreglar el reparto primero.** Dos vías, y hay que elegir con medición:
   subir el techo del ciclo acotado (el suite lo tiene congelado en 1500 s), o
   **reservar** presupuesto para la reparación en vez de darle una fracción de
   las sobras.
3. **Volver a correr la ablación después**, con la tasa de fallo operativo por
   debajo de ~0.2. Solo entonces la comparación mide lo que dice medir.

## Nota de método

Cero esperas por `BUSY` en esta corrida: el arreglo de la mañana no llegó a
ejercitarse. Las dos corridas envenenadas anteriores —la que reventó por el
parseo de `resources` y la que devolvió `operational_failure_rate: 1.0` en 45 s
por un lock retenido— están borradas, no archivadas.
