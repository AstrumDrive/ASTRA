# ASTRA Agent Notes

## Shared project memory

Before operating ASTRA for a project, read
`C:\Users\Nelson\Dev\PROJECT_MEMORY.md` and resolve the target project or
`WDR-###` key with `project-memory\scripts\project_memory.py query`. After a
verified research or engineering work unit, record a concise event with
`project_memory.py record`, including reproducible evidence and next actions.
Never store credentials, model reasoning, or unsupported scientific claims.
Jira mutations require Nelson's explicit instruction.

## Cross-platform collaborator onboarding

On macOS, read `docs/onboarding/ASTRA_MACOS_INSTALL_EN.md` before installing or
operating ASTRA. Antigravity can be the user-facing instructor through the ASTRA
MCP server, but the internal production cycle still requires authenticated
`codex`, `claude`, and `agy` CLIs. Never copy another user's CLI tokens, `.env`,
Tailscale state, or SSH private key. Each collaborator receives an individually
authorized public key.

Use `scripts/astra_doctor.py --remote` for a non-model installation audit. On
macOS, use `remote/check_remote_oracle.sh` after executor/oracle changes.

## Al redactar artículos: `PUBLICATION_POLICY.md` (congelada 2026-07-31)

Obligatoria antes de escribir cualquier manuscrito con resultados de ASTRA. En
resumen: **las auditorías internas no se citan en artículos** (nada de identificadores
de ciclo, ni VALIDATED/REFUTED/WEAK_PASS, ni "ASTRA validó que…"), y todo manuscrito
lleva el **código extraído como artefacto independiente** que el referee pueda correr
sin ASTRA y que reproduzca las cifras del texto. Los volcados de auditoría solo van en
informes de empresa, y solo si Nelson lo pide explícitamente.

## Motores de cálculo en el clúster: NO uses el PATH para descubrirlos

`command -v sage` / `which cadabra2` / `which lean` devuelven **NADA** aunque los
tres estén instalados en Astrum. Viven en envs de conda y toolchains de elan. Para
saber qué hay: `~/astra-worker/astra_engine.sh list`. Para usar:
`astra_engine.sh <sage|cadabra|oracle|lean|sci|maxima|pkgs> <fichero>`.
Instrucción completa para pegar a otro agente:
`docs/onboarding/ASTRA_MACOS_INSTALL_EN.md` y el comando del clúster
`~/astra-worker/astra_engine.sh list`.

GPU: desde el 2026-10-01 CuPy funciona en `oracle` y `pkgs` (antes
`cupy.linalg` fallaba por `libcusolver`; el arreglo es un `.pth` que precarga
los wheels `nvidia-*`). Un validador que use `cupy` o `torch` declara
`gpu_slots` al enviarlo por `astra_cluster_submit`. Medidas y la regla de
validar contra CPU los códigos con truncación por energía, en la sección "GPU"
de `C:\Users\Nelson\Dev\REMOTE_CLUSTER_GUIDE.md`.

## Motores locales para pre-pruebas: sí existen (Debian WSL)

Para corridas cortas locales, ASTRA enruta Sage, Maxima y Cadabra por
`wsl -d Debian` (ver `core/engine_router.py::available_cas`); Debian WSL ya los
trae instalados (Maxima 5.44, SageMath 9.2, Cadabra2 2.3.6). `astra_doctor.py`
los reporta PASS desde una shell normal. Ubuntu WSL NO los tiene: no cambies
`ASTRA_WSL_DISTRO`.

## Desde una sesión con permisos restringidos (sandbox), usa el MCP, no el CLI

Si operas ASTRA desde un contexto sandboxed (p.ej. la extensión de Codex
ejecutando comandos bajo su token restringido), **invoca ASTRA por su servidor
MCP** (`astra_cycle`, `astra_execute`, ...), NO corras `astra_tool.py` como
comando dentro del sandbox. El token restringido no puede crear temporales en
`workspace/cli_tmp` ni alcanzar WSL (`Wsl/Service/E_ACCESSDENIED`), aunque el
ACL y `os.access` digan que sí. El servidor MCP corre fuera del sandbox y no
tiene esa limitación. Síntoma si lo ignoras: `call_cli` corta con un error
explícito de permisos (antes: cuelgue de minutos), y el doctor marca
`wsl_bridge: DENIED in this context`. Escape puntual: `ASTRA_CLI_TEMP_ROOT` a un
directorio escribible por ese token.

Verificado el 2026-09-25 con Codex 0.153: `wsl -d Debian -- sage ...` bajo
`--sandbox workspace-write` devuelve `Wsl/Service/E_ACCESSDENIED`; el mismo
comando bajo `--sandbox danger-full-access` llega a Sage. Codex Desktop fija la
política por hilo (esa sesión corría `workspace-write` aunque `config.toml`
diga `sandbox_mode = "danger-full-access"`), así que desde la app o usas las
tools MCP (`astra_execute` con `# ASTRA_ENGINE: sage|cadabra|maxima`) o pones
el hilo en acceso completo. Sage, Maxima y Cadabra por MCP: probado el mismo
día (`factor(2^64-1)` por Sage, `VERDICT: PASS`).

Dos lecturas erróneas vistas en Codex Desktop el 2026-09-26, para no repetirlas:

- Si TODAS las tools `astra_*` fallan en milisegundos con `Transport closed`,
  el servidor MCP de ESTE hilo murió y Codex Desktop no lo relanza dentro del
  hilo (en el mismo hilo habían funcionado 35 llamadas seguidas). No concluyas
  que ASTRUM es inalcanzable ni que ASTRA está rota: pide al usuario abrir un
  hilo nuevo (o reiniciar la app), que arranca un servidor fresco. El servidor
  se verifica desde fuera con `venv/Scripts/python.exe scripts/astra_doctor.py`.
- Si `ssh astrum ...` devuelve literalmente `off` y `exit /b 1`, no es que el
  alias esté incompleto: el hilo corre con la red apagada
  (`network_access: false`) y lo que respondió no fue el ssh real (el real, con
  `-o BatchMode=yes`, devuelve el inventario de motores). `astra_status` por
  MCP hace ese mismo ssh desde fuera del sandbox y es la comprobación válida
  de acceso a ASTRUM.

Before changing the remote oracle path, read:

- `remote/README.md`

Do not print or commit secrets. `.env` may contain API keys and remote oracle
settings. Machine-specific credentials and private keys always live outside
this repository.

Use the remote check script after touching executor/oracle code:

```powershell
.\remote\check_remote_oracle.ps1
```

## Dos reglas para pedir un ciclo desde un agente (medidas el 2026-10-01)

Valen para `astra_cycle` llamado desde Claude Code, Codex o Antigravity. Sobre
claims de investigación real, pasar de ignorarlas a cumplirlas llevó la tasa
de acierto de 20/27 a 47/50 sin un veredicto falso
(`docs/evidence/RESEARCH_CLAIMS_COMPARISON_20260930.md`, secciones 5 y 6).

1. **Una proposición por ciclo.** Un ciclo decide UNA afirmación decidible.
   Si el claim tiene varias partes ("rho vale X, p_r = -rho y el flujo es
   cero"), son tres ciclos. Un claim con varias partes produce un validador
   que prueba una y un analista que, con razón, devuelve INCONCLUSIVE para
   el resto.
2. **Las definiciones van dentro de `intuition`.** Todo lo que el validador
   necesita para construir los objetos tiene que estar escrito en el texto:
   convenciones (orden de modos de Jordan-Wigner, orden de los productos de
   operadores, signatura y componentes de la métrica, observador, unidades,
   generadores como matrices explícitas, rangos de los parámetros). Nada de
   "ver el repo" o "como en el paper": el autor del validador solo ve el
   texto del ciclo. Desde el 2026-10-01 ese texto llega íntegro al autor
   (`build_translation_input`), pero solo si está ahí.

Forma recomendada de la llamada:

- `objective`: una frase, "Determine whether P", con P la proposición.
- `intuition`: las definiciones completas, luego "Claim: P" y cómo decidirlo
  ("exact 32 x 32 matrices", "symbolic Einstein tensor for generic b(t,x)").
- `exec_timeout`: solo si el cálculo es pesado (tensores simbólicos,
  diagonalizaciones): 600-900 s; el ciclo amplía su presupuesto solo.
- `timeout`: déjalo en su defecto (1500 s). Un ciclo de producción gasta
  100-400 s por ronda de revisión y puede dar tres; con 900 s el ciclo
  muere en PARTIAL antes de ejecutar nada (visto el 2026-10-02). Si hace
  falta más, `astra_cycle_submit` y `astra_job`, no un `timeout` mayor que
  el muro del cliente (1800 s en Codex).
- Leer SIEMPRE `original_claim_verdict` junto a `status`: `status` habla de la
  conjetura que se probó; `original_claim_verdict` (SUPPORTED, REFUTED,
  INCONCLUSIVE, SUBSTITUTED) habla de P. Un `VALIDATED` con
  `original_claim_verdict = REFUTED` significa que P es falsa.

Ejemplo bueno: objective "Determine whether [B_1,H_J] = -i J C_1 for both spin
components in the model defined below"; intuition con el modelo (impureza
S = sigma/2, cuatro modos JW en orden 0up 0dn 1up 1dn, H_J = J sum_a S^a
s_0^a, B y C con el orden de producto escrito, métrica de temperatura
infinita) y "Claim: ... Decide by building every operator as an explicit
32 x 32 matrix". Ejemplo malo: "verifica las identidades del bloque de
intercambio de Kondo" (varias proposiciones, cero definiciones).
