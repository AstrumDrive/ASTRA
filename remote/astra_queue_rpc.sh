#!/bin/bash
# Runs the ASTRA job manager's rpc as the service account on behalf of an
# astra-queue member (installed as /usr/local/sbin/astra-queue-rpc, root-owned).
# Reached only through the sudoers rule in /etc/sudoers.d/astra-queue, which
# resets the environment and keeps SSH_CONNECTION. The caller's identity is
# SUDO_USER, which sudo sets itself and the caller cannot choose.
set -euo pipefail

SERVICE_HOME=/home/astrum
WORKER_DIR="$SERVICE_HOME/astra-worker"
QUEUE_GROUP=astra-queue

fail() {
    printf '{"error":"%s"}\n' "$1"
    exit 2
}

caller="${SUDO_USER:-}"
[[ -n "$caller" && "$caller" != "root" ]] || fail "astra-queue-rpc must be reached through sudo by an astra-queue member"
id -nG -- "$caller" 2>/dev/null | tr ' ' '\n' | grep -qx "$QUEUE_GROUP" || fail "user $caller is not in $QUEUE_GROUP"

export HOME="$SERVICE_HOME"
export ASTRA_AUTHENTICATED_CLIENT="$caller"
export ASTRA_CLUSTER_ROOT="$WORKER_DIR/cluster"
# Same node limits as astra-cluster-manager.service, so admission at submit time
# matches what the scheduler enforces.
export ASTRA_CLUSTER_CPU_RESERVE=4
export ASTRA_CLUSTER_GPU_SLOTS=1
export ASTRA_CLUSTER_MEMORY_RESERVE_MB=4096
umask 0077
cd "$WORKER_DIR"
exec "$WORKER_DIR/venv/bin/python" "$WORKER_DIR/astra_cluster_manager.py" rpc
