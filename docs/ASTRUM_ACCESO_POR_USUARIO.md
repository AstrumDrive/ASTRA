# ASTRUM: acceso por persona al gestor de trabajos

Diseño aprobado por Nelson (administrador único de ASTRUM) el 2026-10-08.
Implementación en la rama `claude/astrum-per-user-access`; el despliegue en
ASTRUM está pendiente (§4).

## 0. Resumen

Cada colaborador entra a ASTRUM con **su propia cuenta Linux y su propia clave**.
Esas cuentas no tienen shell ni `sudo`: lo único que pueden hacer por SSH es
hablar con el gestor de trabajos (enviar, consultar, cancelar lo suyo, ver la
capacidad y `info`). El gestor toma la identidad **del usuario SSH
autenticado**, no del `client_id` que manda el cliente, aplica cuotas por
persona y solo deja cancelar los trabajos propios. La cuenta `astrum` queda como
cuenta de servicio y de administración, con una sola clave remota: la de Nelson,
que sigue entrando como `astrum`.

El cliente ASTRA **no necesita cambios de código** para esto: con
`ASTRA_REMOTE_SCHEDULER=1`, todas sus rutas remotas ya pasan por un único
comando (`astra_cluster_manager.py rpc`).

## 1. Estado de partida verificado (2026-10-08)

| Hecho | Evidencia |
|---|---|
| Un solo usuario con shell además de root: `astrum`, miembro de `sudo` | `getent passwd`, `getent group sudo` |
| `sudo` pide contraseña (los trabajos no pueden escalar a root) | `sudo -n true` falla |
| **SSH acepta contraseña** además de clave | el servidor responde `Permission denied (publickey,password)` |
| `~astrum/.ssh/authorized_keys`: clave de Nelson y `astra-gabriel` | `ssh-keygen -lf` |
| Clave de Nelson: 21 848 inicios de sesión en 30 días, todos desde 100.66.61.113 | `journalctl -u ssh` |
| Clave `astra-gabriel`: 0 inicios de sesión en 30 días | `journalctl -u ssh` |
| La línea 1 de `authorized_keys` contiene la clave de Nelson duplicada dentro del comentario (un `\n` que se escribió como `n`); inocuo, se limpia al migrar | `awk` sobre el fichero: 5 campos |
| `rpc` abre `state.db` **como el usuario que entra por SSH** | `main()` → `rpc(store, …)` |
| `client_id` lo declara el cliente; `cancel` no comprueba dueño | `ClusterStore.submit`, `ClusterStore.cancel` |
| Cada trabajo corre como `astrum` | `_launch_runner` / `run_job` |
| El runner fija `OMP/MKL/OPENBLAS/NUMEXPR/VECLIB_NUM_THREADS = cpu_slots`; con `cpu_slots=12` y `mpirun -np 12` salen 144 hilos por trabajo | causa de la carga 127 del 2026-10-08 |
| Con `ASTRA_REMOTE_SCHEDULER=1` el cliente solo ejecuta `<python> astra_cluster_manager.py rpc` | `execute_remote_code` → `execute_cluster_code` → `cluster_rpc` |
| El gestor desplegado coincide con `remote/astra_cluster_manager.py` de `company/main` (215e33a…) | `sha256sum` |
| El worker desplegado (`astra_remote_worker.py`, 7d75d6b…) es el del árbol de trabajo **sin commit**, no el de `company/main` (609f6ab…) | `sha256sum` |

## 2. Modelo de amenaza

Equipo de tres personas de confianza. Objetivos:

1. **Atribución**: saber quién envió y quién canceló cada trabajo.
2. **Evitar accidentes**: que nadie cancele lo ajeno ni corra cálculos pesados
   fuera de la cola.
3. **Cuotas**: que una persona no ocupe todo el clúster.
4. **Cerrar el uso cómodo de `astrum`**: que la cuenta de administración no sea
   el atajo diario.

No es objetivo (todavía) aislar a un usuario malicioso. Ver §3.7.

## 3. Diseño

### 3.1 Cuentas

- Grupo `astra-queue` con `ivaylo` y `gabriel`. Sin `sudo`, sin contraseña
  (`adduser --disabled-password`), shell `/bin/bash` (sshd ejecuta la orden
  forzada a través de la shell del usuario; con `nologin` no funcionaría).
- `astrum` sigue igual: cuenta de servicio del gestor y de administración.
  Nelson sigue entrando como `astrum`; no hay cuenta de cola `nelson`.

### 3.2 SSH — `remote/sshd_astra_queue.conf` → `/etc/ssh/sshd_config.d/10-astra-queue.conf`

```sshconfig
PasswordAuthentication no

Match User astrum
    AuthorizedKeysFile /etc/ssh/authorized_keys/%u

Match Group astra-queue
    AuthorizedKeysFile /etc/ssh/authorized_keys/%u
    ForceCommand /usr/local/sbin/astra-queue-gate
    PermitTTY no
    AllowTcpForwarding no
    AllowStreamLocalForwarding no
    AllowAgentForwarding no
    X11Forwarding no
    PermitTunnel no
```

- El prefijo `10-` importa: en sshd gana el primer valor leído y los drop-ins
  se leen por orden de nombre, antes que un posible `50-cloud-init.conf`.
- `PasswordAuthentication no`: por SSH solo se entra con clave. La contraseña
  de `astrum` sigue sirviendo en la **consola física** (con Ivaylo) y para
  `sudo`. Es la vía de emergencia si Tailscale o SSH fallan; Ivaylo la conserva.
- Las claves pasan a `/etc/ssh/authorized_keys/<usuario>` (root, 0644): ni los
  colaboradores ni un trabajo que corra como `astrum` pueden añadir claves.
- `ForceCommand` ignora lo que pida el cliente y ejecuta siempre la puerta;
  también bloquea `scp` y `sftp`.

### 3.3 La puerta — `remote/astra_queue_gate.sh` → `/usr/local/sbin/astra-queue-gate`

| Lo que pide el cliente | Qué hace la puerta |
|---|---|
| `… astra_cluster_manager.py rpc` (lo que manda ASTRA) | `exec /usr/bin/sudo -n -u astrum /usr/local/sbin/astra-queue-rpc` (el JSON sigue por stdin) |
| `info` | manda `{"action":"info"}`: hostname, identidad y lista de motores |
| cualquier otra cosa, o sesión interactiva | JSON de error, salida 2, y registro en syslog (`astra-queue-gate`) |

La cadena pedida solo se compara con un patrón; nunca se ejecuta.

### 3.4 `sudo` acotado — `remote/sudoers_astra_queue` → `/etc/sudoers.d/astra-queue`

```sudoers
Defaults!/usr/local/sbin/astra-queue-rpc env_reset, env_keep += "SSH_CONNECTION", !use_pty, !lecture
%astra-queue ALL=(astrum) NOPASSWD: /usr/local/sbin/astra-queue-rpc ""
```

`remote/astra_queue_rpc.sh` → `/usr/local/sbin/astra-queue-rpc` comprueba que
`SUDO_USER` pertenece a `astra-queue`, fija `ASTRA_AUTHENTICATED_CLIENT` con ese
valor y ejecuta el `rpc` del gestor con el Python del venv y los mismos límites
de nodo que el servicio. `sudo` pone `SUDO_USER` y `env_reset` borra todo lo
demás, así que nadie puede suplantar a otro. El `""` prohíbe argumentos.

### 3.5 Cambios en el gestor — `remote/astra_cluster_manager.py`

1. **Identidad autenticada.** Si existe `ASTRA_AUTHENTICATED_CLIENT`, `rpc()`
   sustituye el `client_id` del envío y el solicitante de la cancelación, y lo
   anota (`auth=ssh-user`) en los eventos. Los campos que empiezan por `_` los
   pone solo el gestor; los que mande el cliente se descartan. Sin esa variable
   (entrada como `astrum`) el comportamiento no cambia.
2. **Cancelar solo lo propio.** Un cliente autenticado solo cancela trabajos con
   su `client_id`. Los administradores (`ASTRA_CLUSTER_ADMINS`, por defecto
   `nelson`) y la entrada como `astrum` cancelan cualquiera.
3. **Cuotas** en `~/astra-worker/cluster/quotas.json` (plantilla
   `remote/quotas.example.json`):

   ```json
   {
     "default": {"max_running_cpu_slots": 16, "max_running_gpu_slots": 1, "max_queued": 20},
     "clients": {"nelson": {"max_running_cpu_slots": 28}, "astra-2.0-dev": {"max_running_cpu_slots": 28}}
   }
   ```

   Sin fichero no hay cuotas. Un fichero mal formado desactiva las cuotas (no
   bloquea a nadie) y el error aparece en `astra_cluster_capacity`
   (`quotas_error`). `max_queued` y los topes por trabajo se aplican al enviar;
   los topes en ejecución, en `reserve_next`: si un cliente está en su tope, su
   trabajo espera y pasa el de otro. `astra_cluster_capacity` muestra el uso en
   curso por cliente (`per_client_running`).
4. **Hilos para MPI.** Campo opcional `threads_per_process` (también en la
   herramienta `astra_cluster_submit`). Fija `*_NUM_THREADS`; si falta, se
   mantiene un hilo por slot reservado. Para `mpirun`/`pw.x`/`ph.x`, enviar
   `threads_per_process=1`. Solo entra en el hash de idempotencia cuando se usa.
5. **`info`.** Hostname, identidad del llamador y lista de motores.
6. **Visibilidad.** Cada colaborador puede listar todos los trabajos y leer su
   salida (equipo de confianza).

Pruebas: `tests/test_cluster_manager.py` (19 nuevas) y
`tests/test_astra_queue_gate.py` (POSIX). Cada guarda nueva se comprobó
rompiéndola a propósito: las 9 mutaciones hacen fallar su prueba.

### 3.6 Lado cliente

- `.ssh/config` del colaborador: `User ivaylo` / `User gabriel`.
- `.env`: `ASTRA_REMOTE_SCHEDULER=1` es **obligatorio**. `ASTRA_CLIENT_ID` deja
  de importar para ellos: manda el usuario SSH.
- Prueba de conexión: `ssh astrum info` (las guías de Windows y macOS ya lo dicen).

### 3.7 Riesgo residual (aceptado)

Los trabajos siguen corriendo como `astrum`. Un trabajo puede leer o modificar
todo lo que `astrum` posee, incluido `state.db` y los ficheros de otros
trabajos. No puede añadir claves SSH (§3.2) ni usar `sudo` (pide contraseña).
El código de cada trabajo queda en su `request.json`: un uso indebido deja rastro.

**Nivel 2, cuando entre alguien de fuera:** el runner lanza el worker como el
usuario que envió (`sudo -u <usuario>` acotado para `astrum`), directorios de
trabajo por usuario, `state.db` solo accesible por `astrum`, y motores en una
ruta compartida de solo lectura.

## 4. Despliegue

Las fases 2 y 3 necesitan la contraseña de `sudo` de ASTRUM: las ejecuta Nelson.

| Fase | Qué | Verificación | Reversión |
|---|---|---|---|
| 1 | Rama con gestor, puerta, wrapper, sudoers, drop-in, cuotas, script y pruebas | suite en verde | descartar la rama |
| 2 | Copiar **solo** `astra_cluster_manager.py` a `~/astra-worker/` (con copia `.previous`) y `systemctl --user restart astra-cluster-manager`. **No** usar `deploy_worker.ps1`: copia `astra_remote_worker.py` de `company/main` y revertiría el worker desplegado | `astra_cluster_capacity` responde y muestra `per_client_running`; los trabajos en curso siguen (`KillMode=process`, runners en sesión propia) | restaurar `.previous` y reiniciar |
| 3 | Copiar los ficheros de cola a `~/astra-worker/queue-access/` y ejecutar `sudo bash setup_astra_queue_access.sh` (plan), revisar, y luego `--apply`, **con una sesión abierta** | el script valida `visudo` y `sshd -t`, comprueba la configuración efectiva con `sshd -T` y recarga; una conexión **nueva** `ssh astrum hostname` desde el PC de Nelson debe funcionar antes de cerrar la sesión | `sudo bash setup_astra_queue_access.sh --rollback --apply` |
| 4 | Matriz de pruebas (abajo) | todo en verde | — |
| 5 | Gabriel cambia a `User gabriel`; Ivaylo instala con `User ivaylo` y Nelson autoriza su clave con `--add-key ivaylo ivaylo.pub --apply` | primer trabajo de cada uno con su `client_id` en `state.db` | — |

Matriz de la fase 4:

- Nelson como `astrum`: `astra_status`, `astra_cluster_submit`, cancelar cualquier trabajo → OK.
- Cuenta de cola: `ssh astrum info` → hostname, identidad y motores; `astra_cluster_submit` → `client_id` = usuario SSH aunque el `.env` diga otra cosa.
- Cuenta de cola: `ssh astrum` interactivo, `ssh astrum id`, `scp`, reenvío de puertos → rechazados.
- Cuenta de cola: cancelar un trabajo de otro → rechazado; cancelar uno propio → OK.
- Cuenta de cola: superar `max_queued` → rechazado con mensaje claro.
- Contraseña por SSH contra cualquier cuenta → rechazada.
- `threads_per_process=1` con `cpu_slots=12` → `MKL_NUM_THREADS=1` dentro del trabajo.

## 5. Decisiones de Nelson (2026-10-08)

1. Cuotas: 16 slots de CPU en ejecución, 1 GPU y 20 en cola por persona; Nelson
   (y su cliente `astra-2.0-dev`) 28 de CPU.
2. Administrador del gestor: solo `nelson`.
3. Nelson sigue entrando como `astrum`; sin cuenta de cola propia.
4. Ivaylo conserva la contraseña de `astrum` para la consola física.
5. Los colaboradores pueden leer la salida de trabajos ajenos, por ahora.
