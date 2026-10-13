# Inventario: qué tiene ASTRA 2.0 que producción no

13 de octubre de 2026 · producción `02e80eb` (1.1.10) · ASTRA 2.0 `588bdf6`
(rama `astra-2.0`, último commit el 7 de septiembre)

## Método

ASTRA 2.0 salió de producción en `e4752ea` (6 de agosto). Desde entonces:

- **2.0 tiene 160 commits.** Solo uno está en producción como parche idéntico (`git cherry`).
- **Producción tiene 119 commits** que 2.0 no tiene.

Como muchos arreglos se portaron a mano o se reescribieron, la comparación se
hizo por contenido, en tres pasos:

1. **Archivos.** Se compararon los 150 que 2.0 cambió, excluyendo evidencia y
   benchmarks:
   - 19 son idénticos en producción;
   - 82 existen solo en 2.0;
   - 40 cambiaron en las dos líneas;
   - 9 cambiaron solo en 2.0.
2. **Funciones.** Cada test exclusivo de 2.0 importa las funciones que
   verifica; se comprobó si esas funciones existen en producción.
3. **Arreglos sin test propio.** Se buscó en producción la línea clave de cada
   uno.

Ningún paso gastó cuota de modelos.

## A. Arreglos del motor de ciclo que producción no tiene

Todos fueron verificados como ausentes en `02e80eb`.

| # | Arreglo (commit en 2.0) | Qué evita | Prioridad |
|---|---|---|---|
| A1 | Pedido y salida de los oráculos leídos como UTF-8, no con el código de página de Windows (`865ec03`, `d646551`, `588bdf6`) | Producción lee el pedido con `json.load(sys.stdin)` y captura varios oráculos con `text=True` sin `encoding`: un `∀` o una tilde llegan corruptos | Alta |
| A2 | Si el reparador del traductor agota su tiempo, reintenta una vez en el peldaño siguiente (`085d07e`, `4f39f71`) | Hoy solo se baja de peldaño por cuota; con `ultra` (1.1.9), un tiempo agotado mata la fase | **Alta ahora** |
| A3 | Lean ejecuta `main`, de modo que una prueba verificada por el kernel imprime su veredicto (`6b448b0`) | Una prueba correcta que nunca imprime VERDICT | Alta si se usa Lean |
| A4 | El filtro de `sorry`/`admit`/`axiom` ignora los comentarios de Lean (`2cb3917`) | Rechaza pruebas sanas que mencionan esas palabras en un comentario | Alta si se usa Lean |
| A5 | La sonda que decide si Sage, Maxima o Cadabra están disponibles por WSL espera hasta 60 s el arranque en frío (`8f2d0c1`) | Producción le da 10 s (`core/engine_router.py`, líneas 56 y 72): con WSL frío, un validador de Sage sale como error operativo "sage is not available". El doctor del 12-oct, con su propia sonda de 15 s, ya vio WSL sin responder a tiempo | Media |
| A6 | Reintentar un lanzamiento de CLI transitorio (WinError 5 de un antivirus o de un CLI que se re-arma) en vez de fallar la fase (`bcffa0a`) | Fases perdidas por un error del sistema operativo | Media |
| A7 | Un parche mal formado no destruye un validador ya aprobado que pasó (`1a99f89`) | Perder un ciclo bueno por un parche inválido | Media |
| A8 | Reglas 17-18 del revisor: exigir la carga de prueba de la pregunta decisiva, no de una compañera más fuerte; la regla 17 nunca abre la compuerta (`a1c2128`) | Rondas de revisión que piden demostraciones innecesarias. Destrabó el caso linalg en la corrida 11 sin aceptaciones falsas | Media; se porta por significado, porque la numeración del revisor de producción ya divergió |
| A9 | La conjetura va cercada como dato en la entrada del traductor (`49d644d`) | Que una frase de la conjetura se lea como instrucción. En 2.0 una frase filtrada destruyó un ciclo | Media |
| A10 | Desperdicio de la salida (`39d7a7d`): reintento cuando el traductor devuelve prosa en vez de código, limpieza de artefactos de modo plan y tope de pensamiento de Claude | Ciclos que gastan toda la salida sin producir código | Media; el tope de pensamiento hay que repensarlo con `--effort` (1.1.9) |
| A11 | Los validadores de Sage terminan solos en la ruta de éxito, sin `sys.exit(0)` (`a345fa4`) | Sage reporta `SystemExit` como salida distinta de cero: un PASS impreso se vuelve error operativo | Media |
| A12 | Chequeo dimensional invocable y enganchado al guardia de veredicto (`87efbe9`, `8c4b7ef`) | Errores de unidades que pasan como PASS | Baja: capacidad nueva, 2.0 pidió medir antes de usarla como compuerta |

## B. Capa de campañas

Producción ya tiene la capa de campañas, portada el 22 de agosto (`a40fefd`)
y apagada por defecto (`ASTRA_CAMPAIGN_TOOLS`):

- **Idénticos en producción:** `campaign_api`, `campaign_portfolio`,
  `campaign_resume` y `campaign_store`.
- **Más nuevo en 2.0:**
  - límite de la ruta fallida y cota declarada de toda aproximación (`80f3334`, `ApproximationSpec`);
  - métricas de trayectoria de campaña (`campaign_trajectory_metrics.py`).
- **Cambiados en las dos líneas, hay que reconciliarlos:** `campaign_decision`,
  `campaign_executor`, `campaign_models` y `campaign_policy`.

## C. Solo arnés de benchmarks

Nada de esto hace falta para usar ASTRA:

- reintentos y tiempos de los pilotos externos;
- colas ante un modelo ocupado;
- casos de la suite de calidad;
- interruptores de ablación de G4;
- verificador de deriva entre líneas, escáner de secretos y corredor del canario.

Se portan solo si se vuelven a correr esos benchmarks desde producción.

## D. Presupuesto del ciclo: diseño distinto, no portar tal cual

2.0 reparte el tiempo por fracción del restante (`PHASE_BUDGET_SHARE`,
`PHASE_DOWNSTREAM_RESERVE`, techos persistentes). Producción resolvió lo mismo
por otro camino:

- mínimos útiles por fase (1.1.1);
- chequeo del analista (1.1.6);
- recuperación de tiempos agotados (1.1.7).

Se toman las lecciones medidas en 2.0, no el código. Hay dos con datos: la
corrida 10, y que más pared no salva una reparación que no cabe en una
llamada.

## E. Lo que 2.0 no tiene de producción

En 119 commits, que 2.0 no tiene:

- re-anclaje del veredicto a la pregunta original (`original_claim_verdict`);
- corpus de una proposición por caso (47 de 50) y la entrada completa para el autor;
- NON_DECIDABLE y las preguntas de convención;
- aritmética certificada (Arb);
- recuperación de tiempos agotados;
- cuentas por persona en ASTRUM;
- transporte SSH resistente a caídas (1.1.8);
- escaleras `modelo@esfuerzo` con GPT-6.1 Sol, Opus 5.5 y Gemini 3.8 Flash (1.1.9);
- agy aislado y de solo texto (1.1.10);
- perfil `full` con las tres CLI.

## Recomendación

1. **Portar A1, A2 y A5 a A11 a producción** como 1.1.11, cada uno con el test
   que ya trae de 2.0 adaptado. A3 y A4 entran también si Lean sigue en uso.
   A12 va detrás de un interruptor, para medirlo.
2. **Reconciliar la capa de campañas (B)** cuando se decida encenderla para uso
   propio.
3. **Archivar 2.0 como laboratorio.** Sus compuertas, evidencia y documentos
   quedan como referencia, y el desarrollo sigue en producción.
