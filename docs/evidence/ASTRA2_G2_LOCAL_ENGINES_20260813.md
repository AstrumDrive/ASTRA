# ASTRA 2.0 — G2: doctor y smoke tests de motores locales (2026-08-13)

Autorización: Nelson autorizó arrancar G2.

Sin cuota de modelos: todo es ejecución local.

## Configuración añadida

La línea 2.0 no tenía `.env`. Se creó uno **machine-local, ignorado por Git**,
con **solo configuración no secreta**: el mapa de roles de producción tomado de
`.env.example` y las rutas de motores tomadas de la configuración de
producción. **No se copió ninguna clave, token ni credencial**; las CLIs de
suscripción se autentican solas. Esto además evita el error que dejó
inconcluso el primer smoke de H1: haber corrido con los defaults de las CLIs
en vez de las escaleras de producción.

Rutas de motores (mismo stack Debian/WSL2 pineado que usa producción):

```text
ASTRA_WSL_DISTRO=Debian
ASTRA_LOCAL_LEAN4_WSL_ROOT=/home/nelson/astra-benchmarks/mathlib4-v4.30.0
ASTRA_LOCAL_LEAN4_WSL_LAKE_BIN=/home/nelson/.elan/bin/lake
ASTRA_REQUIRED_LOCAL_ENGINES=z3,sagemath,maxima,cadabra,lean4_local
```

## `scripts/astra_doctor.py`: PASS

Todas las comprobaciones requeridas verdes: paquetes Python científicos, las
tres CLIs de modelo en PATH, git/ssh/tailscale, y el contrato de arquitectura
("canonical production topology").

Dos lecturas que **no** deben malinterpretarse:

- `optional:maxima`, `optional:sage`, `optional:cadabra2` salen
  `OPTIONAL_MISSING`. El doctor busca **ejecutables nativos de Windows**;
  estos motores viven en WSL y **sí funcionan**, como demuestran los smokes de
  abajo. No es un fallo.
- `optional:lean` y `optional:lake` encuentran un **Lean 4.32.2 nativo de
  Windows** instalado por WinGet. Ese binario **no es el oráculo de ASTRA**:
  el pin es Lean 4.30.0 + Mathlib v4.30.0 bajo WSL. El README ya advierte que
  "tener un binario de Lean no relacionado no equivale a un entorno Mathlib
  listo para el kernel". La ruta que ASTRA resuelve es la correcta:
  `wsl -d Debian -- /home/nelson/.elan/bin/lake @ .../mathlib4-v4.30.0`.

## `scripts/run_engine_smokes.py`: 6/6

Ejecución real de un artefacto por motor **a través del router local de
ASTRA**, no descubrimiento. Cada artefacto está construido para que **una
respuesta incorrecta falle**, no solo un import roto.

| Motor | Resultado | Tiempo | Qué prueba |
|---|---|---:|---|
| `python` | PASS | 2.4 s | identidad simbólica con residual exacto (SymPy) |
| `z3` | PASS | 0.7 s | AM-GM sin contraejemplo (`unsat`) |
| `sage` | PASS | 9.3 s | factorización de `t^4-1` verificada por expansión |
| `maxima` | PASS | 1.2 s | integral definida contrastada contra su valor |
| `cadabra` | PASS | 3.2 s | contracción antisimétrico×simétrico canonicaliza a 0 |
| `lean4` | PASS | 153.1 s | teorema kernel-checked contra el Mathlib pineado, `#print axioms` limpio |

El artefacto de Lean lleva Unicode a propósito (`∀`, `ℝ`, `≤`): es exactamente
donde apareció el defecto de codificación de PowerShell, así que el smoke
conserva los símbolos que se habrían destruido. Su verificación no busca un
`VERDICT:` impreso —Lean no tiene ese protocolo— sino elaboración limpia más
un `#print axioms` que solo nombre los axiomas estándar y **sin `sorryAx`**.

## Trampa encontrada durante el trabajo

El marcador de motor debe ser exactamente `# ASTRA_ENGINE: <motor>`. Un
marcador con sintaxis de comentario de otro lenguaje (`/* ... */`) **no se
detecta y el artefacto se enruta silenciosamente a Python**, fallando con un
`SyntaxError` que no menciona el motor. Le pasó al primer artefacto de Maxima
de este mismo script. Anotado en el código para el siguiente que lo lea.

## Estado de G2 tras esto

| Ítem | Estado |
|---|---|
| Doctor/preflight local | **PASS** |
| Motores locales requeridos pasan sus smokes | **PASS (6/6)** |
| Inventario de motores de ASTRUM | pendiente — requiere contactar el clúster |
| Acuerdo de veredictos entre oráculos (suite cliente) | pendiente — requiere ASTRUM |
| Atribución del scheduler, concurrencia, timeouts, cancelación | pendiente |

Los tres pendientes necesitan tocar el clúster, lo que exige autorización
explícita por `HANDOFF.md` §9.

Informe depositado: `workspace/engine_smokes/engine_smoke_*.json`.
