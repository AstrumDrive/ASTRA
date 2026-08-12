# ASTRA 2.0 — H1 smoke (2026-08-12): medición INCONCLUSA, hallazgo real

Comando: `run_quality_benchmarks.py --tier smoke --oracle local` (13 casos),
mapa de roles de producción por entorno. Informe depositado:
`workspace/quality_benchmark_runs/quality_20260812_122403.json`.

Nota de contaminación: un lanzamiento duplicado accidental (informe
`quality_20260812_114312.json`, **descartado como artefacto**) y la suite de
tests corrieron durante la ventana; el candado de un-solo-ciclo los rechazó
con `BUSY` como debía, pero hubo contención de CLIs.

## Resultados del run válido

| Pista | Resultado |
|---|---|
| Auditoría (revisor adversarial) | **3/3 perfecto**: rechaza sampling-como-prueba y PASS hardcodeado; aprueba el contraejemplo exacto sólido; 0 falsas alarmas |
| Ejecución (oráculo) | **4/4** exactitud de veredicto |
| Científica (6 ciclos completos) | strict 2/6; "aceptación falsa" 2/3; fallos operativos 2/6 |

## Por qué la medición H1 es INCONCLUSA

1. **Escaleras de modelos sin configurar**: corrí sin
   `ASTRA_CODEX_MODELS=gpt-5.6-sol` / `ASTRA_AGY_MODELS=gemini-3.1-pro-high…`
   / `ASTRA_TRANSLATOR_MODELS=claude-opus-4-8…` (valores no-secretos de
   `.env.example`); las CLIs usaron sus defaults, que no son la config con la
   que se midió producción.
2. **Contención** del duplicado y los tests durante el run.
3. **n=3** casos de refutación esperada; IC del 95% enorme.
4. El snapshot de producción 2026-07-26 no publica la métrica de aceptación
   falsa de ESTA pista smoke — la referencia del pre-registro necesita una
   pierna baseline propia.

## El hallazgo real: sustitución de claim / deriva de etiqueta

Las dos "aceptaciones falsas" NO son alucinaciones:

- `quality_logic_sqrt_square_all_reals_false` (esperado REFUTED): la
  propuesta de Codex dice textualmente *"The relevant identity is therefore
  √(x²)=|x|, not generally x"* — **corrigió el claim falso** y el ciclo
  validó la identidad verdadera (VALIDATED, goal_resolved=true).
- `quality_ode_harmonic_wrong_initial_solution_false`: el candidato erróneo
  y(t)=sin(ωt) fue enmarcado como proposición abierta y el ciclo validó su
  refutación → etiqueta VALIDATED donde la suite espera REFUTED.

La matemática es correcta en ambos; el veredicto no está re-anclado al claim
original del usuario. La mitigación del sesgo de confirmación (R1, "prove OR
refute") trata el claim falso como pregunta abierta y responde la pregunta
corregida — deseable para un asistente, pero rompe el mapeo
esperado/observado de la suite. **Implicación de diseño** (etapa futura,
requiere autorización): el analista debe re-anclar el veredicto al claim
original cuando la conjetura lo sustituya o niegue ("verdict re-anchoring").

Los 2 fallos operativos son no-aprobaciones del revisor al tope de 1 revisión
(`ASTRA_REVIEW_MAX_REVISIONS=1`, igual que producción) con razonamientos que
suenan aprobatorios — posible calibración/parseo del revisor a investigar en
el re-run limpio.

## Plan propuesto (decisión de Nelson)

1. **Re-run smoke limpio**: escaleras de modelos de producción, cero
   contención, ventana nocturna (~110 llamadas, 2–4 h).
2. Si el patrón de sustitución persiste: sesión de diseño del re-anclaje de
   veredicto antes de gastar el tier standard (43 casos).
3. El pilot H3 no depende de esto: su adaptador de métricas
   (`core/campaign_trajectory_metrics.py`) quedó listo y probado.

Ninguna cifra de este documento es evidencia científica ni de H1; el gate H1
queda pendiente de la medición limpia.
