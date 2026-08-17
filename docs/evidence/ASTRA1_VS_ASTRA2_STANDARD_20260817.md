# 1.0 contra 2.0, tier standard: cambia el TIPO de error, no la tasa de acierto

Primera medición pareada de las dos líneas sobre el mismo benchmark.

- **1.0**: `quality_20260817_024630.json` (checkout de producción, 17-ago, 2 h 30 min)
- **2.0**: `quality_20260813_022505.json` (13-ago)
- Ambas: tier standard, 43 registros, 23 casos científicos, 14 de auditoría,
  6 de ejecución, oráculo local, `--jobs 2`.

## Cifras

| | **ASTRA 1.0** | **ASTRA 2.0** |
|---|---|---|
| casos científicos | 23 | 23 |
| **aceptación falsa** | **0.4167** | **0.0** |
| rechazo falso | 0.0 | 0.0 |
| exactitud estricta | 0.5217 | 0.6957 |
| IC 95 % | [0.330, 0.708] | [0.491, 0.844] |
| exactitud balanceada | 0.5303 | 0.6894 |
| tasa de fallo operativo | 0.2609 | 0.2609 |
| auditoría: recall de defectos críticos | 1.0 | 1.0 |
| auditoría: recall de etiquetas | 0.8333 | 0.9167 |
| **auditoría: falsa alarma en validadores sanos** | **0.3333** | **0.0** |
| ejecución: exactitud de veredicto | 1.0 | 1.0 |
| latencia p50 / p95 | 187 s / 676 s | 327 s / 946 s |

## El hallazgo no es la exactitud, es la naturaleza del error

Los errores de cada línea, sobre los mismos 23 casos:

```text
1.0  →  11/23 mal:  VALIDATED 5   API_ERROR 5   CODE_ERROR 1
2.0  →   7/23 mal:  TIMEOUT 4     API_ERROR 2   INCONCLUSIVE 1
```

**1.0 falla afirmando falsedades. 2.0 falla quedándose sin tiempo.**

Los cinco `VALIDATED` de 1.0 son claims **falsos** aceptados como válidos:

| caso | 1.0 | 2.0 |
|---|---|---|
| `fluids_reynolds_density_squared_false` | VALIDATED | REFUTED |
| `gr_spherical_minkowski_zero_connection_false` | VALIDATED | REFUTED |
| `logic_sqrt_square_all_reals_false` | VALIDATED | REFUTED |
| `quantum_nonunitary_trace_preservation_false` | VALIDATED | REFUTED |
| `symbolic_log_derivative_false` | VALIDATED | REFUTED |

Los cinco son la firma del defecto de re-anclaje encontrado el 12-ago:
producción **detecta bien la falsedad**, forma una conjetura corregida, la valida
y reporta el estado de *su* conjetura en vez del claim del usuario. Cada paso es
correcto; la respuesta es a otra pregunta. 2.0 lo arregló con
`original_claim_verdict`; producción sigue sin ese eje.

## Qué se sostiene estadísticamente y qué no

Con 23 casos pareados:

- **Exactitud global: la diferencia NO es significativa.** McNemar exacto sobre
  discordantes (5 a favor de 1.0, 9 a favor de 2.0): **p = 0.42**. Los IC del
  95 % se solapan ampliamente. *No se puede afirmar que 2.0 acierte más.*
- **Aceptación falsa: 5 de 12 claims falsos contra 0 de 12.** Los cinco
  discordantes van todos en la misma dirección; McNemar exacto **p = 0.0625**.
  Sugerente y por debajo del umbral convencional por poco: con doce claims
  falsos y cinco discordantes, ése es el p mínimo que este diseño puede dar.
- **Falsa alarma de auditoría** (1/3 contra 0/3): n demasiado pequeño para
  contrastar. Salvedad adicional: el fichero de casos de auditoría **difiere
  entre checkouts** por una corrección de fixture, así que esa fila no es
  estrictamente pareada. Las 23 pistas científicas sí lo son (verificado:
  idénticas salvo finales de línea).

## El coste

2.0 tarda **1.75×** por caso (p50 327 s contra 187 s). Es el precio de más
revisión y más reparación, y se ve en sus errores: **4 de los 7 son TIMEOUT**,
que es presupuesto, no epistemología.

Ese intercambio conviene nombrarlo como es: **1.0 es más rápido y afirma cosas
falsas; 2.0 es más lento y se queda callado cuando no puede decidir.** Un timeout
se arregla con presupuesto. Una aceptación falsa se arregla releyendo el paper
después de haberlo enviado.

## Alcance

1. Mide **solo el ciclo atómico**. La capa de campaña de 2.0 no se ejercita aquí
   y 1.0 no la tiene: en ese eje no hay comparación, hay ausencia.
2. Una sola corrida por línea. Las tasas de fallo operativo coinciden
   (0.2609 ambas), lo que sugiere condiciones comparables, pero no hay
   repeticiones que lo confirmen.
3. La medición de 1.0 se hizo con el checkout de producción **de hoy**, que ya
   incluye los dos arreglos portados el 13-ago (Unicode y candado de máquina).
   No es la producción de julio.
