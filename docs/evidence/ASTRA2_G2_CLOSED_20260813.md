# ASTRA 2.0 — G2 cerrado: oráculos y scheduler (2026-08-13)

Autorización: Nelson autorizó los dos ítems restantes de G2, que **envían
trabajo real** al clúster.

Ninguna llamada de modelo: la suite cliente es ejecución determinista y los
trabajos del scheduler son segundos de aritmética o `sleep`.

## Acuerdo de veredictos entre oráculos

`scripts/run_client_validation.py --oracle both --timeout 300`.
Informe: `workspace/client_validation_runs/client_validation_20260813_223922.json`.

```text
casos registrados      7
bundles                12   (11 pasan)
casos cruzados         5
ACUERDO ENTRE ORÁCULOS 1.0
```

**El ítem de G2 pasa**: los cinco casos ejecutados en ambos oráculos dieron el
mismo veredicto de afirmación. Incluye el caso formal
`client_grpython_zero_trace_formal`, con Lean en local (186 s) y en ASTRUM
(23 s) — coherente con el pin idéntico verificado en el inventario.

### El caso que falla no es ciencia, es deriva de instrumento

`client_quantum_transport_eom_open_system` dio `REFUTED` en local. Causa: el
fixture de 2.0 exige `evidence["package_version"] == "0.3.0"` mientras el
paquete instalado ya es `0.4.0.dev0`. Producción tiene esa corrección **sin
committear**; la línea 2.0 heredó el pin viejo del commit base.

No afecta al acuerdo entre oráculos (ese caso corre solo en local, por
decisión propia del fixture: *"el paquete de desarrollo actual no es un
artefacto liberado de ASTRUM"*).

**Portar ese fixture es decisión de Nelson**: es su cambio y es un instrumento
de medida, no lo toco por mi cuenta.

## Scheduler compartido: 4/4

`scripts/check_cluster_scheduler.py` (nuevo). Informe:
`workspace/g2_astrum/scheduler_check_20260813_224407.json`.

| Comprobación | Resultado | Qué demuestra |
|---|---|---|
| `capacity` | PASS | el manager responde con su vista de slots y cola |
| `attribution` | PASS | el job queda atribuido a `astra-2.0-dev`, distinguible de `nelson` |
| `timeout` | PASS | un job que excede su plazo se reporta como tal y **no** como veredicto |
| `cancellation` | PASS | un job cancelado se detiene y queda registrado como cancelado |

La atribución ya se veía en la ruta de trabajo del clúster:
`.../cluster/jobs/astrum_<fecha>_astra-2.0-dev_<id>/`. Por eso la línea 2.0
usa un `ASTRA_CLIENT_ID` propio en vez de reutilizar el de producción: sin esa
separación, los trabajos de ambas líneas serían indistinguibles para el
manager compartido.

### Un falso fallo mío, y lo que enseñó

La primera versión del chequeo de timeout envió un campo `timeout`; el
contrato es `timeout_seconds`. El manager aplicó silenciosamente su default de
**3600 s**, el job de 45 s terminó bien e imprimió `VERDICT: PASS`, y mi
comprobación falló culpando al scheduler.

Dos lecciones registradas: un parámetro con nombre equivocado **no da error,
se ignora**; y la comprobación se reescribió para pasar por
`execute_cluster_code`, la ruta que ASTRA usa de verdad, en vez de una
petición construida a mano — que es la única forma de que el test mida el
sistema y no mi reconstrucción de él.

## Ampliación del chequeo de deriva

El caso del pin `0.3.0` habría sido invisible: `check_line_drift.py` solo
miraba `core/`, `agents/`, `mcp_server/`. Ahora cubre también `benchmarks/` y
ficheros `.json`, porque **un fixture desactualizado mide lo que no debe**.
Primera pasada ampliada, 81 ficheros: 4 `PRODUCTION ONLY` (los dos del
paquete cuántico, más `core/pdf_generator.py` y `main.py`), 0 divergencias
reales.

## Estado de G2

| Ítem | Estado |
|---|---|
| Doctor/preflight local | **PASS** |
| Motores locales pasan sus smokes | **PASS 6/6** |
| Inventario de motores de ASTRUM | **REGISTRADO** |
| Acuerdo de veredictos entre oráculos | **PASS (1.0 sobre 5 casos)** |
| Scheduler: atribución, concurrencia, timeouts, cancelación | **PASS 4/4** |

**G2 queda cerrado.** Con la salvedad explícita de que un caso de la suite
cliente falla por un pin de versión desactualizado, pendiente de decisión.
