# ASTRA Agent Notes

## ASTRA 2.0 development isolation

This checkout is the isolated ASTRA 2.0 development line. Read
`ASTRA2_ACCEPTANCE.md` before changing launchers, MCP registration, remote
deployment, release metadata, or Git remotes.

Until every mandatory gate is recorded as passed and Nelson gives explicit
approval:

- do not point the production MCP entry, desktop shortcut, service, or ASTRUM
  production worker at this directory;
- do not merge this branch into production or enable its disabled push URLs;
- do not copy `.env`, CLI tokens, private keys, Tailscale state, virtual
  environments, or runtime workspaces from the production checkout;
- tests and frozen benchmarks may execute from this checkout using a dedicated
  environment and explicitly supplied machine-local configuration.

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

Before changing the remote oracle path, read:

- `remote/README.md`

Do not print or commit secrets. `.env` may contain API keys and remote oracle
settings. Machine-specific credentials and private keys always live outside
this repository.

Use the remote check script after touching executor/oracle code:

```powershell
.\remote\check_remote_oracle.ps1
```
