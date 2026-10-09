# ASTRUM: acceso por persona al gestor de trabajos

Diseño del acceso de colaboradores a un nodo ASTRUM compartido. Los datos
concretos de cada instalación (host, direcciones, claves, decisiones del
equipo) no están en este repositorio público; el administrador los guarda
aparte.

## 0. Resumen

Cada colaborador entra al nodo con **su propia cuenta Linux y su propia clave**.
Esas cuentas no tienen shell ni `sudo`: lo único que pueden hacer por SSH es
hablar con el gestor de trabajos (enviar, consultar, cancelar lo suyo, ver la
capacidad y `info`). El gestor toma la identidad **del usuario SSH
autenticado**, no del `client_id` que manda el cliente, aplica cuotas por
persona y solo deja cancelar los trabajos propios. La cuenta de servicio
(`astrum`) queda para el gestor y para el administrador.

El cliente ASTRA no necesita cambios de código para esto: con
`ASTRA_REMOTE_SCHEDULER=1`, todas sus rutas remotas pasan por un único comando
(`astra_cluster_manager.py rpc`).

## 1. Por qué

Con una sola cuenta compartida:

- `rpc` abre `state.db` como el usuario que entra por SSH, así que cualquier
  cuenta separada necesitaría escribir en la base del gestor;
- el `client_id` lo declara el cliente y `cancel` no comprueba dueño: el
  registro no distingue quién envió o canceló cada trabajo;
- cualquiera con acceso puede ejecutar cálculos fuera de la cola;
- el runner fijaba `OMP/MKL/OPENBLAS_NUM_THREADS = cpu_slots`, de modo que un
  `mpirun` de N procesos abría N × `cpu_slots` hilos.

## 2. Modelo de amenaza

Equipo pequeño de confianza. Objetivos: atribución de cada envío y cancelación,
evitar accidentes (cancelar lo ajeno, correr fuera de la cola), cuotas por
persona y que la cuenta de administración no sea el atajo diario. No es
objetivo de este nivel aislar a un usuario malicioso (§3.7).

## 3. Diseño

### 3.1 Cuentas

- Grupo `astra-queue` con una cuenta por colaborador. Sin `sudo`, sin
  contraseña (`adduser --disabled-password`), shell `/bin/bash` (sshd ejecuta
  la orden forzada a través de la shell del usuario).
- La cuenta de servicio sigue siendo la del gestor y la del administrador.

### 3.2 SSH — `remote/sshd_astra_queue.conf` → `/etc/ssh/sshd_config.d/10-astra-queue.conf`

- `PasswordAuthentication no`: por SSH solo se entra con clave. La contraseña
  de la cuenta de servicio sigue sirviendo en la consola física y para `sudo`.
- Claves en `/etc/ssh/authorized_keys/<usuario>` (root): ni los colaboradores
  ni un trabajo que corra como la cuenta de servicio pueden añadir claves.
- `Match Group astra-queue`: `ForceCommand` a la puerta, sin TTY, sin reenvío
  de puertos, agente, X11 ni túneles; también bloquea `scp` y `sftp`.
- El prefijo `10-` importa: en sshd gana el primer valor leído y los drop-ins
  se leen por orden de nombre.

### 3.3 La puerta — `remote/astra_queue_gate.sh`

| Lo que pide el cliente | Qué hace la puerta |
|---|---|
| `… astra_cluster_manager.py rpc` | `sudo -n -u astrum` al wrapper del gestor (el JSON sigue por stdin) |
| `info` | hostname, identidad y lista de motores |
| cualquier otra cosa | JSON de error, salida 2, registro en syslog (`astra-queue-gate`) |

La cadena pedida solo se compara con un patrón; nunca se ejecuta.

### 3.4 `sudo` acotado — `remote/sudoers_astra_queue` y `remote/astra_queue_rpc.sh`

El grupo puede ejecutar como la cuenta de servicio un único wrapper sin
argumentos, con `env_reset`. El wrapper comprueba que `SUDO_USER` pertenece al
grupo y fija `ASTRA_AUTHENTICATED_CLIENT` con ese valor, que el llamador no
puede elegir.

### 3.5 Gestor — `remote/astra_cluster_manager.py`

1. **Identidad autenticada**: sustituye el `client_id` del envío y el
   solicitante de la cancelación; los campos con `_` los pone solo el gestor.
2. **Cancelar solo lo propio**, salvo los administradores
   (`ASTRA_CLUSTER_ADMINS`) y la cuenta de servicio.
3. **Cuotas** en `cluster/quotas.json` (plantilla `remote/quotas.example.json`):
   slots de CPU y GPU en ejecución y trabajos en cola, con valores por defecto y
   por cliente. Sin fichero no hay cuotas; un fichero mal formado las desactiva
   y lo informa `astra_cluster_capacity`.
4. **`threads_per_process`** para códigos MPI (`mpirun`, `pw.x`, `ph.x`).
5. **`info`**: host, identidad del llamador y motores.

Pruebas: `tests/test_cluster_manager.py` y `tests/test_astra_queue_gate.py`.

### 3.6 Lado cliente

`.ssh/config` con `User <cuenta propia>`, `.env` con
`ASTRA_REMOTE_SCHEDULER=1`, y prueba con `ssh astrum info`. En Windows,
`scripts/setup_windows_collaborator.ps1` lo deja todo configurado.

### 3.7 Riesgo residual

Los trabajos siguen corriendo como la cuenta de servicio, así que un trabajo
puede leer o modificar lo que esa cuenta posee. No puede añadir claves SSH ni
usar `sudo`, y su código queda en `request.json`. El siguiente nivel lanza cada
trabajo como el usuario que lo envió, con directorios y base de datos aislados.

## 4. Despliegue

1. Copiar solo `astra_cluster_manager.py` al nodo (con copia de seguridad),
   comprobar su sha256 contra el commit y reiniciar el servicio de usuario.
   `remote/deploy_worker.ps1` copia también el worker.
2. Copiar los ficheros de cola y ejecutar `setup_astra_queue_access.sh`: por
   defecto muestra el plan; `--apply` instala con validación (`visudo`,
   `sshd -t`, configuración efectiva con `sshd -T`); `--add-key` autoriza una
   clave; `--rollback --apply` deshace las reglas de sshd y sudo. Mantener
   abierta una sesión de administrador hasta comprobar una conexión nueva.
3. Verificar: shell, `scp`, reenvío y contraseña rechazados; identidad forzada;
   cancelación ajena rechazada; cuotas cargadas.
