# ASTRA 2.0 — Gate H1, tier standard (2026-08-12): aceptación falsa 0.0

Autorización: Nelson autorizó el run tras validar el instrumento de
re-anclaje. Ejecutado con prioridad `BelowNormal` sobre el árbol de procesos
del benchmark para no competir con su trabajo interactivo.

Comando (configuración íntegra de producción, oráculo local, `--jobs 2`):

```powershell
run_quality_benchmarks.py --tier standard --oracle local --jobs 2
```

Informe depositado:
`workspace/quality_benchmark_runs/quality_20260812_214125.json`
(consola: `workspace/benchmark_runs/h1_standard_console.log`).
43 casos programados; 23 científicos decidibles, 14 de auditoría, 6 de
ejecución.

## Resultado del gate

| Métrica | Valor |
|---|---|
| **Aceptación falsa** (métrica de veto del gate) | **0.0** |
| **Rechazo falso** | **0.0** |
| Exactitud estricta | 0.7391 (IC95 0.535–0.875) |
| Exactitud balanceada | 0.7349 |
| Fallo operativo | 0.1739 |
| Auditoría: recall de defectos / críticos / etiquetas | 1.0 / 1.0 / 1.0 |
| Auditoría: falsa alarma sobre validadores sanos | 0.3333 |
| Ejecución: exactitud de veredicto | 1.0 (6/6) |
| Grados de evidencia | A=23, F=6 |

**En 23 casos científicos, ASTRA nunca aceptó como verdadero un claim falso
ni rechazó como falso un claim verdadero.** Ningún fallo del run fue
epistémico.

## Los seis casos no acertados, uno por uno

**Dos INCONCLUSIVE — el eje de re-anclaje respondiendo con honestidad, no
error:**

- `quality_algebra_cancellation_without_nonzero_false`: *"P afirma que
  a/b=c/b implica a=c para todos los reales a,b,c, pero el validador
  establece que las instancias b=0 contienen cocientes indefinidos, por lo
  que P no posee un valor de verdad bajo la división real ordinaria."* El
  fixture espera REFUTED; el analista distingue **falso** de **mal formado**.
  Posición epistémica defendible y más rigurosa que la etiqueta esperada.
- `gr_minkowski_flat_curvature`: *"P asserts both vanishing Christoffel
  symbols and zero curvature; the validator establishes all 64 Christoffel
  components exactly but deliberately does not test the curvature part."* El
  ciclo atómico difirió media proposición y el analista se niega a dar por
  decidida la otra mitad. Es la separación atómico/diferido funcionando.

**Tres API_ERROR — no-aprobación del revisor al tope de 1 revisión:** los
tres razonamientos describen el validador como sólido en sus piernas
decisivas y aun así bloquean por partes auxiliares:

- *"The exact SymPy leg independently constructs the connection, Ricci
  tensor… so it can falsify claims 1–4. However, random floa[ting point]…"*
- *"The decisive theorem and independent proof legs are conceptually sound
  and capable of establishing the universal claim by kernel checking; the
  finite grid is only auxiliary…"*
- *"The decisive SymPy Poly checks are exact, falsifiable, and cover all
  three algebraic claims over QQ; the sampling and point checks are only
  supplemental…"*

**Un TIMEOUT**: `quantum_density_trace_preserved` (931 s).

**Una falsa alarma de auditoría**: `audit_regression_einsteinpy_list_symbols_supported`
→ REVISE en vez de APPROVED. El argumento es nuevo (cobertura del claim
declarado: *"the conjecture asserts acceptance of both list and tuple
coordinate collections, while the script exercises only the list form"*), no
el falso positivo de API original que vNext.1 corrigió. Requiere decidir si
el caso de regresión sigue midiendo lo que pretendía.

## Interpretación

El cuello de botella de ASTRA **no es la veracidad, es la fiabilidad**. El
17.4% de fallo operativo está dominado por el revisor bloqueando validadores
que él mismo describe como decisivamente sólidos, con
`ASTRA_REVIEW_MAX_REVISIONS=1` convirtiendo esa no-aprobación en muerte del
ciclo. Ninguna de esas pérdidas fue una afirmación falsa admitida.

Consecuencia para el objetivo de Nelson ("menos alucinaciones"): en esta
medición no hay alucinaciones que reducir; el margen de mejora está en
convertir revisiones bloqueadas en evidencia. Candidatos, **cada uno
requiere autorización**:

1. calibrar el revisor para no bloquear por piernas auxiliares/supletorias
   cuando las decisivas son sólidas (afecta prompts de producción);
2. considerar `ASTRA_REVIEW_MAX_REVISIONS=2` para casos donde la instrucción
   de revisión es acotada (coste: una llamada más por ciclo afectado);
3. revisar el fixture de regresión de EinsteinPy y los dos fixtures cuyas
   etiquetas discrepan de un análisis más riguroso (instrumento, no modelo).

Comparación con el snapshot de producción del 2026-07-26: no publica una
tasa de aceptación falsa para esta pista, así que **este run es la primera
línea base de la métrica**, no una comparación. G3 sigue abierto: falta la
suite de validación cliente y el subconjunto externo bajo protocolo
congelado.

Ninguna cifra de este documento es evidencia científica publicable
(`PUBLICATION_POLICY.md`).
