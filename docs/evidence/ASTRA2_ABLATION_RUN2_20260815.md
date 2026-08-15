# Ablación, corrida 2: la reserva funcionó, el lanzador la arruinó (2026-08-15)

Reanudación de `research_trajectory_20260814_190454` con la reserva de
presupuesto y el presupuesto congelado ya corregidos. 19 ciclos, 8 celdas.
`operational_failure_rate` = **0.9167 en ambos brazos**, igual que antes.

**Ese número no mide ASTRA. Mide cómo lancé la corrida.**

## El corte es limpio

| contexto de ejecución | ciclos | VALIDATED | `[WinError 5] Access is denied` |
|---|---|---|---|
| interactivo (14-ago, 19:23-21:34) | 9 | **2** | **0** |
| Programador de tareas (15-ago, 08:47-09:53) | 10 | **0** | **10** |

Los diez ciclos ejecutados bajo el Programador de tareas fallaron **en el
lanzamiento** del CLI de codex:

```text
API_ERROR: 'gpt-5.6-sol': lanzamiento fallo: [WinError 5] Access is denied
```

No es cuota ni timeout: es un fallo del sistema operativo al crear el proceso,
antes de que el modelo exista. Comprobado tras el hecho, **desde una sesión
interactiva el mismo CLI responde sin problema** (`ok=True`, `ALIVE`).

Encaja con lo ya sabido del sandbox de Codex en Windows
(`reference_codex_windows_sandbox.md`): codex lanza procesos bajo cuentas
`CodexSandbox*`, y ese mecanismo no sobrevive al contexto del Programador de
tareas —token interactivo limitado, sin escritorio real—.

**Conclusión operativa: el benchmark no se puede correr desde el Programador de
tareas.** La independencia de sesión que buscaba costó exactamente lo que
pretendía proteger.

## Lo que sí quedó medido: la reserva funciona

De los 9 ciclos limpios (contexto interactivo, ya con la reserva y los 1800 s):

| | corrida 1 (sin reserva) | corrida 2, tramo limpio |
|---|---|---|
| presupuesto de ciclo | 1500 s | **1800 s** |
| fallos en `translator_repair` | **8 de 15** | **1 de 9** |
| timeouts de reparación | 12, mediana 165 s | 1, de 193 s |

La reparación deja de ser la primera causa de fallo. Con n=9 es señal
direccional, no prueba; pero la dirección es la que predecía el arreglo.

## Qué se salva y qué no

| caso | configuración | semilla | ciclos limpios | envenenados |
|---|---|---|---|---|
| `gr_invariant_audit` | full | 11 | 3 | 0 |
| `gr_invariant_audit` | full-linear | 11 | 3 | 0 |
| `gr_invariant_audit` | full-linear | 29 | 2 | 0 |
| `gr_invariant_audit` | full | 29 | 1 | 2 |
| `growth_model_discrimination` | los 4 | 11, 29 | **0** | 2 cada uno |

Tres celdas de `gr_invariant_audit` están completas y limpias. El caso
`growth_model_discrimination` está **enteramente envenenado**: sus cuatro celdas
se ejecutaron en su totalidad bajo el Programador de tareas.

## Dos defectos reales que la corrida sí destapó

1. `ValueError: ASTRA subprocess emitted no JSON object` (×2, contexto
   interactivo): el runner no obtuvo JSON del subproceso. Sin diagnóstico
   todavía; no se puede distinguir un cuelgue de una salida corrupta porque el
   stdout crudo no se conserva cuando el parseo falla.
2. Un timeout de codex a los **6 s** y otro a los **62 s**, muy por debajo de
   cualquier techo configurado. Sugiere que el árbol de procesos muere por otra
   causa y se reporta como timeout.

## Recomendación

Relanzar **en sesión interactiva**, apoyándose en `--resume`, que ya demostró
retomar sin perder trabajo. La corrida debe asumir que muere a la mitad; eso es
barato. Lo que no es aceptable es cambiar el contexto de ejecución a mitad del
experimento, que es lo que invalidó esta.

Antes de relanzar hay que **descartar los 10 ciclos envenenados**, no
reanudarlos: quedarían registrados como fallos operativos de la arquitectura.
