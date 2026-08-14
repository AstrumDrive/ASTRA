# ASTRA 2.0 — G2: inventario de motores de ASTRUM (2026-08-13)

Autorización: Nelson autorizó explícitamente contactar ASTRUM para el
inventario.

Operación **de solo lectura**: se consultó el catálogo de motores y la
configuración del oráculo formal. No se envió ningún trabajo, no se modificó
estado remoto y no se consumió cuota de modelos. Host, usuario, clave y
detalles de tailnet **no se registran aquí** por la regla de `remote/README.md`.

## Motores disponibles

Consultado con `~/astra-worker/astra_engine.sh list`, que es la vía correcta:
`command -v sage` / `which cadabra2` **no los encuentran** aunque estén
instalados, porque viven en entornos conda y toolchains de elan.

| Motor | Contenido |
|---|---|
| `oracle` | numérico/simbólico general + GPU (sympy, z3, qutip, torch, cupy, jax) |
| `sci` | materia condensada / DFT (ase, pyscf, gpaw, pymatgen, kwant, spglib) |
| `sage` | SageMath 10.7 — simbólico pesado, `sage.manifolds` para GR |
| `cadabra` | álgebra tensorial de campos (ficheros `.cdb`) |
| `cadabra-py` | cadabra2 vía API de Python |
| `maxima` | CAS clásico |
| `lean` | verificación formal contra mathlib4 (**solo lectura, sin lake**) |
| `pkgs` | paquetes propios: GR_python+grthermo, pyWarpFactory, TELAR, warp_nn, natario, metric-engine, protoespacio, QuantumTransportEOM, mobius_rsoc, rectification |

GPU presente: NVIDIA RTX 3080, 10240 MiB.

## Equivalencia formal local ↔ ASTRUM: verificada

`docs/LEAN4_MATHLIB_WORKFLOW.md` (producción) **afirma** que ambos oráculos
usan el mismo pin. Comprobado directamente:

| | Local (WSL Debian) | ASTRUM |
|---|---|---|
| Toolchain | `leanprover/lean4:v4.30.0` | `leanprover/lean4:v4.30.0` |
| Commit de Mathlib | `c5ea00351c28e24afc9f0f84379aa41082b1188f` | `c5ea00351c28e24afc9f0f84379aa41082b1188f` |
| Mathlib compilado | sí | sí (`.lake/build/lib/lean` presente) |

Es decir, un artefacto formal verificado en un lado es reproducible en el
otro **con el mismo kernel y la misma biblioteca**, que es la condición para
que un acuerdo entre oráculos signifique algo.

## Diferencia real que conviene no olvidar

La ruta remota **no usa `lake`**: `lean_verify.sh` arma `LEAN_PATH` contra el
Mathlib ya compilado y llama a `lean` directamente. Consecuencia práctica:

- un artefacto que solo hace `import Mathlib` y prueba teoremas funciona en
  **ambos** oráculos;
- un artefacto que necesite `lake` (resolver o construir dependencias nuevas)
  funciona **solo en local**.

No es un defecto —evita compilaciones caras en el clúster— pero significa que
los dos oráculos formales **no son intercambiables para todo**, y una campaña
que planifique evidencia formal debe elegir la ruta a conciencia.

## Estado de G2 tras esto

| Ítem | Estado |
|---|---|
| Doctor/preflight local | PASS (2026-08-13) |
| Motores locales pasan sus smokes | PASS 6/6 (2026-08-13) |
| **Inventario de motores de ASTRUM** | **REGISTRADO (este documento)** |
| Acuerdo de veredictos entre oráculos (suite cliente) | pendiente — ejecuta trabajos reales en ambos oráculos |
| Atribución del scheduler, concurrencia, timeouts, cancelación | pendiente |

Los dos pendientes ya no son de inventario: **envían trabajo real al
clúster**, así que requieren una autorización distinta de la de hoy.
