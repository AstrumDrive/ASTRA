#!/bin/bash
# ForceCommand for members of the astra-queue group (installed as
# /usr/local/sbin/astra-queue-gate). Those accounts reach the ASTRA job manager
# and nothing else: no shell, no direct worker, no file transfer.
#
# Accepted requests:
#   "<python> .../astra_cluster_manager.py rpc"  what ASTRA sends with ASTRA_REMOTE_SCHEDULER=1
#   "info"                                       host, caller identity and engine list
# Anything else is refused with a JSON error and logged to syslog.
#
# See docs/ASTRUM_ACCESO_POR_USUARIO.md.
set -uo pipefail

SUDO=/usr/bin/sudo
RPC=/usr/local/sbin/astra-queue-rpc
SERVICE_USER=astrum

request="${SSH_ORIGINAL_COMMAND:-}"
rpc_pattern="(^|[[:space:]/])astra_cluster_manager\.py['\"]?[[:space:]]+rpc[[:space:]]*$"

if [[ "$request" =~ $rpc_pattern ]]; then
    exec "$SUDO" -n -u "$SERVICE_USER" "$RPC"
fi

if [[ "$request" == "info" ]]; then
    printf '{"action":"info"}' | "$SUDO" -n -u "$SERVICE_USER" "$RPC"
    exit $?
fi

logger -t astra-queue-gate -- "user=${USER:-?} refused request=${request:0:200}" 2>/dev/null || true
printf '%s\n' '{"error":"This ASTRUM account only reaches the ASTRA job manager. Use ASTRA with ASTRA_REMOTE_SCHEDULER=1, or run: ssh astrum info"}'
exit 2
