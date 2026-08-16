# Historial del fingerprint del protocolo

El fingerprint existe para que el protocolo **no pueda cambiar en silencio**. Un
cambio legítimo deja rastro aquí; uno accidental rompe
`test_suite_fingerprint_is_deterministic` y se detiene.

| fingerprint | vigente desde | motivo |
|---|---|---|
| `ef119a1e27e51481483ef1166792bec9442a3147c2e5f5436e3918eb2e079054` | 2026-07-25 | congelado original (`frozen_before_live_execution`) |
| `b1ecae713747b867f3db36f59bd01d50a1fcb38a03b81b1cacebe62836bbca79` | 2026-08-15 | **enmienda A1**: `cycle_timeout_seconds` 1800 → 2400 s (y 2100 → 2700 en `warp_shape_pareto`, que conserva su ventaja de 300 s) |

## Enmienda A1 (2026-08-15)

Autorizada por Nelson el 2026-08-15, tras la primera corrida canary válida
(`docs/evidence/ASTRA2_ABLATION_RUN2_FINAL_20260815.md`, 19 ciclos sin
contaminación).

**Motivo.** Las medianas de fase suman 1424 s de los 1740 utilizables; una vez
pagadas ejecución, análisis y navegación (~270 s) quedan **menos de 50 s** de
margen, y **6 de 17 ciclos terminaron exactamente a los 1471 s**. La tasa de
fallo operativo fue **0.9167 en ambos brazos**: lo que se estaba midiendo era la
pared, no la arquitectura.

**Comparabilidad.** Ningún pilot completado depende del valor de 1800 s. Las
cuatro tentativas previas fueron o inválidas (lock retenido, Programador de
tareas, sesión caducada) o canary. **No se invalida ningún resultado publicado.**

**Lo que NO cambia.** Configuraciones, semillas, casos, pesos de experto,
endpoints primarios, regla de reporte, ciclos mínimos antes de resolución,
máximo de fallos operativos consecutivos y el protocolo mínimo en vivo —
incluidos los dos evaluadores humanos ciegos por celda— permanecen intactos.
Solo se movió el techo temporal por ciclo.
