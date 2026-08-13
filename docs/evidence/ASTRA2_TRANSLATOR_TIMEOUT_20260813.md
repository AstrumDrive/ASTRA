# ASTRA 2.0 — prueba dirigida del techo del traductor (2026-08-13)

Autorización: Nelson autorizó la prueba dirigida propuesta tras la
re-medición del gate H1.

Comando: los siete casos que fallaron en
`quality_20260813_022505.json`, con **`ASTRA_TRANSLATOR_TIMEOUT=480`** y
`--cycle-timeout 3600` (para que el techo del benchmark no enmascare el
resultado). Informe: `quality_20260813_043803.json`.

## Resultado: 4 de 7 convierten

| Caso | Antes | Después |
|---|---|---|
| `fluids_hagen_poiseuille_scaling` | TIMEOUT (patch 481 s) | **VALIDATED** |
| `quality_gr_schwarzschild_ricci_nonzero_false` | TIMEOUT (translate 482 s) | **REFUTED** |
| `gr_minkowski_flat_curvature` | INCONCLUSIVE | **VALIDATED** |
| `symbolic_polynomial_factorization_sage` | API_ERROR (revisor) | **VALIDATED** |
| `quality_algebra_cancellation_without_nonzero_false` | API_ERROR | API_ERROR |
| `quantum_density_trace_preserved` | TIMEOUT | API_ERROR |
| `lean_nat_add_comm` | TIMEOUT | TIMEOUT |

## Atribución honesta

**Atribuible al techo** (fases que superan los 240 s del default y por tanto
habrían muerto antes):

- `quality_gr_schwarzschild_ricci_nonzero_false`: `translate` **370 s** →
  veredicto REFUTED correcto;
- `gr_minkowski_flat_curvature`: `translate` **250 s** + patch 189 s →
  VALIDATED;
- `quality_algebra_cancellation`: `translate_patch` **438 s** (llegó a
  completar la reparación, aunque el revisor bloqueó después).

**NO atribuible**: `symbolic_polynomial_factorization_sage` convirtió con
`translate` de sólo **94.8 s**, muy por debajo del techo viejo — su cambio es
la misma varianza de siempre (ya había convertido en la prueba aislada de la
calibración y vuelto a fallar en la suite completa).
`fluids_hagen_poiseuille` no necesitó parche esta vez, así que su conversión
mezcla ambos efectos.

**La tasa de fallo operativo de este run (0.4286) NO es comparable** con la de
la suite: el subconjunto está sesgado por construcción — son precisamente los
casos que ya fallaban.

## Conclusión aplicada

`ASTRA_TRANSLATOR_TIMEOUT=480` queda documentado en `.env.example` con su
justificación. El propio código ya lo recomendaba
(`astra_tool.py:1155`); lo que faltaba era la medición y la plantilla.
Afecta igual a producción, que hoy corre el traductor con 240 s.

## El cuello vuelve a moverse: revisor, otra vez

Dos de los tres fallos restantes son **no-aprobación del revisor**, con el
mismo patrón que la calibración pretendía cerrar: describe las piernas como
sólidas y bloquea igual.

- *"Legs A, B, P, and D soundly cover the partial domain, zero-denominator
  classification, and adversarial zero-total…"* → bloquea.
- *"The general-n cyclic summand certificate soundly supports trace
  cyclicity, and the Hadamard and nonunitary contr[actions]…"* → bloquea.

La calibración (reglas 14–16) hace que el revisor **articule** la distinción
decisiva/auxiliar sin **actuar** sobre ella. Un prompt más no parece la
palanca correcta; opciones estructurales, **cada una requiere autorización**:

1. `ASTRA_REVIEW_MAX_REVISIONS=2` para que la instrucción acotada del revisor
   llegue a aplicarse en vez de matar el ciclo (coste: una llamada más por
   ciclo afectado);
2. tratar como operativo-recuperable el caso "el revisor declara sólidas las
   piernas decisivas y aun así bloquea", dejando que el preflight
   determinista decida;
3. medir primero cuántas veces ocurre, con repeticiones, antes de tocar nada.

El tercer fallo, `lean_nat_add_comm`, ya no es de tiempo sino del reparador:
*"Bounded model patch was not applicable: No forbidden `axiom` declaration or
proof placeholder is present in the artifact. The token only occurs inside the
required axiom-cleanliness machinery (`#print`…)"* — el reparador intenta
arreglar un defecto inexistente. Diagnóstico aparte, ahora visible porque el
Unicode ya no lo enmascara.

Ninguna cifra de este documento es evidencia científica publicable
(`PUBLICATION_POLICY.md`).
