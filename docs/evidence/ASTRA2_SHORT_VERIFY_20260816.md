# Corrida corta de verificación (2026-08-16)

`research_trajectory_20260816_114318`: 1 caso (`gr_invariant_audit`),
2 configuraciones, semilla 11, ≤2 ciclos. 57 min.

## Resultado

| cfg | ciclos | VALIDATED | fallo operativo | timeouts |
|---|---|---|---|---|
| `full` | 2 | **2** | **0.0** | 0 |
| `full-linear` | 2 | **2** | **0.0** | 0 |

**4 de 4 ciclos validados, cero averías.** Es la primera vez que la tubería
completa la cadena entera en ambos brazos sin una sola avería.

## Lo que esto NO demuestra

**El arreglo del techo del traductor no se ejerció.** Los cuatro tiempos de
traducción fueron 173, 155, 244 y 296 s — mediana 208, máximo 296. Todos caben
holgadamente incluso bajo el techo viejo de 480 s. El techo nuevo de 840 s no
llegó a tocarse, así que **este resultado no puede atribuirse a él**.

Los ciclos también fueron mucho más rápidos que los de la corrida 3 (totales
685, 556, 718 y 1668 s, contra una mediana de 1542 s). Parte de la diferencia es
variabilidad de carga de los modelos, no arquitectura.

Con n=4 y ambos brazos al 100 %, tampoco hay señal arquitectónica — y no debería
haberla a este tamaño.

## Lo que sí es sugerente

El cuarto ciclo (`full`) duró **1668 s** con **551 s de reparación** y aun así
validó. Bajo el régimen anterior —presupuesto de 1800 s y una reparación que
recibía 165 s de mediana— ese ciclo casi con certeza habría muerto. Es
consistente con que la reserva y el presupuesto ampliado hicieran su trabajo,
pero un caso no es una medición.

## Lectura

El criterio que fijamos —fallo operativo < 0.2— **se cumple aquí**, con la
advertencia de que 4 ciclos no son base para declarar fiabilidad. Lo que la
corrida sí establece es que **no queda ningún bloqueo estructural conocido**: la
cadena completa —conjetura, traducción, revisión independiente, reparación,
ejecución, análisis, navegación— funciona de extremo a extremo en ambos brazos.

A partir de aquí el seguimiento pasa a ser por uso real, que además es más
exigente: el ciclo warp del 14-ago necesitó 696 s de traducción, por encima de
todo lo visto en el benchmark.
