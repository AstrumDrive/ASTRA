# Ablación completa y limpia: la reserva funciona, el ciclo no cabe (2026-08-15)

`research_trajectory_20260814_190454`, terminada: **8 celdas, 19 ciclos**, sin
un solo ciclo contaminado (0 `WinError 5`, 0 `Not logged in`). Es la primera de
las cuatro tentativas que produce datos válidos de principio a fin.

## El criterio no se cumple

| | `full` | `full-linear` |
|---|---|---|
| celdas | 4 | 4 |
| **tasa de fallo operativo** | **0.9167** | **0.9167** |
| `autonomous_loop_yield` | 0.0833 | 0.0833 |
| `independent_evidence_rate` | 0.0833 | 0.0833 |
| `macro_resolution_rate` | 0 | 0 |
| trazabilidad cruzada (proxy) | **0.237** | 0.115 |
| `credible_evidence_per_model_call` | 0.0086 | 0.0096 |
| llamadas a modelo por celda | 20.2 | 15.0 |
| `blind_research_quality_0_to_100` | — | — |

Fijamos de antemano que por debajo de **0.2** la comparación sería
interpretable. Está en **0.92**. **No procede el pilot completo.**

Ciclos: 2 VALIDATED, 14 PARTIAL, 3 TOOL_ERROR. Seis de las ocho celdas pararon
por `consecutive_operational_failures` tras dos ciclos.

## La reserva sí funcionó — se ve en el dato

Los seis ciclos que fallaron en `translator_repair` muestran todos lo mismo:

```text
patch = 481 s     total = 1471 s     remaining = 329 s
```

La reparación recibió **481 s**, no los 165 s de mediana de la corrida 1. El
arreglo hace exactamente lo que prometía. Y sin embargo el ciclo sigue
fallando, porque el problema se movió de sitio.

## Dónde está ahora el cuello: el ciclo no cabe en 1800 s

Medianas de fase sobre 17 ciclos:

| fase | mediana | máximo |
|---|---|---|
| conjetura | 319 s | 438 s |
| traducción | 514 s | 842 s |
| revisión | 128 s | 241 s |
| reparación | 464 s | 482 s |
| **suma de medianas** | **1424 s** | |

Con 1740 s utilizables (1800 menos el buffer de retorno), quedan **316 s** para
ejecución, análisis y navegación — que la corrida 1 midió en ~270 s. El margen
real es de **menos de 50 s**.

Y se ve en el resultado: **6 de 17 ciclos terminan a los 1471 s**, el punto
exacto donde la reserva impide seguir. No es dispersión, es un tope.

**Un ciclo mediano cabe por los pelos y no sobrevive a ningún imprevisto.** Una
tubería de investigación sin margen para un solo reintento falla en cuanto algo
se tuerce, que es precisamente lo que muestra el 0.92.

## Qué NO es esto

No es contaminación del arnés. Las tres tentativas anteriores midieron un lock
retenido, el Programador de tareas y una sesión caducada; esta mide **a ASTRA**.
El 0.92 es una propiedad real del sistema bajo el presupuesto que su propio
benchmark declara.

## Decisión pendiente

Dos caminos, excluyentes, y ninguno es mío:

1. **Ampliar el presupuesto congelado** de 1800 s a ~2400 s. Da margen para un
   reintento y deja de medir la pared en vez de la arquitectura. Contra: el
   suite está congelado (`status: frozen_before_live_execution`); enmendarlo
   exige hacerlo explícito y fechado. A favor: **ningún pilot válido se ha
   corrido contra él todavía**, así que no rompe comparabilidad con nada.
2. **Abaratar las fases**. Conjetura (319 s) y traducción (514 s) se llevan el
   58 % del ciclo. La conjetura es un ensemble de dos proveedores más críticas
   más síntesis; ahí hay margen. Contra: cambia la arquitectura que queremos
   medir, así que hay que medir antes y después.

Mi recomendación: **la 1**, y correr después la ablación otra vez. La 2 mezcla
la optimización con el objeto de estudio.

## Dos defectos abiertos, sin diagnosticar

- `ValueError: ASTRA subprocess emitted no JSON object` (×2). El runner no
  conserva el stdout crudo cuando el parseo falla, así que no se puede
  distinguir un cuelgue de una salida corrupta.
- Timeouts de codex a los **6 s** y **1 s**, y de claude a los **87 s**, muy por
  debajo de cualquier techo configurado. Sugiere un árbol de procesos muriendo
  por otra causa y reportándose como timeout.
