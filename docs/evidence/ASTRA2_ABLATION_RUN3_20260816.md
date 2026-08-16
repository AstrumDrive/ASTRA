# Ablación sobre el protocolo enmendado: el cuello se movió otra vez (2026-08-16)

`research_trajectory_20260815_210230`, completa: 8 celdas, 18 ciclos, ~7 h,
presupuesto de ciclo **2400 s** (enmienda A1). Sin contaminación de arnés.

## El criterio sigue sin cumplirse

| | `full` | `full-linear` |
|---|---|---|
| celdas | 4 | 4 |
| ciclos | 8 | 10 |
| **VALIDATED** | **0** | **3** |
| averías | 5 | 4 |
| rechazos del revisor | 2 | 3 |
| `operational_failure_rate` | 1.00 | 0.75 |
| trazabilidad cruzada (proxy) | **0.210** | 0.133 |
| llamadas a modelo por celda | 16.0 | 26.3 |

Separando lo que el agregado mezcla —**averías** (timeout, presupuesto agotado)
frente a **rechazos del revisor**, que son el sistema haciendo su trabajo—:

| | averías / ciclos | |
|---|---|---|
| `full` | 5 / 8 | **0.63** |
| `full-linear` | 4 / 10 | **0.40** |

Sigue muy por encima del 0.2 que fijamos. **La comparación no es interpretable.**

## Lo que la enmienda sí consiguió

Los ciclos ya no mueren contra la pared: mediana de `total` **1542 s** con
máximo **2318 s**, contra los 1471 s clavados de la corrida anterior. El
presupuesto dejó de ser el límite.

## Y el nuevo cuello está a la vista

Ocho timeouts, siete de ellos del **traductor**:

```text
techos alcanzados: 240, 277, 279, 360, 480, 480, 480, 480
víctimas: claude-opus-4-8 ×7, gpt-5.6-sol ×1
```

Cuatro murieron **exactamente en 480 s**, que es
`ASTRA_TRANSLATOR_TIMEOUT` en `.env`. Ese valor se dimensionó para un ciclo de
1500 s; con 2400 s de presupuesto **ya no escala con nada**. Y la mediana real
de traducción en esta corrida es **573 s**, con máximo de 1194 s: el techo está
por debajo de la mediana de la tarea.

Es el mismo hallazgo del ciclo warp del 14-ago —que necesitó 696 s de
traducción— reapareciendo en el benchmark.

## El dato incómodo

**`full` no validó ni un ciclo; `full-linear` validó tres.** Va en contra de la
hipótesis del proyecto.

No se puede concluir nada de ahí todavía, y conviene decir por qué con
precisión: con 63 % y 40 % de averías, qué brazo valida depende sobre todo de
**dónde cayeron las averías**, no de cómo razona. `full` además gastó menos
llamadas por celda (16 contra 26) porque murió antes, así que tuvo menos
oportunidades. Con n=4 celdas por brazo, 0 contra 3 es compatible con el azar.

Pero queda anotado: es la primera señal medida, y apunta en contra.

## Siguiente paso

El techo del traductor debe escalar con el presupuesto del ciclo, igual que ya
se hizo con el modo persistente. Con 2400 s y una mediana de traducción de
573 s, 480 s es sencillamente pequeño.

Después de eso —y solo si las averías bajan de 0.2— la comparación empieza a
significar algo. Antes no.
