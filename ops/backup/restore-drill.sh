#!/usr/bin/env bash
# Prove a backup can be read and restored, without touching production.
#
# Order of trust: (1) the artifact's signature must verify against your allowed-signers file, before anything is
# decrypted; (2) it is decrypted with YOUR private key; (3) the decrypted tar is unpacked by a strict allowlist
# extractor and its manifest validated (bundle.py); (4) file checksums are checked; (5) the dump is restored into a
# throwaway Postgres (no network) and compared with the manifest. age alone proves nothing about who made a file.
#
# Usage:
#   restore-drill.sh --identity KEYFILE --file ARTIFACT.tar.age [--signers FILE]
#   restore-drill.sh --identity KEYFILE --from-remote latest|NAME [--signers FILE]
#   ... add --extract-to DIR to only verify, decrypt and unpack (for a real restore or to recover .env)
#
# --signers defaults to ~/.config/science-bank-backup/allowed_signers: one line, "science-bank-backup ssh-ed25519
# AAAA...", the PUBLIC signing key. Keep a copy off this server (password manager). The ARTIFACT.sig file must sit
# next to the artifact (it is downloaded alongside it with --from-remote).
#
# The private key is read from the path you give and is never copied. Keep it in your password manager; put it on
# disk only for the moment you run this, then delete it.
#
# Exit codes: 0 pass; 1 fail; 64 bad arguments.
set -uo pipefail
SCRIPT_TAG=drill
# shellcheck source=lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

usage() { sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

IDENTITY="" FILE="" FROM_REMOTE="" EXTRACT_TO=""
while [ $# -gt 0 ]; do
  case "$1" in
    --signers) SIGNERS_FILE="${2:-}"; shift 2 ;;
    --identity) IDENTITY="${2:-}"; shift 2 ;;
    --file) FILE="${2:-}"; shift 2 ;;
    --from-remote) FROM_REMOTE="${2:-}"; shift 2 ;;
    --extract-to) EXTRACT_TO="${2:-}"; shift 2 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
done
{ [ -n "$IDENTITY" ] && { [ -n "$FILE" ] || [ -n "$FROM_REMOTE" ]; }; } || { usage >&2; exit 64; }

umask 077
CONTAINER=""
TMP="$(mktemp -d "$STATE_DIR/drill.XXXXXX")"
cleanup() {
  [ -n "$CONTAINER" ] && docker rm -f "$CONTAINER" >/dev/null 2>&1
  rm -rf "${TMP:?}"
}
trap cleanup EXIT
fail() { log "FAIL: $1"; echo "RESULT: FAIL - $1"; exit 1; }

[ -r "$IDENTITY" ] || fail "cannot read the identity file $IDENTITY"
[ "$(($(stat -c %a "$IDENTITY") % 100))" = 0 ] || log "WARN: $IDENTITY is readable by other users; tighten it with chmod 600"

# Resolve and fetch the artifact.
if [ -n "$FROM_REMOTE" ]; then
  name="$FROM_REMOTE"
  if [ "$name" = latest ]; then
    name="$(rclone lsf "$RCLONE_REMOTE" --files-only 2>>"$LOG_FILE" | grep -E "$ARTIFACT_RE" | sort | tail -1)"
    [ -n "$name" ] || fail "no backups found on $RCLONE_REMOTE"
  fi
  [[ "$name" =~ $ARTIFACT_RE ]] || fail "not a backup file name: $name"
  rclone copyto "$RCLONE_REMOTE/$name" "$TMP/artifact.age" 2>>"$LOG_FILE" || fail "could not download $name"
  rclone copyto "$RCLONE_REMOTE/$name.sig" "$TMP/artifact.age.sig" 2>>"$LOG_FILE" || fail "could not download the signature $name.sig (an unsigned backup is not trusted)"
  ARTIFACT="$TMP/artifact.age"
  SIGFILE="$TMP/artifact.age.sig"
else
  name="$(basename "$FILE")"
  [ -r "$FILE" ] || fail "cannot read $FILE"
  # Work on private copies, so what is verified is exactly what is later decrypted (no check-then-use gap).
  cp "$FILE" "$TMP/artifact.age" || fail "cannot copy $FILE"
  ARTIFACT="$TMP/artifact.age"
  SIGFILE="$TMP/artifact.age.sig"
  [ -r "$FILE.sig" ] && cp "$FILE.sig" "$SIGFILE"
fi
[ -r "$ARTIFACT" ] || fail "cannot read $ARTIFACT"
echo "artifact: $name"

# 1. Authenticity, before anything is decrypted or unpacked.
[ -r "$SIGFILE" ] || fail "no signature found for $name (an unsigned backup is not trusted)"
[ -r "$SIGNERS_FILE" ] || fail "no allowed-signers file at $SIGNERS_FILE (pass --signers; it holds the PUBLIC signing key)"
verify_sig "$ARTIFACT" "$SIGFILE" "$SIGNERS_FILE" || fail "the signature does not verify; this file was not made by the backup job, or was altered"
echo "signature: verified"

# 2. Decrypt, 3. strict unpack and manifest validation, 4. checksums.
age -d -i "$IDENTITY" -o "$TMP/bundle.tar" "$ARTIFACT" 2>"$TMP/age.err" || fail "could not decrypt (wrong key, or a damaged file)"
python3 "$OPS_DIR/bundle.py" extract "$TMP/bundle.tar" "$TMP/payload" "$name" >"$TMP/bundle.out" 2>&1 || fail "$(cat "$TMP/bundle.out")"
rm -f "$TMP/bundle.tar"
python3 - "$TMP/payload" <<'PY' || fail "file checksum does not match the manifest"
import hashlib, json, os, sys
payload = sys.argv[1]
manifest = json.load(open(os.path.join(payload, "manifest.json")))
bad = []
for name, meta in manifest["files"].items():
    path = os.path.join(payload, name)
    if not os.path.exists(path):
        bad.append(name + " (missing)")
        continue
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != meta["sha256"]:
        bad.append(name)
if bad:
    print("checksum problem: " + ", ".join(bad))
    sys.exit(1)
print("checksums ok: " + ", ".join(sorted(manifest["files"])))
PY

if [ -n "$EXTRACT_TO" ]; then
  mkdir -p "$EXTRACT_TO" && chmod 700 "$EXTRACT_TO" && cp -a "$TMP/payload/." "$EXTRACT_TO/" || fail "could not extract to $EXTRACT_TO"
  echo "extracted to $EXTRACT_TO (contains the database dump and, if included, .env; delete it when done)"
  echo "RESULT: PASS (decrypted and verified; no restore performed)"
  exit 0
fi

# Restore into a throwaway Postgres.
command -v docker >/dev/null || fail "docker is not available"
CONTAINER="sb-restore-drill-$$"
docker run -d --rm --name "$CONTAINER" -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=drill \
  --network none --tmpfs /var/lib/postgresql/data "$DRILL_IMAGE" >/dev/null 2>>"$LOG_FILE" || fail "could not start a throwaway Postgres ($DRILL_IMAGE)"
for _ in $(seq 1 60); do
  [ "$(docker logs "$CONTAINER" 2>&1 | grep -c 'ready to accept connections')" -ge 2 ] &&
    docker exec "$CONTAINER" pg_isready -U postgres -d drill >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$CONTAINER" pg_isready -U postgres -d drill >/dev/null 2>&1 || fail "the throwaway Postgres did not become ready"

docker exec -i "$CONTAINER" pg_restore -U postgres -d drill --no-owner --no-privileges --exit-on-error \
  <"$TMP/payload/science_bank.dump" 2>"$TMP/restore.err" || fail "pg_restore failed: $(head -c 300 "$TMP/restore.err")"

restored="$(docker exec -i "$CONTAINER" psql -U postgres -d drill -At -c 'select version_num from alembic_version' 2>&1)"
counts=""
for t in $(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))["tables"]))' "$TMP/payload/manifest.json"); do
  n="$(docker exec -i "$CONTAINER" psql -U postgres -d drill -At -c "select count(*) from \"$t\"" 2>/dev/null)" || n="MISSING"
  counts+="$t|${n:-MISSING}"$'\n'
done

RESTORED_VERSION="$restored" RESTORED_COUNTS="$counts" python3 - "$TMP/payload" <<'PY'
import json, os, sys
payload = sys.argv[1]
m = json.load(open(os.path.join(payload, "manifest.json")))
got = dict(l.split("|") for l in os.environ["RESTORED_COUNTS"].splitlines() if l)
failed, warned = False, False
print(f"{'table':<20}{'manifest':>10}{'restored':>10}")
for table, want in m["tables"].items():
    have = got.get(table, "MISSING")
    if have == "MISSING" or (int(have) == 0 and want > 0):
        status, failed = "FAIL", True
    elif int(have) != want:
        status, warned = "differs (a write may have landed during the backup)", True
    else:
        status = "ok"
    print(f"{table:<20}{want:>10}{have:>10}  {status}")
version_ok = os.environ["RESTORED_VERSION"] == m["alembic_version"]
failed = failed or not version_ok
print(f"schema version: manifest {m['alembic_version']}, restored {os.environ['RESTORED_VERSION']}  {'ok' if version_ok else 'FAIL'}")
env = m["files"].get("env")
print("env: " + ("included and checksum-verified" if env else "NOT included in this backup"))
print(f"backup made {m['created_at']} on {m['host']} at commit {m['git_commit']} (label: {m['label'] or 'none'})")
sys.exit(1 if failed else 0)
PY
rc=$?
if [ "$rc" = 0 ]; then echo "RESULT: PASS"; log "drill passed for $name"; exit 0; fi
fail "restored data does not match the manifest"
