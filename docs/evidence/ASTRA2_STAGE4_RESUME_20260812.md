# ASTRA 2.0 — evidencia de la etapa 4: resume explícito de campaña

Fecha: 2026-08-12

Autorización: Nelson autorizó las etapas restantes una a una ("vamos con
todas las etapas una a una").

Base: commit `c0c664d`; el código de esta etapa entra en el mismo commit que
introduce este documento.

## Alcance implementado

`core/campaign_resume.py` (nuevo, puro): `resume_campaign(store)` reconstruye
el estado de trabajo tras cualquier interrupción **sin repetir episodios**
(están en el ledger, que sigue siendo la única autoridad):

- el checkpoint es un acelerador validado, nunca autoridad: si está obsoleto,
  ausente o corrupto, el resume cae a replay completo y **republica** el
  checkpoint atómicamente (`STALE_REBUILT` / `MISSING_REBUILT` /
  `INVALID_REBUILT` en el informe);
- una cola truncada del ledger **bloquea la reanudación**
  (`repair_truncated_tail`) hasta archivarla explícitamente, exponiendo el
  prefijo válido para inspección — semántica del contrato del primer corte;
- corrupción anterior a la última línea propaga fail-closed sin tocar nada;
- recomendación determinista de la siguiente acción: `empty` /
  `activate_campaign` / `select_initial_branch` / `campaign_step` /
  `await_human_review` / `terminal`;
- `rebuild_checkpoint=False` da un resume estrictamente de solo lectura (sin
  lock de escritor), utilizable mientras otro proceso mantiene la campaña
  abierta — probado con un segundo store lector.

Tests: `tests/test_campaign_resume.py` (9 tests, runner falso, sin modelos).
El test de no-repetición encadena dos `campaign_step` con un resume en medio
y verifica que el conteo de episodios avanza 1 → 2 sin duplicados.

## Comandos y resultados

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_campaign_resume.py -q
# 9 passed in 0.83s

.\venv\Scripts\python.exe -m pytest -q
# 287 passed, 6 skipped, 28 subtests passed in 14.49s
```

Entorno sin cambios: Python `3.12.10`, `pip freeze` SHA-256
`59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5`.
