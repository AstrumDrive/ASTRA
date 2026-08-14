# Prueba con `astra_dev`: NEC de una onda viajera warp (2026-08-14)

Primer uso real de la línea de desarrollo desde un agente vía MCP, sobre la
pregunta de Nelson: *¿podemos hacer andar este warp drive con las condiciones
de energía cumplidas a velocidad constante?*

## Lo que hizo ASTRA

Ciclo `cycle_20260814_031010_f2fa`, persistente, oráculo local, 1845 s.
El ensemble (codex `gpt-5.6-sol` + agy `gemini-3.1-pro-high`, síntesis codex)
convirtió la pregunta general en una **conjetura concreta y decidible** en
524 s:

```text
xi = x - v t,  r^2 = xi^2 + y^2 + z^2,  v = 1/2
f      = 1 / (1 + (r^2/R^2)^2)
alpha  = 1 + f/4     beta^x = -f/2     psi = 1 + f/5
ds^2 = -alpha^2 dt^2 + psi^4 [ (dx + beta^x dt)^2 + dy^2 + dz^2 ]

Claim decisivo:  m_p = min_{|s|=1} T_uv k^u k^v  <  0   en  p = (0, 0, R, 0)
```

Con protocolo estricto autoimpuesto: diferenciar **antes** de sustituir,
aritmética exacta con aislamiento de raíces, **prohibición explícita** de
decidir por muestreo angular o flotantes, y acotación honesta de que un
resultado en `p` decide la NEC **solo en `p`**.

**El ciclo terminó en `TOOL_ERROR`**: la fase de traducción agotó 480 s y su
reintento de script mínimo otros 360 s
(`API_ERROR: 'claude-opus-4-8': timeout tras 360s`). ASTRA no falló al
razonar; falló al escribir el validador.

## El resultado

El checkpoint sugiere explícitamente usar la conjetura con `astra_execute`.
El validador lo escribí yo siguiendo el protocolo de la conjetura, y se
ejecutó por el oráculo de ASTRA:

| | R = 1 | R = 2 |
|---|---|---|
| `m_p` | −196091158785784⁄1172859407230599 | −49022789696446⁄1172859407230599 |
| ≈ | −0.16719 | −0.04180 |

- Escalado **exacto** `m_p ∝ 1/R²` (verificado como identidad racional, no
  numéricamente): confirma la predicción de independencia del signo respecto
  de `R` que la propia conjetura hacía.
- Certificado del mínimo:
  `s* = (−465850/8173439, −3√7398676540469/8173439, 0)`.
- Tétrada euleriana verificada ortonormal **contra la métrica calculada**, no
  asumida.
- Guard determinista de ASTRA: `verdict_suspect: false`, 3/3 checks.

**Conclusión para esta familia: la NEC se viola en la pared.** Y como la NEC
es la más débil de las condiciones puntuales, WEC, DEC y SEC fallan también
en `p`.

Lectura física: el término constante de `N(s)` es positivo (≈ +0.447), pero
los coeficientes cuadráticos son negativos, y **domina el radial**
(≈ −0.613 en `s₂`, frente a −0.157 en `s₁` y `s₃`). Los rayos nulos radiales
en la pared son los que ven densidad de energía negativa.

## Alcance: qué NO dice este resultado

1. **No dice que toda onda viajera warp viole las CE.** Decide una familia
   concreta —perfil suave con factor conforme `ψ = 1 + f/5`— en un punto.
2. **No contradice a Fuchs et al. 2024.** Esa construcción de velocidad
   constante con materia ordinaria satisface las CE, pero es una
   configuración **distinta**: una *cáscara* de materia con interior plano,
   no un perfil conforme suave. La lección es justamente esa: el ansatz suave
   ingenuo falla donde la estructura de cáscara funciona.
3. **No cierra el programa de la onda viajera.** La pregunta abierta sigue
   siendo si existe un modo viajero del sistema acoplado Einstein-materia con
   precursor → cavidad plana → wake; este resultado **poda una rama**, que es
   trabajo útil pero negativo.

## Cierre: la cadena completa (ciclo `cycle_20260814_120554_ab9d`, 12:40)

Tercer intento, ya con la conjetura vallada como dato y la contabilidad de
fases arreglada. **El ciclo completó la cadena entera** en 2013 s:

| fase | s |
|---|---|
| conjetura | 176 |
| traducción | **696** |
| revisión | 345 |
| parche del validador | **658** |
| ejecución | 27 |
| análisis | 53 |
| navegación | 57 |

- Validador de **250 líneas**, **15/15 CHECK OK**, `VERDICT: PASS`, oráculo
  `PASS`, guard determinista limpio (`verdict_suspect: false`, 44
  comparaciones, 0 asserts).
- **Revisión independiente real**: el revisor (`gpt-5.6-sol`) devolvió primero
  `REVISE` con las etiquetas `sampling_as_proof` y `missing_assumption` —exigió
  que la optimización numérica no contara como prueba— y solo aprobó tras un
  parche acotado que añadió el testigo exacto y la independencia de `R` de la
  tetrada. Un `APPROVED` precedido de un `REVISE` con causa es la señal que
  buscábamos.
- **Testigo exacto** `s_* = (0,-1,0)`, con
  `k_* = (8/9, 2/9, -100/121, 0)` futuro y nulo, y
  `q(s_*) = -23778856/143496441 < 0` ⟹ `m_{p_R} < 0` para todo `R > 0`.

### Contraste con el cálculo a mano

| | valor | ≈ |
|---|---|---|
| mínimo global (validador mío, minimización exacta de Lagrange) | −196091158785784⁄1172859407230599 | −0.167191 |
| testigo exacto (validador de ASTRA, estrategia distinta) | −23778856⁄143496441 | −0.165710 |

El testigo queda **por encima** del mínimo global, como debe ser, a un 0.9 %.
Dos validadores escritos por separado, con estrategias distintas —minimización
global frente a testigo exacto más criterio tipo S-lemma— coinciden en el signo
y guardan entre sí la desigualdad correcta. Esto es lo que faltaba esta
madrugada.

### Lo que ASTRA dice del claim original

`original_claim_verdict: INCONCLUSIVE`, y la razón es exactamente el alcance
que hubo que poner a mano en la sección anterior:

> P afirma que existe una solución Einstein-materia estable, subluminal y sin
> materia exótica con la estructura viajera solicitada; el testigo exacto
> refuta únicamente esta configuración explícita, sin probar ni excluir la
> existencia de otras configuraciones.

`goal_coverage: partial`, `goal_resolved: false`, con siete ítems diferidos
—entre ellos el minimizador global exacto, la clasificación Hawking-Ellis, la
estabilidad y la cavidad extensa—. El re-anclaje de veredicto funcionó: el
ciclo valida **su** conjetura y dice, por separado, que **la pregunta de Nelson
sigue abierta**.

Navegación propuesta: desacoplar el perfil radial del lapso `α` del shift
`β^i`, o introducir vorticidad en el shift, para romper la proporcionalidad
estricta que fuerza la violación en el plano transversal.

### Qué NO demuestra este ciclo

La fuga de plan-mode de `agy` **volvió a aparecer en la deliberación**, pero
esta vez la síntesis la filtró y **no llegó a la conjetura**. Es decir: la
valla no se ejerció en vivo en esta corrida. Que el ciclo saliera bien no es
evidencia de que la valla funcione —eso lo sostienen los tests conductuales, no
este run—.

Lo que sí queda medido: la traducción necesitó **696 s** y el parche **658 s**.
Con el techo por defecto de 480 s habría fallado otra vez. El techo importa
para física de investigación; lo que era falso es que fuera la causa del fallo
anterior.

Coste del ciclo: **3.09 USD** (traductor).

## Estatus epistémico, con precisión

> **Actualizado (12:40).** Lo que sigue describía el estado tras el primer
> ciclo. El tercero cerró la brecha: hay validador del traductor, revisión
> independiente con `REVISE` motivado antes del `APPROVED`, y coincidencia con
> el cálculo a mano. Se conserva el párrafo porque delimita qué valía y qué no
> valía el resultado de las 05:09.

El cálculo es evidencia ejecutable con certificado exacto, pero **no completó
la cadena de ASTRA**: el validador es mío, no del traductor, y por tanto
**ningún revisor independiente lo auditó**. El guard determinista no detectó
auto-confirmación, lo cual es necesario pero no suficiente. Para elevarlo a
veredicto certificado haría falta un ciclo con presupuesto de traducción
suficiente.

## Lo que este test enseñó sobre la herramienta

> **Corrección (2026-08-14, mismo día).** El párrafo siguiente era n=1 y quedó
> **refutado** por el reintento con techo de 1200 s
> (`ASTRA2_PLAN_ARTIFACT_INJECTION_20260814.md`): el traductor no fallaba por
> falta de tiempo sino por un artefacto de plan-mode de `agy` filtrado en la
> conjetura, y por agotar sus 64 000 tokens de salida en razonamiento interno.
> El límite que ataba era de tokens, no de segundos. Lo que sigue se conserva
> como registro de lo que se creyó, no como conclusión vigente.

El techo del traductor **es insuficiente para física de investigación real**.
Nuestro p90 de 431 s (`ASTRA2_PHASE_BUDGET_20260813.md`) se midió sobre casos
de benchmark mucho más ligeros; escribir un validador de Einstein exacto con
clasificación de Hawking-Ellis excede 480 s + 360 s de reintento.

Y un dato útil para calibrar: el cálculo correcto tarda **13 segundos**. Mi
primer intento —cargando expresiones simbólicas completas— fue **matado por
consumo de memoria** dos veces. La diferencia no es potencia de máquina sino
método: la curvatura en un punto depende solo de `g`, `∂g` y `∂²g` **en ese
punto**, así que hay que evaluar cada derivada al sustituir en lugar de
arrastrar funciones racionales gigantes. Un traductor con más tiempo pero el
mismo método habría fallado igual.
