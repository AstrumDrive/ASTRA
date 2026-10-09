#!/usr/bin/env bash
# Per-person access to the ASTRA job manager on ASTRUM.
# Design and rationale: docs/ASTRUM_ACCESO_POR_USUARIO.md.
#
# Run from the directory that holds the remote/ queue files, with sudo:
#   sudo bash setup_astra_queue_access.sh                               # plan only, changes nothing
#   sudo bash setup_astra_queue_access.sh --apply                       # install
#   sudo bash setup_astra_queue_access.sh --add-key ivaylo ivaylo.pub   # plan
#   sudo bash setup_astra_queue_access.sh --add-key ivaylo ivaylo.pub --apply
#   sudo bash setup_astra_queue_access.sh --rollback --apply            # remove the sshd and sudo rules
#
# Keep the SSH session that runs --apply open until a NEW connection as astrum
# has worked from another terminal. Deploy the new astra_cluster_manager.py first:
# this script refuses to run against a manager without authenticated identity.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER=astrum
SERVICE_HOME=/home/astrum
WORKER_DIR="$SERVICE_HOME/astra-worker"
QUEUE_GROUP=astra-queue
QUEUE_USERS=(ivaylo gabriel)
GABRIEL_KEY_COMMENT=astra-gabriel
KEY_DIR=/etc/ssh/authorized_keys
GATE=/usr/local/sbin/astra-queue-gate
RPC=/usr/local/sbin/astra-queue-rpc
SUDOERS=/etc/sudoers.d/astra-queue
DROPIN=/etc/ssh/sshd_config.d/10-astra-queue.conf
HOME_KEYS="$SERVICE_HOME/.ssh/authorized_keys"
QUOTAS="$WORKER_DIR/cluster/quotas.json"
BACKUP_DIR="/root/astra-queue-backups/$(date +%Y%m%d_%H%M%S)"

APPLY=0
MODE=install
ADD_USER=""
ADD_FILE=""
while (($#)); do
    case "$1" in
        --apply) APPLY=1 ;;
        --rollback) MODE=rollback ;;
        --add-key)
            MODE=add-key
            ADD_USER="${2:-}"
            ADD_FILE="${3:-}"
            shift 2
            ;;
        -h | --help)
            sed -n '2,15p' "$0"
            exit 0
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 2
            ;;
    esac
    shift
done

TAG=plan
((APPLY)) && TAG=apply
say() { printf '%s\n' "$*"; }
step() { printf '[%s] %s\n' "$TAG" "$*"; }
die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

if [[ $EUID -ne 0 ]]; then
    ((APPLY)) && die "--apply needs sudo"
    say "(not root: plan only; checks that need root are skipped)"
fi
for cmd in sshd visudo adduser usermod ssh-keygen systemctl install awk; do
    command -v "$cmd" >/dev/null 2>&1 || [[ -x "/usr/sbin/$cmd" ]] || die "missing command: $cmd"
done
SSHD="$(command -v sshd || echo /usr/sbin/sshd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# type, key and last field as the comment; options prefixes are not expected here.
normalize_keys() { awk 'NF >= 2 && $1 !~ /^#/ { print $1, $2, (NF >= 3 ? $NF : "") }' "$1"; }
fingerprints() { ssh-keygen -lf "$1" | awk '{ print $2 }' | sort; }

backup() {
    ((APPLY)) || return 0
    mkdir -p "$BACKUP_DIR"
    local item
    for item in "$DROPIN" "$SUDOERS" "$KEY_DIR" "$HOME_KEYS"; do
        [[ -e "$item" ]] && cp -a -- "$item" "$BACKUP_DIR/" || true
    done
    say "backup: $BACKUP_DIR"
}

reload_ssh() {
    if [[ $EUID -ne 0 ]]; then
        step "sshd -t and systemctl reload ssh (skipped: needs root)"
        return 0
    fi
    "$SSHD" -t || return 1
    step "systemctl reload ssh"
    ((APPLY)) && systemctl reload ssh
    return 0
}

# ---------------------------------------------------------------- rollback
if [[ $MODE == rollback ]]; then
    backup
    step "remove $DROPIN and $SUDOERS (accounts, keys and scripts stay, inert)"
    if ((APPLY)); then
        rm -f -- "$DROPIN" "$SUDOERS"
        reload_ssh || die "sshd -t failed after removing the drop-in; inspect /etc/ssh"
        say "Rolled back. astrum keys come again from $HOME_KEYS."
    fi
    exit 0
fi

# ---------------------------------------------------------------- add-key
if [[ $MODE == add-key ]]; then
    printf '%s\n' "${QUEUE_USERS[@]}" | grep -qx -- "$ADD_USER" || die "user must be one of: ${QUEUE_USERS[*]}"
    [[ -f "$ADD_FILE" ]] || die "public key file not found: $ADD_FILE"
    [[ -d "$KEY_DIR" ]] || die "$KEY_DIR does not exist; run the installation first"
    normalize_keys "$ADD_FILE" >"$TMP/new.pub"
    [[ $(wc -l <"$TMP/new.pub") -eq 1 ]] || die "$ADD_FILE must contain exactly one public key"
    new_fp="$(fingerprints "$TMP/new.pub")" || die "$ADD_FILE is not a valid public key"
    target="$KEY_DIR/$ADD_USER"
    if [[ -f "$target" ]] && fingerprints "$target" 2>/dev/null | grep -qx -- "$new_fp"; then
        say "$new_fp is already authorized for $ADD_USER"
        exit 0
    fi
    step "authorize $new_fp for $ADD_USER in $target"
    if ((APPLY)); then
        backup
        cat "$TMP/new.pub" >>"$target"
        chown root:root "$target"
        chmod 0644 "$target"
        fingerprints "$target"
    fi
    exit 0
fi

# ---------------------------------------------------------------- install
for file in astra_queue_gate.sh astra_queue_rpc.sh sudoers_astra_queue sshd_astra_queue.conf quotas.example.json; do
    [[ -f "$SRC/$file" ]] || die "missing $SRC/$file"
done
[[ -x "$WORKER_DIR/venv/bin/python" ]] || die "missing $WORKER_DIR/venv/bin/python"
grep -q ASTRA_AUTHENTICATED_CLIENT "$WORKER_DIR/astra_cluster_manager.py" ||
    die "deploy the new astra_cluster_manager.py to $WORKER_DIR first (it has no authenticated identity)"

# 1. Split astrum's current keys: astra-gabriel goes to gabriel, the rest stays with astrum.
if [[ -f "$KEY_DIR/$SERVICE_USER" ]]; then
    say "keys for $SERVICE_USER already in $KEY_DIR/$SERVICE_USER (left unchanged):"
    fingerprints "$KEY_DIR/$SERVICE_USER"
    KEEP_KEYS=1
else
    KEEP_KEYS=0
    [[ -f "$HOME_KEYS" ]] || die "missing $HOME_KEYS"
    normalize_keys "$HOME_KEYS" | awk -v g="$GABRIEL_KEY_COMMENT" '$3 != g' >"$TMP/astrum"
    normalize_keys "$HOME_KEYS" | awk -v g="$GABRIEL_KEY_COMMENT" '$3 == g' >"$TMP/gabriel"
    [[ -s "$TMP/astrum" ]] || die "no key would remain for $SERVICE_USER; refusing"
    fingerprints "$TMP/astrum" >"$TMP/astrum.fp" || die "astrum key set does not parse"
    fingerprints "$HOME_KEYS" >"$TMP/original.fp" || die "$HOME_KEYS does not parse"
    comm -23 "$TMP/astrum.fp" "$TMP/original.fp" | grep -q . && die "normalized astrum keys differ from the originals"
    say "keys that stay with $SERVICE_USER:"
    cat "$TMP/astrum.fp"
    if [[ -s "$TMP/gabriel" ]]; then
        say "keys that move to gabriel:"
        fingerprints "$TMP/gabriel"
    fi
fi

backup

# 2. Group and accounts: no sudo, no password, a shell only so ForceCommand can run.
step "groupadd -f $QUEUE_GROUP"
((APPLY)) && groupadd -f "$QUEUE_GROUP"
for user in "${QUEUE_USERS[@]}"; do
    if id -u "$user" >/dev/null 2>&1; then
        say "user $user exists"
    else
        step "adduser --disabled-password $user"
        ((APPLY)) && adduser --disabled-password --gecos "" "$user" >/dev/null
    fi
    step "usermod -aG $QUEUE_GROUP $user"
    ((APPLY)) && usermod -aG "$QUEUE_GROUP" "$user"
    if id -nG "$user" 2>/dev/null | tr ' ' '\n' | grep -qxE 'sudo|admin|wheel'; then
        die "$user is in an administrative group; remove it before continuing"
    fi
done

# 3. Root-owned key files.
step "install -d $KEY_DIR (root, 0755)"
if ((APPLY)); then
    install -d -o root -g root -m 0755 "$KEY_DIR"
    if ((KEEP_KEYS == 0)); then
        install -o root -g root -m 0644 "$TMP/astrum" "$KEY_DIR/$SERVICE_USER"
        if [[ -s "$TMP/gabriel" && ! -f "$KEY_DIR/gabriel" ]]; then
            install -o root -g root -m 0644 "$TMP/gabriel" "$KEY_DIR/gabriel"
        fi
    fi
    for user in "${QUEUE_USERS[@]}"; do
        [[ -f "$KEY_DIR/$user" ]] || install -o root -g root -m 0644 /dev/null "$KEY_DIR/$user"
    done
fi

# 4. Gate and rpc wrapper.
step "install $GATE and $RPC (root, 0755)"
if ((APPLY)); then
    install -o root -g root -m 0755 "$SRC/astra_queue_gate.sh" "$GATE"
    install -o root -g root -m 0755 "$SRC/astra_queue_rpc.sh" "$RPC"
fi

# 5. sudo rule, validated before and after installation.
visudo -cqf "$SRC/sudoers_astra_queue" || die "sudoers_astra_queue does not validate"
step "install $SUDOERS (root, 0440)"
if ((APPLY)); then
    install -o root -g root -m 0440 "$SRC/sudoers_astra_queue" "$SUDOERS"
    visudo -cq || {
        rm -f -- "$SUDOERS"
        die "sudo configuration invalid after install; $SUDOERS removed"
    }
fi

# 6. Quotas (never overwrites an existing file).
if [[ -f "$QUOTAS" ]]; then
    say "quotas: $QUOTAS exists (left unchanged)"
else
    step "install $QUOTAS from quotas.example.json (astrum, 0644)"
    ((APPLY)) && install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0644 "$SRC/quotas.example.json" "$QUOTAS"
fi

# 7. sshd drop-in, validated; on any failure it is removed again.
step "install $DROPIN (root, 0644) and validate with sshd -t"
if ((APPLY)); then
    install -o root -g root -m 0644 "$SRC/sshd_astra_queue.conf" "$DROPIN"
    if ! "$SSHD" -t; then
        rm -f -- "$DROPIN"
        die "sshd -t failed; drop-in removed, nothing reloaded"
    fi
    effective() { "$SSHD" -T -C "user=$1,host=astrum,addr=192.0.2.1" | awk -v k="$2" '$1 == k { $1 = ""; sub(/^ /, ""); print }'; }
    problems=""
    [[ "$(effective "$SERVICE_USER" passwordauthentication)" == no ]] || problems+=" password-auth"
    [[ "$(effective "$SERVICE_USER" authorizedkeysfile)" == "$KEY_DIR/%u" ]] || problems+=" astrum-keyfile"
    for user in "${QUEUE_USERS[@]}"; do
        [[ "$(effective "$user" forcecommand)" == "$GATE" ]] || problems+=" $user-forcecommand"
        [[ "$(effective "$user" permittty)" == no ]] || problems+=" $user-tty"
    done
    if [[ -n "$problems" ]]; then
        rm -f -- "$DROPIN"
        die "effective sshd configuration is not as designed:$problems; drop-in removed, nothing reloaded"
    fi
    say "effective sshd configuration verified for $SERVICE_USER and ${QUEUE_USERS[*]}"
fi

reload_ssh || die "sshd -t failed before reload"

if ((APPLY)); then
    cat <<EOF

Installed. Do NOT close this session yet. From your PC, in a NEW terminal:
  ssh astrum hostname          # must print the hostname (astrum, your key)
If that fails, run here:  sudo bash $0 --rollback --apply
Then authorize Ivaylo's key:  sudo bash $0 --add-key ivaylo /path/ivaylo.pub --apply
EOF
else
    say ""
    say "Plan only; nothing was changed. Re-run with --apply to install."
fi
