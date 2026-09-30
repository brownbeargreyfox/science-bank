#!/usr/bin/env bash
# End-to-end tests for the backup scripts. Needs docker, age, age-keygen, rclone, python3.
#
# Everything is scratch: a throwaway Postgres container, a throwaway age key pair, a local directory standing in for
# the Drive remote, and a fake notifier that appends to a file. Nothing touches production, Google Drive, or ntfy.
#
# Usage: ops/backup/tests/run-tests.sh          (exit 0 only if every test passes)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS="$(cd "$HERE/.." && pwd)"
WORK="$(mktemp -d)"
chmod 700 "$WORK"
PG="sb-backup-test-$$"
PASS=0 FAILS=0

cleanup() {
  docker rm -f "$PG" >/dev/null 2>&1
  rm -rf "${WORK:?}"
}
trap cleanup EXIT

for tool in docker age age-keygen rclone python3 flock; do
  command -v "$tool" >/dev/null || { echo "missing tool: $tool"; exit 2; }
done

ok() { echo "PASS  $1"; PASS=$((PASS + 1)); }
no() { echo "FAIL  $1${2:+  ($2)}"; FAILS=$((FAILS + 1)); }
expect() { # description, expected rc, actual rc
  if [ "$2" = "$3" ]; then ok "$1"; else no "$1" "exit $3, wanted $2"; fi
}
has() { # description, file, pattern
  if grep -qE -- "$3" "$2" 2>/dev/null; then ok "$1"; else no "$1" "no match for /$3/ in $2"; fi
}

# ---------- scratch environment ----------
mkdir -p "$WORK/cfg" "$WORK/state" "$WORK/local" "$WORK/remote"
docker run -d --rm --name "$PG" -e POSTGRES_PASSWORD=t -e POSTGRES_DB=science_bank postgres:16-alpine >/dev/null ||
  { echo "could not start scratch Postgres"; exit 2; }
for _ in $(seq 1 60); do
  [ "$(docker logs "$PG" 2>&1 | grep -c 'ready to accept connections')" -ge 2 ] &&
    docker exec "$PG" pg_isready -U postgres -d science_bank >/dev/null 2>&1 && break
  sleep 1
done
docker exec -i "$PG" psql -U postgres -d science_bank -v ON_ERROR_STOP=1 -q <"$HERE/fixture.sql" >/dev/null ||
  { echo "fixture load failed"; exit 2; }

age-keygen -o "$WORK/id.txt" 2>/dev/null
age-keygen -o "$WORK/wrong-id.txt" 2>/dev/null
age-keygen -y "$WORK/id.txt" >"$WORK/cfg/recipients.txt"
printf 'POSTGRES_PASSWORD=fixture-password\nJWT_SECRET=fixture-secret\n' >"$WORK/fixture.env"
cat >"$WORK/notify.sh" <<EOF
ntfy_alert() { echo "\$1 | \$2 | \${3:-}" >>"$WORK/alerts.log"; }
EOF

# Every script run gets this environment; extra VAR=value arguments override it.
run() { # [VAR=value ...] -- script args...
  local over=()
  while [ "$1" != -- ]; do over+=("$1"); shift; done
  shift
  env SB_BACKUP_CONFIG_DIR="$WORK/cfg" STATE_DIR="$WORK/state" BACKUP_DIR="$WORK/local" \
    RECIPIENTS_FILE="$WORK/cfg/recipients.txt" RCLONE_REMOTE="$WORK/remote" NOTIFY_SCRIPT="$WORK/notify.sh" \
    ENV_FILE="$WORK/fixture.env" PROJECT_DIR="$WORK" \
    DUMP_CMD="docker exec -i $PG pg_dump -U postgres -d science_bank -Fc" \
    SQL_CMD="docker exec -i $PG psql -U postgres -d science_bank -At -v ON_ERROR_STOP=1" \
    DRILL_IMAGE=postgres:16-alpine "${over[@]}" "$@"
}
newest_local() { find "$WORK/local" -maxdepth 1 -name 'science-bank-*.tar.age' | sort | tail -1; }
count_local() { find "$WORK/local" -maxdepth 1 -name 'science-bank-*.tar.age' | wc -l; }
count_remote() { find "$WORK/remote" -maxdepth 1 -name 'science-bank-*.tar.age' | wc -l; }
reset_alerts() { rm -f "${WORK:?}/alerts.log"; }

echo "== syntax"
for f in lib.sh backup-science-bank.sh check-backup-health.sh restore-drill.sh tests/run-tests.sh; do
  bash -n "$OPS/$f" 2>/dev/null && ok "bash -n $f" || no "bash -n $f"
done

echo "== backup: happy path"
reset_alerts
run -- "$OPS/backup-science-bank.sh" >"$WORK/out1" 2>"$WORK/err1"
expect "backup exits 0" 0 $?
ART="$(newest_local)"
[ -n "$ART" ] && ok "encrypted copy exists locally" || no "encrypted copy exists locally"
[ "$(stat -c %a "$ART")" = 600 ] && ok "artifact is mode 600" || no "artifact is mode 600" "$(stat -c %a "$ART")"
[[ "$(basename "$ART")" =~ ^science-bank-[0-9]{8}T[0-9]{6}Z\.tar\.age$ ]] && ok "artifact name format" || no "artifact name format" "$ART"
[ -f "$WORK/remote/$(basename "$ART")" ] && ok "artifact uploaded to the remote" || no "artifact uploaded to the remote"
cmp -s "$ART" "$WORK/remote/$(basename "$ART")" && ok "remote copy is byte-identical" || no "remote copy is byte-identical"
[ -s "$WORK/state/last-local-success" ] && [ -s "$WORK/state/last-upload-success" ] && ok "success markers written" || no "success markers written"
has "last-run.json says ok" "$WORK/state/last-run.json" '"status": "ok"'
[ ! -s "$WORK/alerts.log" ] && ok "no alerts on success" || no "no alerts on success" "$(cat "$WORK/alerts.log")"
[ -z "$(find "$WORK/state" -maxdepth 1 -name 'run.*')" ] && ok "no temp directories left behind" || no "no temp directories left behind"
! grep -q 'fixture-password\|fixture-secret' "$WORK/state/backup.log" && ok "log never contains secrets" || no "log never contains secrets"
! grep -aq 'fixture-password' "$ART" && ok "artifact is not plaintext" || no "artifact is not plaintext"

echo "== backup: contents (decrypted with the test key)"
mkdir "$WORK/x1"
age -d -i "$WORK/id.txt" -o "$WORK/b1.tar" "$ART" && tar -xf "$WORK/b1.tar" -C "$WORK/x1"
[ -f "$WORK/x1/science_bank.dump" ] && [ -f "$WORK/x1/manifest.json" ] && [ -f "$WORK/x1/env" ] && ok "bundle has dump, manifest, env" || no "bundle has dump, manifest, env"
cmp -s "$WORK/x1/env" "$WORK/fixture.env" && ok ".env is carried unchanged" || no ".env is carried unchanged"
python3 - "$WORK/x1/manifest.json" <<'PY' && ok "manifest counts match the fixture" || no "manifest counts match the fixture"
import json, sys
m = json.load(open(sys.argv[1]))
want = {"users": 3, "questions": 40, "assessments": 2, "administrations": 3, "item_results": 25, "audit_events": 60}
assert m["tables"] == want, m["tables"]
assert m["alembic_version"] == "0005_results_and_variants"
assert set(m["files"]) == {"science_bank.dump", "env"}
PY

echo "== backup: options and guards"
run -- "$OPS/backup-science-bank.sh" --label pre-deploy --no-upload >/dev/null 2>&1
expect "--label/--no-upload exits 0" 0 $?
ls "$WORK/local" | grep -q -- '-pre-deploy\.tar\.age$' && ok "label appears in the file name" || no "label appears in the file name"
[ "$(count_remote)" = 1 ] && ok "--no-upload did not upload" || no "--no-upload did not upload" "remote has $(count_remote)"
run -- "$OPS/backup-science-bank.sh" --label 'Bad Label!' >/dev/null 2>&1
expect "bad label is rejected" 64 $?
run INCLUDE_ENV=0 -- "$OPS/backup-science-bank.sh" --no-upload >/dev/null 2>&1
LATEST="$(newest_local)"
mkdir "$WORK/x2"; age -d -i "$WORK/id.txt" -o "$WORK/b2.tar" "$LATEST" && tar -xf "$WORK/b2.tar" -C "$WORK/x2"
[ ! -e "$WORK/x2/env" ] && ok "INCLUDE_ENV=0 leaves .env out" || no "INCLUDE_ENV=0 leaves .env out"

echo "== backup: failure handling"
BEFORE="$(count_local)"; reset_alerts; LAST_OK="$(cat "$WORK/state/last-local-success")"; sleep 1
printf '# mistake\nAGE-SECRET-KEY-1QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ\n' >"$WORK/bad-recipients.txt"
run RECIPIENTS_FILE="$WORK/bad-recipients.txt" -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "a private key in the recipients file is refused" 1 $?
[ "$(count_local)" = "$BEFORE" ] && ok "  ...and no artifact was produced" || no "  ...and no artifact was produced"
has "  ...and an alert was raised" "$WORK/alerts.log" 'Science Bank backup failed.*PRIVATE key'
run RECIPIENTS_FILE="$WORK/missing.txt" -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "a missing recipients file fails" 1 $?
printf 'not-a-key\n' >"$WORK/junk-recipients.txt"
run RECIPIENTS_FILE="$WORK/junk-recipients.txt" -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "a malformed recipient fails" 1 $?
reset_alerts
run DUMP_CMD=false -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "a failing dump fails the run" 1 $?
has "  ...with an alert" "$WORK/alerts.log" 'backup failed.*dump failed'
[ "$(count_local)" = "$BEFORE" ] && ok "  ...and no partial artifact" || no "  ...and no partial artifact"
[ "$(cat "$WORK/state/last-local-success")" = "$LAST_OK" ] && ok "  ...and the success marker did not move" || no "  ...and the success marker did not move"
has "  ...and last-run.json says failed" "$WORK/state/last-run.json" '"status": "failed"'
run DUMP_CMD="echo tiny" -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "a suspiciously small dump is refused" 1 $?
run DUMP_CMD="head -c 4000 /dev/zero" -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "a dump that is not a Postgres archive is refused" 1 $?

echo "== backup: upload failure keeps the local copy"
reset_alerts; BEFORE="$(count_local)"; UP_OK="$(cat "$WORK/state/last-upload-success")"; sleep 1
run RCLONE_REMOTE=/proc/nonexistent/remote -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "an upload failure exits 2" 2 $?
[ "$(count_local)" = "$((BEFORE + 1))" ] && ok "  ...local encrypted copy is kept" || no "  ...local encrypted copy is kept"
[ "$(cat "$WORK/state/last-upload-success")" = "$UP_OK" ] && ok "  ...upload marker did not move" || no "  ...upload marker did not move"
has "  ...alert says not offsite" "$WORK/alerts.log" 'not offsite'

echo "== backup: an upload that reports success but stores a short file"
mkdir -p "$WORK/bin"
REAL_RCLONE="$(command -v rclone)"
cat >"$WORK/bin/rclone" <<EOF
#!/usr/bin/env bash
"$REAL_RCLONE" "\$@"; rc=\$?
if [ "\$1" = copyto ] && [ \$rc = 0 ]; then truncate -s -1 "\$3"; fi
exit \$rc
EOF
chmod +x "$WORK/bin/rclone"
reset_alerts; UP_OK="$(cat "$WORK/state/last-upload-success")"; sleep 1
run PATH="$WORK/bin:$PATH" RCLONE_REMOTE="$WORK/remote" -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "a truncated remote copy is detected (exit 2)" 2 $?
has "  ...alert reports the size mismatch" "$WORK/alerts.log" 'uploaded copy is'
[ "$(cat "$WORK/state/last-upload-success")" = "$UP_OK" ] && ok "  ...upload marker did not move" || no "  ...upload marker did not move"
rm -rf "${WORK:?}/bin" "${WORK:?}/remote"/*

echo "== backup: concurrency"
( flock "$WORK/state/lock" sleep 4 ) &
sleep 1
run -- "$OPS/backup-science-bank.sh" --no-upload >/dev/null 2>&1
expect "a second run while one is active exits 75" 75 $?
wait

echo "== retention"
rm -rf "${WORK:?}/local" "${WORK:?}/remote"; mkdir -p "$WORK/local" "$WORK/remote"
for d in 01 02 03 04 05; do : >"$WORK/local/science-bank-202001${d}T000000Z.tar.age"; : >"$WORK/remote/science-bank-202001${d}T000000Z.tar.age"; done
: >"$WORK/local/not-ours.txt"
run -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
expect "run with old copies present exits 0" 0 $?
[ "$(count_local)" = 3 ] && ok "local: pruned to MIN_KEEP (3) newest" || no "local: pruned to MIN_KEEP (3) newest" "$(count_local)"
[ -e "$WORK/local/science-bank-20200105T000000Z.tar.age" ] && [ -e "$WORK/local/science-bank-20200104T000000Z.tar.age" ] &&
  [ ! -e "$WORK/local/science-bank-20200103T000000Z.tar.age" ] && ok "local: kept the two newest old copies, dropped the rest" || no "local: kept the two newest old copies, dropped the rest"
[ -e "$WORK/local/not-ours.txt" ] && ok "local: unrelated files untouched" || no "local: unrelated files untouched"
[ "$(count_remote)" = 3 ] && ok "remote: pruned to MIN_KEEP (3) newest" || no "remote: pruned to MIN_KEEP (3) newest" "$(count_remote)"
rm -f "${WORK:?}/local"/science-bank-2020*; : >"$WORK/local/science-bank-20200101T000000Z.tar.age"
run LOCAL_RETENTION_DAYS=36500 -- "$OPS/backup-science-bank.sh" --no-upload >/dev/null 2>&1
[ -e "$WORK/local/science-bank-20200101T000000Z.tar.age" ] && ok "retention window is respected (nothing pruned inside it)" || no "retention window is respected"

echo "== health check"
reset_alerts
run -- "$OPS/check-backup-health.sh" >/dev/null 2>&1
expect "fresh markers: healthy" 0 $?
run -- "$OPS/check-backup-health.sh" --check-remote >/dev/null 2>&1
expect "fresh markers and fresh remote: healthy" 0 $?
echo $(($(date +%s) - 40 * 3600)) >"$WORK/state/last-upload-success"
run -- "$OPS/check-backup-health.sh" >/dev/null 2>&1
expect "a stale upload marker alerts" 1 $?
has "  ...alert is urgent and names the marker" "$WORK/alerts.log" 'stale or unverifiable.*last-upload-success.*\| urgent'
date +%s >"$WORK/state/last-upload-success"
rm -f "${WORK:?}/state/last-local-success"
run -- "$OPS/check-backup-health.sh" >/dev/null 2>&1
expect "a never-written marker alerts" 1 $?
date +%s >"$WORK/state/last-local-success"
rm -rf "${WORK:?}/remote"/*
run -- "$OPS/check-backup-health.sh" --check-remote >/dev/null 2>&1
expect "--check-remote alerts when the remote has no backups" 1 $?
: >"$WORK/remote/science-bank-20200101T000000Z.tar.age"
run -- "$OPS/check-backup-health.sh" --check-remote >/dev/null 2>&1
expect "--check-remote alerts when the newest remote backup is old" 1 $?

echo "== restore drill"
run -- "$OPS/backup-science-bank.sh" --no-upload >/dev/null 2>&1
ART="$(newest_local)"
run -- "$OPS/restore-drill.sh" --identity "$WORK/id.txt" --file "$ART" >"$WORK/drill1.out" 2>&1
expect "drill passes on a good backup" 0 $?
has "  ...reports PASS" "$WORK/drill1.out" 'RESULT: PASS'
has "  ...compares row counts" "$WORK/drill1.out" 'questions +40 +40 +ok'
has "  ...checks the schema version" "$WORK/drill1.out" 'schema version: manifest 0005_results_and_variants, restored 0005_results_and_variants  ok'
[ -z "$(docker ps -aq --filter name=sb-restore-drill)" ] && ok "  ...throwaway container is gone afterwards" || no "  ...throwaway container is gone afterwards"
! grep -q 'fixture-password' "$WORK/drill1.out" && ok "  ...output never prints .env contents" || no "  ...output never prints .env contents"
run -- "$OPS/restore-drill.sh" --identity "$WORK/wrong-id.txt" --file "$ART" >"$WORK/drill2.out" 2>&1
expect "drill fails with the wrong key" 1 $?
has "  ...says so plainly" "$WORK/drill2.out" 'could not decrypt'
run -- "$OPS/restore-drill.sh" --identity "$WORK/id.txt" --file "$WORK/missing.age" >/dev/null 2>&1
expect "drill fails on a missing file" 1 $?
run -- "$OPS/restore-drill.sh" >/dev/null 2>&1
expect "drill with no arguments exits 64" 64 $?

echo "== restore drill: tampering and damage"
mkdir "$WORK/t1"; age -d -i "$WORK/id.txt" -o "$WORK/tb.tar" "$ART" && tar -xf "$WORK/tb.tar" -C "$WORK/t1"
printf 'X' >>"$WORK/t1/science_bank.dump"
tar -C "$WORK/t1" -cf "$WORK/tb2.tar" manifest.json science_bank.dump env
age -R "$WORK/cfg/recipients.txt" -o "$WORK/tampered.tar.age" "$WORK/tb2.tar"
run -- "$OPS/restore-drill.sh" --identity "$WORK/id.txt" --file "$WORK/tampered.tar.age" >"$WORK/drill3.out" 2>&1
expect "a modified dump is caught by the checksum" 1 $?
has "  ...and reported" "$WORK/drill3.out" 'checksum'
cp "$ART" "$WORK/damaged.tar.age"; printf '\x00\x01\x02' | dd of="$WORK/damaged.tar.age" bs=1 seek=300 conv=notrunc 2>/dev/null
run -- "$OPS/restore-drill.sh" --identity "$WORK/id.txt" --file "$WORK/damaged.tar.age" >/dev/null 2>&1
expect "a damaged encrypted file is caught" 1 $?
mkdir "$WORK/t2"; tar -xf "$WORK/tb.tar" -C "$WORK/t2"
python3 - "$WORK/t2/manifest.json" <<'PY'
import json, sys
p = sys.argv[1]; m = json.load(open(p)); m["tables"]["nonexistent_table"] = 1; json.dump(m, open(p, "w"))
PY
tar -C "$WORK/t2" -cf "$WORK/tb3.tar" manifest.json science_bank.dump env
age -R "$WORK/cfg/recipients.txt" -o "$WORK/mismatch.tar.age" "$WORK/tb3.tar"
run -- "$OPS/restore-drill.sh" --identity "$WORK/id.txt" --file "$WORK/mismatch.tar.age" >"$WORK/drill4.out" 2>&1
expect "a table missing after restore fails the drill" 1 $?
has "  ...table is named" "$WORK/drill4.out" 'nonexistent_table .*MISSING'

echo "== restore drill: extract only"
run -- "$OPS/restore-drill.sh" --identity "$WORK/id.txt" --file "$ART" --extract-to "$WORK/extracted" >"$WORK/drill5.out" 2>&1
expect "--extract-to succeeds" 0 $?
[ -f "$WORK/extracted/science_bank.dump" ] && [ "$(stat -c %a "$WORK/extracted")" = 700 ] && ok "  ...unpacked into a private directory" || no "  ...unpacked into a private directory"
cmp -s "$WORK/extracted/env" "$WORK/fixture.env" && ok "  ...recovered .env matches the original" || no "  ...recovered .env matches the original"

echo "== drill from the remote"
rm -rf "${WORK:?}/remote"/*; run -- "$OPS/backup-science-bank.sh" >/dev/null 2>&1
run -- "$OPS/restore-drill.sh" --identity "$WORK/id.txt" --from-remote latest >"$WORK/drill6.out" 2>&1
expect "--from-remote latest passes" 0 $?

echo
echo "passed: $PASS   failed: $FAILS"
[ "$FAILS" = 0 ]
