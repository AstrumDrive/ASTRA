# Contraste: preprint arXiv:2602.03837v3 ↔ ASTRA 2.0

Fecha: 2026-08-12

Fuente: D. P. Woodruff, V. Cohen-Addad et al. (Google Research + universidades),
*"Accelerating Scientific Research with Gemini: Case Studies and Common
Techniques"*, arXiv:2602.03837v3 [cs.CL], 6 mar 2026. 154 páginas. Leído
completo en las secciones metodológicas (§§1–3, 5, 6, 9, Fig. 3, Fig. 23) y
barrido dirigido del resto (casos de estudio de dominio).

Propósito de este documento: ser el insumo de diseño para decidir qué técnicas
del preprint se incorporan a ASTRA 2.0 y en qué etapa. **No modifica el
contrato congelado del primer corte** (`ASTRA2_IMPLEMENTATION_CONTRACT.md`);
cualquier adopción que toque prompts, síntesis o runtime pertenece a etapas
posteriores de `HANDOFF.md` §7 y requiere autorización explícita.

## 1. Qué es el preprint (y qué no es)

Es una colección de testimonios: investigadores expertos resolviendo problemas
abiertos reales (TCS, teoría de la información, física, economía) en
colaboración conversacional con una **versión interna** de Gemini Deep Think
(entrenamiento RL adicional, corpus curado, "long linear chain of interactive
verification calls" en la salida). De ahí destila un "playbook" (§2) y un caso
de lazo automatizado (§6.1).

No es un paper de sistemas: no hay benchmark, ni pipeline reproducible, ni
métricas comparativas, ni acceso al modelo usado. Las técnicas transfieren;
la capacidad bruta del modelo interno no. Nuestra arquitectura usa CLIs de
suscripción (Codex, Claude, agy) — la expectativa de rendimiento debe
calibrarse con nuestros propios benchmarks, no con sus testimonios.

Punto clave que el propio paper admite (§9.1): los problemas con "extremely
long, sparse reward horizons without intermediate feedback" **exceden la
autonomía de los modelos actuales** y requieren orquestación humana. ASTRA 2.0
existe exactamente para fabricar ese feedback intermedio (ledger de evidencia
por episodio); el preprint confirma el diagnóstico de fondo.

## 2. Lo que el preprint VALIDA del diseño ya congelado

| Decisión ASTRA/2.0 ya tomada | Confirmación en el preprint |
|---|---|
| Ciclo atómico traducir→revisar→ejecutar→auditar con re-inyección de errores (repair vNext.1) | §2.6 y §6.1: el lazo "neuro-simbólico" (propuesta simbólica → código → traceback re-inyectado → poda) es su técnica estrella; es estructuralmente el ciclo ASTRA |
| `NUMERICAL_INSTABILITY` ≠ refutación (cinco ejes; clases de fallo) | §6.1: los métodos 1–3 eran *matemáticamente correctos* pero numéricamente inestables (cancelación O(e^{Nπ})); la inestabilidad podó el método, no refutó la matemática. Validación externa directa de nuestro eje |
| "Un PASS impreso no es autoridad" + revisión independiente pre-oráculo | §3.2: el hallazgo del fallo en SNARGs requirió revisor adversarial explícito; una lectura estándar produce "superficial reviews or hallucinations" |
| `ATOMIC_VALIDATED` / PARTIAL / deferred obligations | Fig. 23: contrato "Outcome 1: COMPLETE PROOF / Outcome 2: STRUCTURED PARTIAL PROGRESS (Proven Lemmas / The Crux / Next Steps)" — es nuestra misma separación con otros nombres |
| Evidencia por tipo de claim (contraejemplo exacto refuta universal; muestreo no prueba) | §2.3 y §3.1: refutación de la conjetura de Korula et al. con contraejemplo mínimo exacto (n=3, m=2) verificado exhaustivamente |
| Ruta Lean/formalización para obligaciones decisivas | §9.3: "the natural evolution of this workflow is Formal Verification... autoformalization pipelines (Lean, Coq, Isabelle)" |
| El modelo más fuerte reservado para verificación de milestone | §6.1 "Hierarchical Refinement": pasar el resultado ganador a un modelo mayor sin restricciones halló un descuido algebraico y telescopó la serie a forma cerrada |
| Preservar propuestas minoritarias como ramas (portafolio) | §6.1 "Methodological Diversity": seis métodos analíticos distintos para la misma integral; la diversidad metodológica fue lo que produjo la solución exacta (método 6) |

Conclusión: **ninguna decisión congelada del primer corte queda contradicha
por el preprint.** Al contrario: las dos apuestas más discutibles de la
revisión arquitectónica (separación inestabilidad/refutación y escalada solo
en milestones) aparecen como lecciones ganadas por el equipo de Google.

## 3. Técnicas rescatables, con etapa y coste

Ordenadas por relación valor/riesgo para los tres objetivos de Nelson:
resolución lógica (RL), menos alucinaciones (MA), mejor investigación (MI).

### R1. Prompting neutro "prove or refute" — MA, coste mínimo

§8.1/§9.2: sesgo de confirmación documentado — el modelo tiende a "probar" lo
que el prompt presupone, con argumentos "hand-wavy". El prompting neutro
mejora significativamente el rigor. **Acción**: auditar los prompts de
conjetura/síntesis/traducción de `agents/*.py` para verificar que ningún
prompt presuponga la verdad del claim; regla de estilo permanente. Toca
prompts → requiere autorización, pero es la adopción más barata y de mayor
retorno anti-alucinación.

### R2. Auto-corrección iterativa del revisor — MA, coste bajo

Fig. 3 (protocolo SNARGs): (1) revisión inicial objetiva, (2) autocrítica
buscando alucinaciones propias, (3) revisión revisada, (4) segunda ronda,
(5) revisión final. Con ese protocolo el modelo encontró un fallo fatal
(consistencia perfecta vs. estadística) que la revisión humana inicial no vio.
**Acción**: extender el prompt del revisor Codex con rondas de autocrítica.
Cautela vNext.1: mantener la calibración de que una sospecha de API no
ejecutada no puede bloquear (regresión EinsteinPy) — la autocrítica debe
reducir falsos positivos, no añadirlos. Medible de inmediato con
`benchmark_validator_repair.py` y los casos de regresión de auditoría.

### R3. Contrato "Crux" en el resultado parcial — RL, coste mínimo

Fig. 23 añade a nuestro PARTIAL dos campos que hoy no exigimos: **The Crux**
(exactamente dónde se atasca la prueba) y **Next Steps** (estrategias para
cerrar el hueco). Nuestro parsing de deferred captura pendientes, no el punto
exacto de bloqueo. **Acción**: exigir "crux" en el formato de salida del
analista; mapearlo a `unresolved_obligations` del Claim del primer corte. Da
al Navigator un objetivo discriminante preciso para el siguiente ciclo.

### R4. Negative prompting para diversidad metodológica — MI, coste medio

§6.1: tras hallar una ruta válida, "DO NOT use this method. Reflect on your
plan and try a different plan" produjo seis métodos independientes. Encaja
exactamente con nuestros campos `method_family` y `material_difference` del
Branch: al promover una alternativa tras evidencia negativa (o al buscar
independencia metodológica tras un SUPPORTS), el prompt de propuesta debe
**prohibir explícitamente las familias ya exploradas**. Es la versión
operativa del gate `no_exhausted_duplicate` del primer corte. Etapa 1 de §7
(portafolio estructurado).

### R5. Ancla numérica congelada por campaña — MA+RL, coste medio

§6.1: cada nodo del tree search se puntuó contra una **línea base numérica de
alta precisión** fijada de antemano; la poda barata eliminó >80% de ~600
ramas antes de gastar razonamiento caro, y el traceback/inestabilidad se
re-inyectó como feedback. **Acción**: para campañas de derivación, registrar
al inicio un Evidence de referencia (kind NUMERICAL, con su metadata de
precisión obligatoria del primer corte) que toda rama simbólica debe
reproducir; el gate `feasible_evidence_plan` ya puede exigirlo como "evidencia
discriminante más barata". Etapas 2–3 de §7 (episodios + widening).

### R6. Episodio de escalada en milestone — MI, coste medio

§6.1 "Hierarchical Refinement": verificación + simplificación por el modelo
más capaz, solo sobre resultados candidatos a cerrar un deliverable. Ya está
en la revisión arquitectónica como política; falta materializarlo como tipo de
Episode con presupuesto propio cuando se envuelva `astra_cycle` (etapa 2 de
§7). El caso del preprint muestra el retorno: equivalencia entre métodos y
forma cerrada que el lazo restringido no vio.

### R7. De-identificación de contexto — MA, coste bajo

§2.7/§9.2: el modelo a veces rehúsa atacar un problema si reconoce que es
"abierto", o evita maquinaria no elemental por conservadurismo; quitar la
identidad del paper (solo statement + definiciones) lo desbloquea. **Acción**:
flag opcional al construir el brief de un Episode: presentar el claim atómico
sin procedencia. Compatible con nuestro requisito de statement autocontenido
del Claim. Etapa con prompts.

### R8. Obligaciones LITERATURE verificadas — MA+MI, coste medio

§2.5: pedir al modelo la lista de teoremas externos de los que depende la
prueba, verificarlos fuera (fuente real), y re-generar la prueba
autocontenida con los enunciados verificados. Mapea a nuestro Evidence kind
`LITERATURE` (metadata `source` obligatoria del primer corte) y al eje de
obligaciones del Claim. Etapas 2–3.

### R9. Modo "revisor de papers" con el protocolo SNARGs — uso aparte

§3.2 + §9.4: Google ya usa esto para dar feedback a autores de STOC. Nelson
ya usa ASTRA para revisar manuscritos propios; el protocolo de Fig. 3 es
directamente aplicable a ese modo de uso hoy, sin tocar ASTRA 2.0.

## 4. Lo que NO se adopta (y por qué)

1. **MCTS de recompensa escalar a nivel de campaña.** El tree search del
   preprint es *intra-derivación*, puntuado contra una verdad numérica
   determinista — epistémicamente seguro. Eso no habilita un MCTS genérico de
   ramas de investigación con recompensa aprendida, que la revisión
   arquitectónica ya rechazó (§3 de la revisión). La lectura correcta es de
   dos niveles: campañas con gates duros + vector de prioridad visible
   (grueso), y poda numérica barata dentro del validador/episodio (fino).
2. **"Vibe-proving" humano como modo por defecto.** Los éxitos del preprint
   son de orquestación humana intensiva. ASTRA 2.0 apunta a autonomía con
   evidencia intermedia; el humano entra por heartbeat/milestone y como
   `HUMAN_REVIEW`, no como director por turno.
3. **Expectativas del modelo interno.** Parallel thinking, RL matemático
   adicional y cadena larga de verificación en salida no están en nuestros
   CLIs. Adoptamos protocolos, no presuponemos capacidades.
4. **El PDF no entra al repo.** Material de terceros; se cita por arXiv id.

## 5. Hipótesis medibles (pre-registrables cuando toque)

Con los benchmarks ya congelados (calidad, repair, trayectoria):

- **H1 (R1, MA)**: el prompting neutro reduce la aceptación falsa (métrica de
  veto de release de la suite de calidad) sin reducir la validación correcta.
- **H2 (R2, MA)**: la revisión con autocrítica iterativa aumenta la detección
  de defectos reales sin aumentar el bloqueo falso (casos de regresión de
  auditoría + `benchmark_validator_repair.py`).
- **H3 (R4, MI)**: el negative prompting aumenta preservación de ramas,
  diversidad de familias y recuperación tras evidencia negativa a presupuesto
  igual (benchmark de trayectoria, `full` vs variante).
- **H4 (R5, RL/MA)**: el ancla numérica congelada reduce llamadas de modelo
  por evidencia creíble en campañas de derivación.

Ninguna de estas hipótesis se considera evidencia hasta correr bajo protocolo
congelado con fingerprint, conforme a `RESEARCH_TRAJECTORY_BENCHMARK.md` y
`PUBLICATION_POLICY.md`.

## 6. Recomendación

Para la etapa 1 de §7 (portafolio estructurado, pendiente de autorización):
incorporar R3 y R4 al diseño del portafolio (son campos y reglas, no cambios
de runtime), y R1 como auditoría de prompts en la misma etapa. R2 puede ir en
una mini-etapa propia con el benchmark de repair como gate. R5–R8 esperan a
las etapas 2–3. R9 es un uso operativo de producción, independiente de 2.0.
