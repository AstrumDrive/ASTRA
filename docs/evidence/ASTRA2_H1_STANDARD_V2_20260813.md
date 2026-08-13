# ASTRA 2.0 — re-medición del gate H1 tras los tres cambios (2026-08-13)

Autorización: Nelson autorizó las tres acciones (port del arreglo Unicode a
producción, corrección del fixture EinsteinPy, re-medición completa).

Runs comparados, ambos tier standard / 43 casos / oráculo local / config
íntegra de producción:

- antes: `quality_20260812_214125.json`
- después: `quality_20260813_022505.json`

## Comparación

| Métrica | Antes | Después |
|---|---|---|
| **Aceptación falsa** | **0.0** | **0.0** |
| **Rechazo falso** | **0.0** | **0.0** |
| Auditoría: falsa alarma en validadores sanos | 0.3333 | **0.0** |
| Auditoría: recall de defectos / críticos | 1.0 | 1.0 |
| Ejecución: exactitud de veredicto | 1.0 | 1.0 |
| Exactitud estricta | 0.7391 | 0.6957 |
| Fallo operativo | 0.1739 | 0.2609 |

## Qué SÍ queda establecido

1. **La compuerta aguanta.** Aceptación falsa 0.0 en dos corridas
   independientes de 23 casos, con la calibración del revisor activa. La
   distinción decisiva/auxiliar no abrió ninguna puerta trasera.
2. **El fixture corregido mide lo que debía**: `audit_regression_einsteinpy_list_symbols_supported`
   pasó a **APPROVED en 10.5 s** (antes REVISE), y la falsa alarma sobre
   validadores sanos cayó a **0.0** sin perder recall de defectos.

## Qué NO queda establecido (y no debe afirmarse)

**El cambio en fallo operativo (0.174 → 0.261) no es atribuible.** Con
n=1 por caso, la misma suite muestra variaciones de hasta 2× en duración
sobre casos idénticos (`quality_fluids_poiseuille` 560→948 s;
`gr_spherical_minkowski` 534→928 s; `gr_schwarzschild_ricci_scalar`
817→472 s). Los intervalos de confianza del 95% sobre 4/23 y 6/23 se solapan
ampliamente. **No hay señal**: ni mejora ni empeoramiento demostrable.
Resolverlo exige repeticiones (`--repeats 3`, triple coste).

Del mismo modo, `symbolic_polynomial_factorization_sage` convirtió a
VALIDATED en la prueba aislada y volvió a fallar aquí: es la misma varianza,
no una regresión.

## Hallazgo nuevo y concreto: el cuello es el TRADUCTOR, no el revisor

Este sí es atribuible, porque sale de las trazas de fase y no de la
comparación ruidosa. Los cuatro TIMEOUT mueren en traducción o en el parche
acotado, nunca en revisión:

| Caso | Fase fatal | Segundos |
|---|---|---|
| `quality_gr_schwarzschild_ricci_nonzero_false` | `translate` | 481.6 |
| `lean_nat_add_comm` | `translate_patch` | 241.6 |
| `quantum_density_trace_preserved` | `translate_patch` | 240.6 |
| `fluids_hagen_poiseuille_scaling` | `translate_patch` | 481.1 |

Los números delatan la causa: **240 s es el techo por llamada**
(`ASTRA_CLI_TIMEOUT`, default de `_configured_phase_timeout` para *toda*
fase), y ~480 s es ese techo dos veces, una por modelo de la escalera
`claude-opus-4-8,sonnet`. El propio código lo advierte en
`astra_tool.py:1155`: *"el TRADUCTOR genera scripts de fisica largos
(ASTRA_TRANSLATOR_TIMEOUT=480)"* — pero **`.env.example` nunca define esa
variable**, así que producción también corre el traductor con 240 s.

Además, las dos no-aprobaciones restantes muestran la calibración
**parcialmente** aplicada: el revisor ya nombra explícitamente las piernas
como no decisivas — *"all sampling/factorization legs are non-decisive"*,
*"the three scientific legs are otherwise sound and independently
decisive"* — y aun así bloquea. Articula la distinción sin actuar sobre ella.

## Recomendación

Antes de gastar otra suite completa: **prueba dirigida de
`ASTRA_TRANSLATOR_TIMEOUT=480` sobre los 4–6 casos que fallan** (~30–60 min).
Es la hipótesis más barata y mejor sustentada, la recomienda el propio código,
y afecta igual a producción. Solo si convierte, tiene sentido re-medir la
suite entera con repeticiones.

Ninguna cifra de este documento es evidencia científica publicable
(`PUBLICATION_POLICY.md`).
