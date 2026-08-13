# ASTRA 2.0 — medición con repeticiones: el techo real es el ciclo (2026-08-13)

Autorización: Nelson eligió la opción 3 (medir con repeticiones antes de
tocar nada).

Diseño: los cuatro casos con firma de bloqueo del revisor, **3 repeticiones
cada uno** (12 ciclos), configuración actual con
`ASTRA_TRANSLATOR_TIMEOUT=480` y `--cycle-timeout 3600`. Informe:
`quality_20260813_153418.json`.

## Taxonomía de los 12 ciclos

| Mecanismo | Ciclos |
|---|---|
| **Presupuesto TOTAL del ciclo agotado (1440 s)** | **6** |
| Bloqueo del revisor | 2 |
| Reparador acotado que falla | 1 |
| Veredicto correcto (REFUTED / VALIDATED) | 2 |
| INCONCLUSIVE (veredicto honesto, no fallo) | 1 |

Por caso:

```text
algebra_cancellation      REFUTED(758s)   INCONCLUSIVE(1441s)  TIMEOUT(1443s)
gr_schwarzschild_nonzero  REVISOR(908s)   TIMEOUT(1446s)       TIMEOUT(1467s)
quantum_density           TIMEOUT(1191s)  TIMEOUT(1446s)       TIMEOUT(1443s)
symbolic_polynomial       REVISOR(440s)   REPARADOR(913s)      VALIDATED(305s)
```

## Respuesta a la pregunta planteada

**El bloqueo del revisor NO es reproducible por caso: 2 de 12 ciclos, y nunca
dos veces en el mismo caso.** Es varianza del muestreo, no conducta
sistemática. Por tanto **el cambio estructural (opción 2) no está
justificado**; si acaso, la palanca proporcionada sería el reintento
(`ASTRA_REVIEW_MAX_REVISIONS=2`), y ni siquiera es hoy la causa dominante.

Esto es exactamente lo que la medición con repeticiones existía para decidir,
y contradice lo que habría concluido de las corridas con n=1.

## Hallazgo dominante: el techo de 1440 s del ciclo

Las duraciones se agrupan en 1441, 1443, 1445, 1446, 1466, 1442 s. No es
ningún techo de fase ni el revisor: es el **presupuesto total del ciclo**,
`astra_tool.py:1090` → `cycle_timeout_seconds or 1500`, menos 60 s de buffer
de retorno = **1440 s útiles**. El benchmark nunca fija
`cycle_timeout_seconds` en `cycle_request`, así que hereda ese default; y
`--cycle-timeout 3600` **no lo toca**, porque ese flag es el timeout del
subproceso, no el presupuesto interno.

## Corrección a mi recomendación anterior

`ASTRA_TRANSLATOR_TIMEOUT=480` **no debe adoptarse aislado**. Con la escalera
`claude-opus-4-8,sonnet`, la traducción puede consumir hasta 960 s de los
1440 s disponibles, dejando sin tiempo a revisión, reparación, oráculo y
auditoría. Es decir: subir el techo de fase movió el fallo desde "la fase
muere pronto" hasta "el ciclo entero se queda sin tiempo". Los dos parámetros
están acoplados y cambié uno solo.

La corrección coherente es una de estas, **ninguna adoptada**:

1. subir el presupuesto del ciclo para casos pesados (que el benchmark pase
   `cycle_timeout_seconds` explícito, p. ej. 2400–3000 s, en vez de heredar
   1500) **y** mantener el techo del traductor en 480;
2. dejar el ciclo en 1500 s y devolver el traductor a 240 s, aceptando que
   los validadores de física largos no caben;
3. medir la distribución del tiempo por fase en casos pesados y repartir el
   presupuesto con datos, en vez de por intuición.

Mientras no se decida, `.env.example` conserva `ASTRA_TRANSLATOR_TIMEOUT=480`
con esta advertencia añadida: **es beneficioso solo si el presupuesto total
del ciclo lo acompaña**.

## Advertencia metodológica

Estos 12 ciclos son un subconjunto **sesgado por construcción** (los casos
que ya fallaban). Sus tasas no se comparan con las de la suite completa. Lo
que sí sostiene es la conclusión de reproducibilidad por caso, que era la
pregunta.

Ninguna cifra de este documento es evidencia científica publicable
(`PUBLICATION_POLICY.md`).
