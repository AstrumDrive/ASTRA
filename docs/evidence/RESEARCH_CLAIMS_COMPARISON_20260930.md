# Un modelo solo contra el ciclo de producción sobre claims de investigación real (2026-09-30 / 2026-10-01)

Tercera medición de la auditoría de eficiencia
(`ASTRA_EFFICIENCY_AUDIT_20260930.md`). Los 23 casos congelados del tier
estándar resultaron fáciles para ambos brazos
(`PRODUCTION_PROFILE_AND_BASELINE_ARM_20260930.md`, sección 4), y la
pregunta de Nelson es otra. Si ASTRA ayuda en la investigación, tiene que
decidir mejor que un modelo solo sobre los claims que salen de sus
proyectos, no sobre ejercicios de libro. Este documento mide eso.

Resultado en una frase: sobre 27 claims de investigación, el ciclo de
producción acertó 16 y el modelo solo 12, ninguno aceptó un claim falso,
la ventaja del ciclo está toda en fiabilidad operativa (repara validadores
rotos y respeta la métrica dada), no alcanza significación con esta muestra
(p = 0,34), y el mayor freno de los dos brazos resultó ser una tubería de
ASTRA, no los modelos: el autor del validador nunca veía las definiciones
del usuario. Arreglado el mismo día.

## 1. El corpus: 27 claims con verdad medida

`benchmarks/quality/research/cycle/research_v1.json`. Los claims vienen de
proyectos activos de `Dev`, con sus convenciones escritas en el propio caso
para que ninguna arquitectura dependa de leer el repo:

| Bloque | Proyecto de origen | Casos | Verdaderos | Falsos sembrados |
|---|---|---|---|---|
| Jerarquía Kondo de dos orbitales | `physics/kondo_eom_minimal_hierarchy_codex` | 6 | 3 | 3 |
| Identidades de energía en RG (pared plana, cáscara estática, Kinnersley) | `warp/energy_identities_ledger` | 6 | 3 | 3 |
| Cáscara hueca con lapso unidad | `warp/hollow-core-energy-conditions-reproducibility` | 2 | 1 | 1 |
| Quench súbito de masa, coeficientes de Bogoliubov | `physics/quenched-scalar-field-keldysh-wigner-wavelet` | 4 | 2 | 2 |
| Cota del cohete relativista | `warp/high_speed_subluminal_warp` | 2 | 1 | 1 |
| Gradiente de una función armónica | `warp/high_speed_subluminal_warp` | 2 | 1 | 1 |
| Curvatura de Wu-Yang SU(2) y espectro de carga SU(3) | `physics/spectral-smarr-sun` | 3 | 2 | 1 |
| Teorema de Nagaoka en la cinta de Möbius | `physics/mobius_geometric_spin_transport` | 2 | 1 | 1 |
| **Total** | | **27** | **14** | **13** |

Cada falso sembrado altera una sola cosa del claim verdadero vecino (un
signo, un coeficiente, un umbral, el flujo) y lo declara en
`metadata.seeded_error`. Un modelo que conozca el resultado verdadero y lo
confunda con el enunciado cae en estos casos.

Ningún `expected` se tomó de los documentos de los proyectos. Los cuatro
scripts de `benchmarks/quality/research/reference/` rederivan cada claim
desde cero, con otra implementación que la del proyecto de origen:

- `kondo_reference.py`: impureza de espín 1/2 por cuatro modos de
  Jordan-Wigner, matrices de 32 por 32, métrica de temperatura infinita
  evaluada como traza exacta.
- `gr_reference.py`: tensor de Einstein en SymPy desde los símbolos de
  Christoffel, para funciones genéricas de la métrica. Las cuatro métricas
  tardan 8 s en una máquina ociosa (`outputs/gr_reference_20261001_timing.txt`).
- `misc_reference.py`: límites exactos de los coeficientes de Bogoliubov,
  integración numérica del cohete contra la forma cerrada, identidad del
  gradiente armónico sobre cuatro funciones armónicas, curvatura y espectro
  con las matrices explícitas de los generadores.
- `mobius_reference.py`: diagonalización exacta de un hueco en el modelo de
  Hubbard a U infinita sobre la cinta de Möbius de 8 sitios, espacio de 1024
  estados, con el espín total del estado fundamental leído de S².

Las salidas están depositadas en `reference/outputs/*_20260930.txt` y
`*_20261001.txt`. Un caso entra al corpus solo si el valor impreso de su
`metadata.reference` coincide con su `expected`. Los 27 coinciden. La cota
de Natário quedó fuera a propósito, porque el artículo está en revisión.

## 2. Protocolo

Los mismos dos brazos del documento anterior, sin cambios en el `.env` vivo
durante la corrida:

- `single-model`: un solo Codex (GPT-6 Luna) propone, escribe el validador,
  lee la salida del oráculo y dicta el veredicto. Sin revisor, sin
  reparación, sin guarda determinista, sin reintentos.
- `no-ensemble`: el perfil de producción. Codex propone, Claude Opus 5.5
  traduce, revisor independiente (Codex), oráculo, analista (Codex) con el
  veredicto re-anclado al claim original.

Oráculo local en los dos. Puntuación re-anclada, como en el documento
anterior. Los casos pesados llevan su propio `timeout` de ejecución, 900 s
para los tensores de Einstein simbólicos y 600 s para la diagonalización,
y el runner espera hasta 3000 s por ciclo. Lanzamiento desde un PowerShell
separado de la sesión, con la prioridad de los procesos del benchmark
bajada a `BelowNormal` a los 90 s:

```powershell
.\venv\Scripts\python.exe scripts\run_quality_benchmarks.py --case-root benchmarks\quality\research --no-legacy --tier standard --tracks cycle --oracle local --cycle-timeout 3000 --config single-model
.\venv\Scripts\python.exe scripts\run_quality_benchmarks.py --case-root benchmarks\quality\research --no-legacy --tier standard --tracks cycle --oracle local --cycle-timeout 3000 --config no-ensemble
```

Registro de la corrida en `workspace/benchmark_runs/research_arms_20260930_2330.status`
y los dos `research_<brazo>_20260930_2330.log`. Reportes:
`workspace/quality_benchmark_runs/quality_20261001_012649.{json,md}`
(modelo solo) y `quality_20261001_045331.{json,md}` (producción). La
comparación lado a lado y la estadística están depositadas en
`workspace/quality_benchmark_runs/research_arms_compare_20261001.txt`.
Como `workspace/` no se versiona, los dos reportes Markdown, la
comparación y el registro de la corrida están copiados en
`docs/evidence/research_arms_20261001/`.

## 3. Resultados

### 3.1 Titular

| Métrica | Modelo solo | Producción `no-ensemble` |
|---|---:|---:|
| Aciertos estrictos | 12 / 27 (0,444) | 16 / 27 (0,593) |
| Aceptaciones falsas (claim falso dado por válido) | 0 / 13 | 0 / 13 |
| Refutaciones falsas (claim verdadero dado por refutado) | 2 / 14 | 1 / 14 |
| Fallos operativos (definición del runner) | 10 / 27 (0,370) | 4 / 27 (0,148) |
| No decidió (NON_DECIDABLE, INCONCLUSIVE, SUBSTITUTED) | 3 | 6 |
| Latencia p50 / p95 por ciclo | 254 s / 429 s | 360 s / 1122 s |
| Pared total | 116,5 min (23:30 a 01:26) | 206,7 min (01:26 a 04:53) |

Pares discordantes: 7 casos los acertó solo producción, 3 solo el modelo
solo, 9 los acertaron los dos y 8 los fallaron los dos. McNemar exacto a dos
colas sobre 3 contra 7: p = 0,344. La ventaja del ciclo es consistente con
lo que se ve caso a caso, pero 27 claims no bastan para declararla.

Una de las dos refutaciones falsas del modelo solo, y la única de
producción, es el mismo caso, y ahí los dos brazos tenían razón (sección
3.4). Sin ese caso, n = 26: modelo solo 12 / 26 (0,462) con 1 / 13
refutaciones falsas; producción 16 / 26 (0,615) con 0 / 13. Los pares
discordantes no cambian.

### 3.2 Caso a caso

| Caso | Esperado | Modelo solo | Producción |
|---|---|---|---|
| `res_harmonic_gradient_factor_false` | REFUTED | REFUTED | REFUTED |
| `res_harmonic_gradient_subharmonic_true` | VALIDATED | VALIDATED | VALIDATED |
| `res_kondo_b1_commutator_sign_false` | REFUTED | REFUTED | REFUTED |
| `res_kondo_b1_commutator_true` | VALIDATED | CODE_ERROR | NON_DECIDABLE |
| `res_kondo_c1_commutator_x1_false` | REFUTED | CODE_ERROR | API_ERROR |
| `res_kondo_c1_norm_false` | REFUTED | CODE_ERROR | API_ERROR |
| `res_kondo_exchange_block_true` | VALIDATED | CODE_ERROR | NON_DECIDABLE |
| `res_kondo_two_orbital_norms_true` | VALIDATED | REFUTED | NON_DECIDABLE |
| `res_mobius_nagaoka_saturated_true` | VALIDATED | CODE_ERROR | **VALIDATED** |
| `res_mobius_nagaoka_wrong_flux_false` | REFUTED | CODE_ERROR | **REFUTED** |
| `res_su2_wu_yang_curvature_sign_false` | REFUTED | REFUTED | REFUTED |
| `res_su2_wu_yang_curvature_true` | VALIDATED | **VALIDATED** | API_ERROR |
| `res_su3_charge_spectrum_true` | VALIDATED | CODE_ERROR | **VALIDATED** |
| `res_gr_kinnersley_sign_false` | REFUTED | CODE_ERROR | **REFUTED** |
| `res_gr_kinnersley_true` | VALIDATED | CODE_ERROR | **VALIDATED** |
| `res_gr_planar_wall_rho_false` | REFUTED | REFUTED | REFUTED |
| `res_gr_planar_wall_true` | VALIDATED | **VALIDATED** | INCONCLUSIVE |
| `res_gr_static_shell_dec_false` | REFUTED | REFUTED | REFUTED |
| `res_gr_static_shell_true` | VALIDATED | REFUTED | REFUTED |
| `res_gr_unit_lapse_shell_pr_false` | REFUTED | REFUTED | REFUTED |
| `res_gr_unit_lapse_shell_true` | VALIDATED | **VALIDATED** | API_ERROR |
| `res_quench_bogoliubov_uv_true` | VALIDATED | INCONCLUSIVE | INCONCLUSIVE |
| `res_quench_occupation_monotone_true` | VALIDATED | INCONCLUSIVE | INCONCLUSIVE |
| `res_quench_occupation_vanishes_at_zero_false` | REFUTED | REFUTED | REFUTED |
| `res_quench_uv_coefficient_false` | REFUTED | REFUTED | REFUTED |
| `res_rocket_mass_bound_reversed_false` | REFUTED | CODE_ERROR | **REFUTED** |
| `res_rocket_mass_bound_true` | VALIDATED | SUBSTITUTED | **VALIDATED** |

En negrita, el acierto que el otro brazo no tuvo. Los cuatro `API_ERROR`
de producción son, leídos en los checkpoints, dos rechazos del revisor
tras dos revisiones, un analista que agotó el tope de 240 s de la CLI y un
presupuesto de ciclo agotado tras una ejecución de 900 s. El runner los
etiquetaba todos como error de modelo; desde hoy distingue
`REVIEW_REJECTED` y `BUDGET_EXHAUSTED`.

### 3.3 Dónde gana cada brazo

Producción acierta sola en siete casos, y en los siete el modelo solo cayó
por una razón operativa que el ciclo corrige:

- Möbius, los dos casos. El modelo solo escribió validadores con errores
  de sintaxis y no tiene reparación. En producción el revisor devolvió el
  validador, el reparador lo arregló y la diagonalización dio S = 7/2 con
  flujo 1/2 y S = 1/2 con flujo cero. Costó 895 s y 1198 s de ciclo.
- Kinnersley, los dos casos. El traductor del modelo solo cambió los signos
  de g_uu, g_ur, g_θθ y g_φφ y obtuvo un residuo no nulo que el analista,
  con razón, no leyó como refutación. En producción Opus respetó la métrica
  del enunciado y las dos decisiones de signo salieron.
- Espectro SU(3). El check simbólico del modelo solo murió en un error de
  valor de verdad relacional de SymPy; producción lo evitó.
- Cohete, los dos casos. El modelo solo produjo el contraejemplo correcto
  (w = 1/2 da e^{-2θ} < e^{-θ}) pero su validador terminó en `VERDICT: FAIL`
  con todos los checks en OK y el analista lo devolvió como `CODE_ERROR`;
  en el caso verdadero sustituyó la cota global por su versión diferencial
  local. Producción decidió los dos.

El modelo solo acierta solo en tres casos, y en los tres producción se
hundió por su propio peso:

- Curvatura de Wu-Yang verdadera. El revisor rechazó dos veces un validador
  cuyo tramo principal esperaba que "le suministraran" los generadores, que
  el enunciado da como matrices explícitas. Es el defecto de tubería de la
  sección 3.5.
- Pared plana verdadera. El validador de producción probó solo ρ = 0 y el
  analista re-anclado se negó a certificar las otras cláusulas:
  INCONCLUSIVE. El modelo solo probó las tres.
- Cáscara con lapso unidad. El validador de producción lanzó un cálculo
  simbólico que agotó los 900 s del oráculo, y con 77 s restantes del
  presupuesto de 1500 s el ciclo ya no pudo pasar por revisión. La
  derivación de referencia de las cuatro métricas tarda 8 s.

### 3.4 Lo que los dos brazos encontraron en el corpus

Dos defectos del enunciado, no de la física, salieron de la corrida y
quedan corregidos en `research_v1.json` (marcados en `metadata.revised`):

- `res_gr_static_shell_true`, parte (4): "bajo p_r = 0 y m' ≥ 0, la DEC
  equivale a 2m/R ≤ 4/5". En un radio con m' = 0 se tiene ρ = p_⊥ = 0 y la
  DEC se cumple con cualquier 2m/R < 1; el modelo solo lo exhibió con
  2m/R = 9/10. El umbral de la referencia salía del cociente p_⊥/ρ, que
  asume ρ > 0. El enunciado correcto exige m' > 0.
  `gr_reference.py` imprime ahora el agujero
  (`gr_static_shell_v1_wording_false_at_m_prime_zero: TRUE`). Las dos
  refutaciones fueron correctas y por eso el caso sale del titular en la
  cuenta de n = 26.
- Los seis casos de Kondo usaban b y c como índice del producto vectorial y
  como índice de espinor a la vez. El revisor de producción rechazó un
  validador por eso en `res_kondo_c1_norm_false`. Ahora son j, k.

Y un error que sí es del modelo: en `res_kondo_two_orbital_norms_true` el
modelo solo construyó C_{0,↑} como componente esférica (S × s_0)^x + i(S ×
s_0)^y, sin el fermión f_{0b}, y obtuvo traza 8 (norma 1/4) en vez de 12
(3/8). Las tres convenciones de orden plausibles dan 3/8
(`kondo_reference.py`, comprobación del 2026-10-01).

### 3.5 La causa común: el autor del validador no veía las definiciones

Hasta hoy `astra_tool.py` construía la entrada del traductor con el
objetivo corto, las respuestas del usuario a declaraciones MISSING y la
conjetura del proponente. El texto de `intuition`, donde van las
convenciones de Jordan-Wigner, los operadores compuestos, las componentes
de la métrica o los generadores, llegaba al proponente y al analista pero
nunca al autor del validador. Cuando la conjetura no reescribía las
definiciones, el validador las declaraba ausentes. En los checkpoints:

- Modelo solo: tres `CODE_ERROR` de Kondo con validadores que imprimen
  "operator definitions not supplied".
- Producción: tres `NON_DECIDABLE` de Kondo con listas MISSING
  (convención de modos, H_J, B, C, Y), el analista del cuarto agotando
  240 s sobre un validador MISSING, y el rechazo de SU(2) por generadores
  "no suministrados". En dos de ellos el analista anota que "el prompt sí
  trae las definiciones", porque él sí las recibe.

Son 3 de los 15 fallos del modelo solo y 5 de los 11 de producción. Es el
mayor freno individual de la medición y afectaba por igual a los dos brazos,
así que la comparación sigue siendo justa; lo que no es justo es con el
usuario.

Arreglo (commit de hoy): `build_translation_input` en `astra_tool.py` cita
el texto del usuario entre el objetivo y la conjetura, bajo el rótulo
"USER'S CLAIM AND DEFINITIONS", con un tope de 3500 caracteres para que la
conjetura siga dentro de la ventana de 5000 que leen el revisor y el
reparador. Tests en `tests/test_translation_input.py`.

### 3.6 Otros ajustes salidos de la corrida

- `ASTRA_CLI_TIMEOUT` sube de 240 a 480 s en el `.env` vivo (respaldo
  `.env.bak_20261001`). Un analista de Luna en razonamiento alto excedió
  los 240 s.
- El runner pasa `cycle_timeout_seconds = max(1500, timeout + 900)` para
  que un caso con oráculo de 900 s conserve revisión y análisis.
- Claims con varias partes producen validadores parciales en los dos
  brazos (los dos de quench, INCONCLUSIVE en ambos; el cohete y la pared
  plana en un brazo cada uno). El re-anclaje hizo su trabajo al no
  certificarlos, pero el corpus debe pedir una proposición por caso. Queda
  para v1.2.
- Dos ciclos del modelo solo refutaron bien y salieron `CODE_ERROR` porque
  checks auxiliares fallaron; la puntuación re-anclada solo lee el eje
  `original_claim_verdict` cuando el estado es VALIDATED, REFUTED o
  WEAK_PASS. Se mantiene estricto a propósito: un refutador con código roto
  no es evidencia de grado.

## 4. Lectura

1. Sobre claims de investigación la deliberación sí rinde, y rinde donde
   la auditoría del 30-sep predijo: fiabilidad. Siete aciertos netos frente
   a tres, todos por reparar validadores rotos, respetar la métrica dada o
   decidir donde el modelo solo se quedó a medias. Cuesta 1,8 veces la
   pared y una p95 de 19 min.
2. Ni un claim falso aceptado en 54 ciclos. El oráculo más el veredicto
   re-anclado sostienen la garantía que importa para investigación.
3. Con n = 27 la ventaja no alcanza significación (p = 0,34). Hacen falta
   más claims, no más brazos.
4. El mayor salto disponible no está en los modelos sino en la tubería:
   las definiciones del usuario no llegaban al autor del validador. Con el
   arreglo de hoy, los cinco casos de Kondo y el de SU(2) que cayeron por
   eso son los primeros candidatos a cambiar de signo en la repetición.
5. El corpus también sale mejorado: dos enunciados míos eran imprecisos y
   los brazos lo detectaron antes que yo. El investigador incrédulo
   funciona en las dos direcciones.

Siguiente medición, cuando haya cuota: los mismos 27 claims en v1.1 con el
arreglo de la tubería, solo en producción, para medir cuánto de la brecha
era tubería. Después, v1.2 con una proposición por caso.
