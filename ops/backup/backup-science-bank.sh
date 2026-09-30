#!/usr/bin/env bash
# Encrypted, offsite backup of the Science Bank Postgres database and .env.
#
#   dump (pg_dump -Fc) + manifest (+ .env) -> tar -> age (public keys only) -> local copy -> rclone upload -> prune
#
# Usage: backup-science-bank.sh [--label NAME] [--no-upload]
#   --label NAME   suffix for the file name, e.g. "pre-deploy" (a-z, 0-9, dash)
#   --no-upload    keep the encrypted copy locally only
#
# Exit codes: 0 ok; 1 failed before an encrypted copy existed; 2 local copy kept but the upload failed;
#             64 bad arguments; 75 another backup is already running.
set -uo pipefail
SCRIPT_TAG=backup
# shellcheck source=lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

usage() { sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

LABEL=""
UPLOAD="${UPLOAD:-1}"
while [ $# -gt 0 ]; do
  case "$1" in
    --label) LABEL="${2:-}"; shift 2 ;;
    --no-upload) UPLOAD=0; shift ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done
[[ -z "$LABEL" || "$LABEL" =~ ^[a-z0-9][a-z0-9-]{0,30}$ ]] || { echo "bad --label (use a-z, 0-9, dash)" >&2; exit 64; }

umask 077
START=$(date +%s)
NAME=""

write_last_run() { # status message
  python3 - "$STATE_DIR/last-run.json" "$1" "$2" "$NAME" "$(($(date +%s) - START))" <<'PY'
import json, sys, time
path, status, message, name, seconds = sys.argv[1:6]
with open(path, "w") as f:
    json.dump({"finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": status,
               "message": message, "artifact": name, "seconds": int(seconds)}, f)
PY
}

fail() { # message [exit code]
  log "ERROR: $1"
  write_last_run failed "$1"
  notify "Science Bank backup failed" "$1" high
  exit "${2:-1}"
}

exec 9>"$STATE_DIR/lock"
flock -n 9 || { log "another backup run is in progress; skipping"; exit 75; }

TMP="$(mktemp -d "$STATE_DIR/run.XXXXXX")"
trap 'rm -rf "${TMP:?}"' EXIT
PAYLOAD="$TMP/payload"
mkdir -p "$PAYLOAD"

command -v age >/dev/null || fail "age is not installed"
command -v python3 >/dev/null || fail "python3 is not installed"
[ "$UPLOAD" = 1 ] && { command -v rclone >/dev/null || fail "rclone is not installed"; }
msg="$(validate_recipients "$RECIPIENTS_FILE")" || fail "$msg"

# 1. Dump.
log "dumping the database"
bash -c "$DUMP_CMD" >"$PAYLOAD/science_bank.dump" 2>>"$LOG_FILE" || fail "database dump failed (see $LOG_FILE)"
bytes=$(stat -c %s "$PAYLOAD/science_bank.dump")
[ "$bytes" -ge "$MIN_DUMP_BYTES" ] || fail "dump is only $bytes bytes (minimum $MIN_DUMP_BYTES); refusing to keep it"
[ "$(head -c 5 "$PAYLOAD/science_bank.dump")" = "PGDMP" ] || fail "dump is not a Postgres custom-format archive"

# 2. Row counts and schema version, recorded in the manifest so a restore can be checked against them.
SQL="select version_num from alembic_version;"
for t in $TABLES; do SQL+=$'\n'"select '$t|'||count(*) from $t;"; done
COUNTS="$(printf '%s\n' "$SQL" | bash -c "$SQL_CMD" 2>>"$LOG_FILE")" || fail "could not read table counts"

# 3. .env (database password, JWT secret). It is only ever stored inside the encrypted bundle.
if [ "$INCLUDE_ENV" = 1 ]; then
  if [ -r "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$PAYLOAD/env"
  else
    log "WARN: $ENV_FILE is not readable; the backup will not contain it"
  fi
fi

# 4. Manifest.
GIT_COMMIT="$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
COUNTS="$COUNTS" python3 - "$PAYLOAD" "$LABEL" "$GIT_COMMIT" <<'PY' || fail "could not write the manifest"
import hashlib, json, os, socket, sys, time
payload, label, commit = sys.argv[1:4]
lines = [l.strip() for l in os.environ["COUNTS"].splitlines() if l.strip()]
tables = {}
for line in lines[1:]:
    name, count = line.split("|")
    tables[name] = int(count)
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
files = {}
for name in ("science_bank.dump", "env"):
    path = os.path.join(payload, name)
    if os.path.exists(path):
        files[name] = {"sha256": sha256(path), "bytes": os.path.getsize(path)}
manifest = {"format": 1, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "label": label,
            "host": socket.gethostname(), "git_commit": commit, "alembic_version": lines[0], "tables": tables,
            "files": files}
with open(os.path.join(payload, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=1)
PY

# 5. Bundle and encrypt.
members=(manifest.json science_bank.dump)
[ -f "$PAYLOAD/env" ] && members+=(env)
tar -C "$PAYLOAD" -cf "$TMP/bundle.tar" "${members[@]}" || fail "could not build the bundle"
age -R "$RECIPIENTS_FILE" -o "$TMP/bundle.tar.age" "$TMP/bundle.tar" 2>>"$LOG_FILE" || fail "encryption failed"
[ -s "$TMP/bundle.tar.age" ] || fail "encryption produced an empty file"
rm -f "$TMP/bundle.tar"

NAME="science-bank-$(date -u +%Y%m%dT%H%M%SZ)${LABEL:+-$LABEL}.tar.age"
mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR" || fail "cannot create $BACKUP_DIR"
cp "$TMP/bundle.tar.age" "$BACKUP_DIR/.$NAME.partial" && mv "$BACKUP_DIR/.$NAME.partial" "$BACKUP_DIR/$NAME" ||
  fail "could not write the encrypted copy to $BACKUP_DIR"
write_marker last-local-success
size=$(stat -c %s "$BACKUP_DIR/$NAME")
log "encrypted copy written: $BACKUP_DIR/$NAME ($size bytes)"

# 6. Upload, then confirm the remote copy has the same size.
if [ "$UPLOAD" = 1 ]; then
  upload_error=""
  if ! rclone copyto "$BACKUP_DIR/$NAME" "$RCLONE_REMOTE/$NAME" 2>>"$LOG_FILE"; then
    upload_error="upload failed"
  else
    remote_size="$(rclone lsjson "$RCLONE_REMOTE" --files-only --include "$NAME" 2>>"$LOG_FILE" |
      python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["Size"] if d else "")' 2>/dev/null)"
    [ "$remote_size" = "$size" ] || upload_error="uploaded copy is ${remote_size:-missing} bytes, expected $size"
  fi
  if [ -n "$upload_error" ]; then
    log "ERROR: $upload_error (local copy kept)"
    write_last_run partial "$upload_error"
    notify "Science Bank backup not offsite" "$upload_error. The encrypted copy is still in $BACKUP_DIR." high
    exit 2
  fi
  write_marker last-upload-success
  log "uploaded to $RCLONE_REMOTE/$NAME"
fi

# 7. Retention. Never fatal; never drops below MIN_KEEP newest copies.
i=0
while IFS= read -r f; do
  base="$(basename "$f")"
  [[ "$base" =~ $ARTIFACT_RE ]] || continue
  i=$((i + 1))
  [ "$i" -le "$MIN_KEEP" ] && continue
  if older_than "$base" "$LOCAL_RETENTION_DAYS"; then rm -f -- "$f" && log "pruned local: $base"; fi
done < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'science-bank-*.tar.age' | sort -r)
find "$BACKUP_DIR" -maxdepth 1 -type f -name '.science-bank-*.partial' -mtime +1 -delete 2>/dev/null

if [ "$UPLOAD" = 1 ]; then
  i=0
  while IFS= read -r base; do
    [[ "$base" =~ $ARTIFACT_RE ]] || continue
    i=$((i + 1))
    [ "$i" -le "$MIN_KEEP" ] && continue
    if older_than "$base" "$REMOTE_RETENTION_DAYS"; then
      if rclone deletefile "$RCLONE_REMOTE/$base" 2>>"$LOG_FILE"; then log "pruned remote: $base"; else log "WARN: could not prune remote $base"; fi
    fi
  done < <(rclone lsf "$RCLONE_REMOTE" --files-only 2>>"$LOG_FILE" | sort -r)
fi

write_last_run ok "$NAME"
log "backup complete: $NAME in $(($(date +%s) - START))s"
echo "$BACKUP_DIR/$NAME"
