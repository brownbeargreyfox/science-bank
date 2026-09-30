#!/usr/bin/env bash
# Shared settings and helpers for the Science Bank backup scripts. Sourced, never executed directly.
#
# Every setting can be overridden from the environment or from $CONFIG_DIR/backup.conf (plain KEY=VALUE shell;
# no secrets belong in it). The defaults below describe the production host.

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_DIR="${SB_BACKUP_CONFIG_DIR:-$HOME/.config/science-bank-backup}"
# shellcheck disable=SC1091
[ -r "$CONFIG_DIR/backup.conf" ] && . "$CONFIG_DIR/backup.conf"

PROJECT_DIR="${PROJECT_DIR:-$(cd "$OPS_DIR/../.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-/srv/pool/config/science-bank-backups}" # local encrypted copies, off the root disk
STATE_DIR="${STATE_DIR:-$HOME/.local/state/science-bank-backup}"  # log, lock, markers
RECIPIENTS_FILE="${RECIPIENTS_FILE:-$CONFIG_DIR/recipients.txt}"   # age PUBLIC keys, one per line
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive-backup:science-bank-backups}"
NOTIFY_SCRIPT="${NOTIFY_SCRIPT:-/srv/pool/config/dashboard-backups/notify.sh}" # defines ntfy_alert "title" "msg" [priority]
ENV_FILE="${ENV_FILE:-$PROJECT_DIR/.env}"
INCLUDE_ENV="${INCLUDE_ENV:-1}"
LOCAL_RETENTION_DAYS="${LOCAL_RETENTION_DAYS:-14}"
REMOTE_RETENTION_DAYS="${REMOTE_RETENTION_DAYS:-90}"
MIN_KEEP="${MIN_KEEP:-3}"               # never prune below this many newest copies, however old they are
MAX_AGE_HOURS="${MAX_AGE_HOURS:-30}"    # the watchdog alerts past this
MIN_DUMP_BYTES="${MIN_DUMP_BYTES:-1024}"
TABLES="${TABLES:-users questions assessments administrations item_results audit_events}" # row counts in the manifest
DRILL_IMAGE="${DRILL_IMAGE:-postgres:16-alpine}"

# Authenticity. age only encrypts: anyone holding the public key can create a file that decrypts. So every artifact is
# also signed (OpenSSH signatures, namespace below). The signing key lives on this host because it signs at backup
# time; the matching PUBLIC key goes in an allowed-signers file kept off-host (password manager) and is what the
# restore drill verifies against, before anything is decrypted or unpacked. Someone who can only write to the
# Drive folder cannot forge a signature.
SIGNING_KEY_FILE="${SIGNING_KEY_FILE:-$CONFIG_DIR/signing_ed25519}"
SIGNERS_FILE="${SIGNERS_FILE:-$CONFIG_DIR/allowed_signers}"
SIG_PRINCIPAL="science-bank-backup"
SIG_NAMESPACE="science-bank-backup"

# The two commands that talk to Postgres. Both run through `bash -c`. Tests replace them with commands aimed at a
# scratch container; production uses the compose service, which already has POSTGRES_USER/POSTGRES_DB set.
default_dump_cmd() {
  printf 'docker compose --project-directory %q exec -T postgres sh -c %q' "$PROJECT_DIR" \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'
}
default_sql_cmd() {
  printf 'docker compose --project-directory %q exec -T postgres sh -c %q' "$PROJECT_DIR" \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1'
}
DUMP_CMD="${DUMP_CMD:-$(default_dump_cmd)}"
SQL_CMD="${SQL_CMD:-$(default_sql_cmd)}"

# Artifact names sort chronologically: science-bank-YYYYMMDDTHHMMSSZ[-label].tar.age
ARTIFACT_RE='^science-bank-[0-9]{8}T[0-9]{6}Z(-[a-z0-9-]+)?\.tar\.age$'

mkdir -p "$STATE_DIR" && chmod 700 "$STATE_DIR"
LOG_FILE="$STATE_DIR/backup.log"

log() {
  printf '%s [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${SCRIPT_TAG:-backup}" "$*" | tee -a "$LOG_FILE" >&2
}

# notify TITLE MESSAGE [PRIORITY]. Sourced in a subshell so the host script cannot change our state.
notify() {
  if [ -r "$NOTIFY_SCRIPT" ]; then
    ( # shellcheck disable=SC1090
      . "$NOTIFY_SCRIPT" && ntfy_alert "$@" ) >>"$LOG_FILE" 2>&1 || log "WARN: the notify script failed"
  else
    log "ALERT (no notify script at $NOTIFY_SCRIPT): $1 - $2"
  fi
}

write_marker() { date +%s >"$STATE_DIR/$1"; }

# Hours since a marker was written, one decimal, or the word "never".
marker_age_hours() {
  local f="$STATE_DIR/$1"
  [ -s "$f" ] || { echo never; return; }
  awk -v now="$(date +%s)" -v then="$(cat "$f")" 'BEGIN { printf "%.1f", (now - then) / 3600 }'
}

# Epoch seconds encoded in an artifact name.
name_epoch() {
  local digits
  digits="$(sed -E 's/^science-bank-([0-9]{8})T([0-9]{6})Z.*/\1\2/' <<<"$1")"
  date -u -d "${digits:0:4}-${digits:4:2}-${digits:6:2} ${digits:8:2}:${digits:10:2}:${digits:12:2}" +%s
}

# older_than NAME DAYS
older_than() {
  [ $(( $(date +%s) - $(name_epoch "$1") )) -gt $(( $2 * 86400 )) ]
}

# sign_file FILE -> writes FILE.sig. Fails if the key is missing or unusable.
sign_file() {
  [ -r "$SIGNING_KEY_FILE" ] || { echo "signing key not readable: $SIGNING_KEY_FILE"; return 1; }
  ssh-keygen -Y sign -q -f "$SIGNING_KEY_FILE" -n "$SIG_NAMESPACE" "$1" 2>&1 || return 1
}

# verify_sig FILE SIGFILE SIGNERS_FILE. Succeeds only for a signature by a key listed in SIGNERS_FILE.
verify_sig() {
  [ -r "$1" ] && [ -r "$2" ] && [ -r "$3" ] || return 1
  ssh-keygen -Y verify -f "$3" -I "$SIG_PRINCIPAL" -n "$SIG_NAMESPACE" -s "$2" <"$1" >/dev/null 2>&1
}

# Only ever encrypt to PUBLIC keys. Refuse anything else, and above all refuse a private key pasted by mistake.
validate_recipients() {
  local f="$1" line n=0
  [ -r "$f" ] || { echo "recipients file not readable: $f"; return 1; }
  if grep -q 'AGE-SECRET-KEY' "$f"; then
    echo "recipients file contains a PRIVATE key (AGE-SECRET-KEY); refusing. Keep only the age1... public key line."
    return 1
  fi
  while IFS= read -r line || [ -n "$line" ]; do
    line="$(tr -d '[:space:]' <<<"${line%%#*}")"
    [ -z "$line" ] && continue
    [[ "$line" =~ ^age1[0-9a-z]{58}$ ]] || { echo "not a valid age public key: ${line:0:10}..."; return 1; }
    n=$((n + 1))
  done <"$f"
  [ "$n" -ge 1 ] || { echo "no age public keys found in $f"; return 1; }
}
