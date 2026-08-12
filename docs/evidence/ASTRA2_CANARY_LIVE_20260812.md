# ASTRA 2.0 — evidencia del canary VIVO de campaña (2026-08-12)

Autorización: "go" explícito de Nelson ("sigamos") tras presentarle los topes
congelados. Protocolo: `docs/benchmarks/ASTRA2_CANARY_PREREGISTRATION_V1.md`
(huella `9a25c214a5d2b38d1e8f615518ce9d2f46213b08ae193c1cd1ad7792c321bd92`,
verificada por el runner antes de arrancar).

Comando ejecutado (mapa de roles de producción suministrado por entorno,
oráculo local, repair vNext.1, ensemble codex+agy en conjetura, caché
apagada):

```powershell
scripts\run_campaign_canary.py --live --yes
```

Fuentes de todas las cifras (depositadas, ignoradas por Git):

- `workspace/campaign_canary_runs/live_canary_cmp_cd11be51fcd34e22.json`
- `workspace/campaigns/cmp_cd11be51fcd34e22/` (ledger de 22 eventos +
  checkpoint + artefactos)

## Veredicto del endpoint primario (operabilidad): **PASS**

| Criterio pre-registrado | Resultado |
|---|---|
| ≥1 episodio con evidencia transcrita | **2 episodios**, 2 records de Evidence (`SYMBOLIC`/`SCOPED`/`SUPPORTS`) con `validator.py` archivado y hash SHA-256 verificado contra disco |
| Ledger reproduce limpio y el checkpoint valida | replay `HEALTHY`, 22 eventos, checkpoint anclado en la secuencia 22 y validado contra el prefijo |
| Decisión determinista por episodio | `SELECT` (R0-initial-selection) → `CONTINUE` (R7-continue) → `CLOSE` (R2-campaign-exhausted) |
| Ningún gasto supera los topes | 2/3 ciclos, 17/36 llamadas de modelo, 2384/3600 s de pared, 3 s de ejecución; cierre limpio por política (la pared restante, 1216 s, ya no cubría el plan de 1800 s del siguiente episodio) |

El lazo completo corrió con modelos reales de punta a punta — arranque,
selección de rama bootstrap, dos ciclos atómicos (conjetura ensemble →
crítica cruzada → síntesis → traducción → revisión independiente → oráculo
local → auditoría), transcripción a eventos, y **cierre autónomo por regla
determinista de presupuesto**, no por intervención humana ni por error.
Duración por episodio: 1774 s y 609 s de pared de modelo.

Conforme al pre-registro §1: este PASS demuestra operabilidad, **no** mejora
científica comparativa.

## Hallazgos de integración (valor del canary) y correcciones

1. **Portafolio emitido pero perdido en la frontera**: la síntesis SÍ produjo
   el bloque `astra-portfolio` en el ciclo vivo, pero la validación lo
   rechazó completo por una entrada vacía en `quantifiers`
   (`portfolio_error: "quantifiers must not contain empty entries"`, visible
   en el checkpoint del ciclo). El fail-soft protegió el ciclo como estaba
   diseñado. Corrección: las listas del portafolio filtran entradas vacías
   en la frontera (la capa estricta de records no cambia) + instrucción
   explícita al modelo; test de regresión
   `test_empty_list_entries_are_filtered_not_fatal`.
2. **Forma real del resultado del ciclo**: `_do_cycle` guarda la salida del
   oráculo bajo `execution` (no `execution_result`), los modelos reales bajo
   `cli_models` y la ruta de oráculo bajo `oracle_used`. Por eso el canary
   archivó `validator.py` pero no `stdout.txt`. Corrección: el ejecutor
   acepta ambas formas y mapea `cli_models`/`oracle_used`; test de regresión
   `test_real_cycle_result_shape_is_transcribed`.

Ambas correcciones aterrizaron DESPUÉS del run vivo; la suite completa quedó
en `301 passed, 6 skipped, 28 subtests`. Una re-verificación viva de 1 ciclo
(~10–30 min de cuota) confirmaría el flujo del portafolio en caliente; es
opcional y queda a decisión de Nelson.

## Interpretación

- G4 sigue abierto: el canary habilita el pilot comparativo (H3), no lo
  sustituye. H1 (gate de aceptación falsa) y el pilot tienen presupuestos
  propios pendientes de decisión.
- Nada de este documento constituye resultado científico ni se cita en
  manuscritos (`PUBLICATION_POLICY.md`).
