# ASTRA 2.0 — H1 smoke LIMPIO (2026-08-12): cero alucinaciones, defecto de etiqueta confirmado

Comando (configuración íntegra de producción de `.env.example`: `gpt-5.6-sol`
razonamiento `xhigh`, `gemini-3.1-pro-high` esfuerzo `high`,
`claude-opus-4-8` traductor, revisión independiente, navegación post-ciclo,
repair vNext.1, caché apagada, oráculo local, un solo proceso sin contención):

```powershell
run_quality_benchmarks.py --tier smoke --oracle local
```

Informe depositado: `workspace/quality_benchmark_runs/quality_20260812_163841.json`
(consola: `workspace/benchmark_runs/h1_smoke_clean_console.log`).

## Cifras crudas

| Pista | Resultado |
|---|---|
| Auditoría (revisor adversarial) | **3/3**; recall de defectos 1.0; **falsas alarmas 0.0** |
| Ejecución (oráculo) | **4/4** exactitud de veredicto |
| Científica (6 casos) | strict 0.5; "false_acceptance_rate" 0.6667; fallo operativo 0.1667 |
| Grados de evidencia | A=7, F=3 |
| Latencia | p50 18.8 s; p95 725.6 s |

Mejoras claras frente al run sucio: fallo operativo 0.33 → **0.17**, strict
0.33 → **0.50**, grados A 6 → **7**, y `logic_false_square_claim` pasó de
`API_ERROR` a **REFUTED correcto**.

## Hallazgo principal: la "aceptación falsa" de 0.6667 es un ARTEFACTO DE MEDICIÓN

Texto literal de las conjeturas de consenso que ASTRA formó y validó:

- `quality_logic_sqrt_square_all_reals_false` (claim sembrado falso:
  ∀x∈R, √(x²)=x):
  > *"Bajo la convención de raíz cuadrada principal, x*=-1 es un
  > **contraejemplo exacto** a ∀x∈R, √(x²)=x … En consecuencia, √(x²)=x ⟺
  > x≥0, y **la afirmación universal sobre R es falsa**."*

- `quality_ode_harmonic_wrong_initial_solution_false` (candidato falso
  y=sin(ωt)):
  > *"y(t)=sin(ωt) **no satisface** el problema de valores iniciales dado,
  > porque incumple necesariamente y(0)=1 … el candidato queda **refutado**
  > para todo ω admisible."*

En ambos casos ASTRA **refutó correctamente el claim falso**. El ciclo
reporta `VALIDATED` porque la conjetura que efectivamente probó ("existe un
contraejemplo", "el candidato es refutado") resultó verdadera. La suite
compara ese estado contra el `REFUTED` esperado del claim original.

**Conteo epistémico correcto de este run**: 5 ciclos completaron; en **5/5 la
ciencia fue correcta**; alucinaciones (aceptar como verdadero algo falso):
**0**. La `false_acceptance_rate` publicada mide desalineación de etiqueta,
no error científico.

## Defecto de diseño identificado: falta re-anclaje de veredicto

`astra_tool` reporta el estado de la **conjetura formada**, no del **claim
original del usuario**. Cuando la conjetura niega o sustituye al claim
(consecuencia deseable de la postura neutral R1 "prove OR refute"), el
veredicto se invierte respecto a lo que el usuario preguntó.

Corrección propuesta (etapa futura, **requiere autorización**): el analista
recibe explícitamente el claim original y devuelve `original_claim_verdict`
∈ {SUPPORTED, REFUTED, INCONCLUSIVE, SUBSTITUTED} junto al estado atómico
actual; `_goal_coverage` lo propaga sin colapsar ejes; la suite compara
contra ese campo. Esto también beneficia a producción: hoy un usuario que
pregunta por un claim falso recibe "VALIDATED" con la refutación en el
cuerpo del texto.

## Estado del gate H1

**No superado ni fallado: bloqueado por instrumento.** Medir aceptación falsa
con estos casos requiere primero el re-anclaje; con la instrumentación actual
el tier standard (43 casos, 7–14 h) mediría mayoritariamente el mismo
desajuste. Recomendación: implementar el re-anclaje (barato, sin cuota, con
tests deterministas) y sólo entonces gastar el standard.

El caso `ode_harmonic_oscillator_solution` dio `TIMEOUT` a 662 s: operativo,
atribuible al razonamiento `xhigh`; no es refutación (separación de ejes
respetada).

Ninguna cifra de este documento es evidencia científica publicable
(`PUBLICATION_POLICY.md`).
