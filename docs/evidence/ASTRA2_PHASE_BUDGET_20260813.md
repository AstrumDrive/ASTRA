# ASTRA 2.0 — distribución real de tiempo por fase (2026-08-13)

Autorización: Nelson pidió extraer la distribución sin gastar cuota.

Fuente: `scripts/analyze_phase_budget.py` releyendo los informes ya
depositados en `workspace/quality_benchmark_runs/`. **Cero llamadas de
modelo**: solo re-lee logs ya pagados.

Muestra: **84 ciclos** con trazas de fase, 9 corridas, 23 casos.
61 completos, 23 incompletos.

## Tratamiento de datos censurados

Una fase que se detuvo en su techo no cuesta ese tiempo: necesitaba **al
menos** ese tiempo. Esas observaciones se cuentan aparte y se excluyen de los
percentiles; si no, el techo se auto-confirmaría como "el coste real".

## Coste por fase (solo observaciones no censuradas)

| Fase | n | p50 | p90 | máx | censuradas |
|---|---:|---:|---:|---:|---:|
| `translate` | 79 | 157 s | 431 s | 703 s | 5 |
| `translate_patch` | 44 | 117 s | 343 s | 454 s | **20** |
| `conjecture` | 82 | 130 s | 197 s | 401 s | 2 |
| `review` | 80 | 89 s | 169 s | 352 s | 2 |
| `analyze` | 61 | 18 s | 40 s | 126 s | 0 |
| `navigate` | 57 | 26 s | 34 s | 45 s | 0 |
| `execute` | 61 | 2 s | 6 s | 19 s | 0 |

Ciclos completos de punta a punta: **p50 533 s, p90 921 s, p95 994 s**.

Dónde mueren los 23 incompletos: `translate` 15, `translate_patch` 6,
`conjecture` 2. **Ninguno en revisión, análisis ni ejecución.**

## Conclusión 1: el presupuesto total NO es el problema

Con 1440 s útiles y un p90 de ciclo completo de 921 s, hay **+519 s de
holgura**. Subir el presupuesto total, que era la opción 1 que yo mismo
propuse, **no está respaldado por los datos**: los ciclos que terminan caben
de sobra.

## Conclusión 2: el problema es la ESCALERA de modelos, no los techos

Sumando el p90 de cada fase: 431 + 343 + 197 + 169 + 40 + 34 + 6 = **1220 s**,
que cabe en 1440 s. Es decir, **el presupuesto actual admite el p90 de todas
las fases a la vez, siempre que cada una se ejecute UNA vez.**

Lo que no admite es un reintento. Con `ASTRA_TRANSLATOR_MODELS=claude-opus-4-8,sonnet`,
una traducción que agota su techo reintenta con el segundo modelo y **duplica**
el coste de la fase. La evidencia es directa: en las corridas con techo de
240 s se midieron traducciones de 448, 463 y 481 s — exactamente 240 × 2. Con
el techo en 480 s, un reintento consume **960 s**, más que el ciclo completo
en su p90 (921 s), y deja 480 s para conjetura + revisión + reparación +
auditoría, que en p90 necesitan 775 s. **Un reintento del traductor garantiza
el fallo del ciclo.**

## Conclusión 3: el techo de 240 s estaba mal calibrado para la reparación

`translate_patch` tiene **20 observaciones censuradas de 64** (31%): su p90
real es 343 s contra un techo por defecto de 240 s. La reparación acotada era
la fase más estrangulada de todo el pipeline, y no se veía porque su fallo se
presentaba como "el ciclo se quedó sin tiempo".

## Reparto propuesto por datos (no adoptado)

| Fase | Techo propuesto | Base |
|---|---:|---|
| `conjecture` | 240 s | p90 197 s |
| `translate` | 480 s | p90 431 s |
| `review` | 240 s | p90 169 s |
| `translate_patch` | 360 s | p90 343 s |
| resto (analyze/navigate/execute) | 120 s | p90 80 s |
| **suma** | **1440 s** | = presupuesto útil actual |

El reparto encaja exactamente en el presupuesto vigente **si ninguna fase se
duplica**. Por tanto la palanca real es la escalera, y hay tres formas de
tratarla, **ninguna adoptada**:

1. dividir el techo de la fase entre el número de modelos de su escalera, de
   modo que el coste total de la fase (incluidos reintentos) respete su
   asignación;
2. dejar el traductor con un solo modelo y usar la escalera solo como
   fallback ante error, no ante timeout;
3. hacer que el reintento herede el presupuesto restante real en vez de un
   techo fijo.

La opción 1 es la más simple y la más fiel a lo medido; la 3 es la más
correcta si se quiere conservar la escalera. Cualquiera exige tests y
autorización, porque toca `cli_backend`/`astra_tool` de producción.

## Nota de método

Esta es la primera recomendación de la sesión construida sobre 84
observaciones en vez de 1–3. Las tres anteriores (calibrar el revisor, subir
el techo del traductor, subir el presupuesto total) se apoyaban en muestras
que no distinguían señal de ruido, y dos de ellas resultaron equivocadas al
repetir la medición.

Ninguna cifra de este documento es evidencia científica publicable
(`PUBLICATION_POLICY.md`).
