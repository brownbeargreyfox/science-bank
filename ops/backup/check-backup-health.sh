#!/usr/bin/env bash
# Dead-man's switch for the Science Bank backups. Alerts when no successful backup has landed recently, which
# catches the case the backup script cannot: the script (or its timer) never ran at all.
#
# Usage: check-backup-health.sh [--check-remote]
#   --check-remote   also list the remote and require (a) its newest artifact to be fresh, (b) that artifact's
#                    signature to actually VERIFY against the allowed-signers file (downloaded, nothing decrypted),
#                    and (c) the last artifact this host uploaded to still be listed. Catches an upload that
#                    "succeeds" into the wrong place, a forged newest file, and deleted or rolled-back remote files.
#
# Exit codes: 0 healthy; 1 alerting.
set -uo pipefail
SCRIPT_TAG=watchdog
# shellcheck source=lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

CHECK_REMOTE=0
case "${1:-}" in
  --check-remote) CHECK_REMOTE=1 ;;
  "") ;;
  *) echo "usage: check-backup-health.sh [--check-remote]" >&2; exit 64 ;;
esac

problems=()
WORK="$(mktemp -d "$STATE_DIR/watchdog.XXXXXX")"
trap 'rm -rf "${WORK:?}"' EXIT
stale() { awk -v a="$1" -v m="$MAX_AGE_HOURS" 'BEGIN { exit !(a > m) }'; }

for marker in last-local-success last-upload-success; do
  age="$(marker_age_hours "$marker")"
  if [ "$age" = never ]; then
    problems+=("$marker: no successful run has ever been recorded")
  elif stale "$age"; then
    problems+=("$marker: ${age}h ago (limit ${MAX_AGE_HOURS}h)")
  fi
done

if [ "$CHECK_REMOTE" = 1 ]; then
  listing="$(rclone lsf "$RCLONE_REMOTE" --files-only 2>>"$LOG_FILE")"
  newest="$(grep -E "$ARTIFACT_RE" <<<"$listing" | sort | tail -1)"
  if [ -z "$newest" ]; then
    problems+=("remote $RCLONE_REMOTE: no backups listed (or the remote could not be reached)")
  else
    remote_age=$(awk -v now="$(date +%s)" -v then="$(name_epoch "$newest")" 'BEGIN { printf "%.1f", (now - then) / 3600 }')
    stale "$remote_age" && problems+=("remote newest backup is ${remote_age}h old (limit ${MAX_AGE_HOURS}h): $newest")
    # A signature that merely exists proves nothing: download both files and verify against the allowed signers.
    # Nothing is decrypted, so no private key is needed here.
    if ! grep -qxF "$newest.sig" <<<"$listing"; then
      problems+=("remote newest backup has no signature file: $newest.sig")
    elif [ ! -r "$SIGNERS_FILE" ]; then
      problems+=("cannot verify the remote signature: no allowed-signers file at $SIGNERS_FILE")
    elif ! rclone copyto "$RCLONE_REMOTE/$newest" "$WORK/artifact" 2>>"$LOG_FILE" ||
      ! rclone copyto "$RCLONE_REMOTE/$newest.sig" "$WORK/artifact.sig" 2>>"$LOG_FILE"; then
      problems+=("could not download the newest remote backup or its signature: $newest")
    elif ! verify_sig "$WORK/artifact" "$WORK/artifact.sig" "$SIGNERS_FILE"; then
      problems+=("remote newest backup signature does not verify (forged or damaged?): $newest")
    fi
    # The backup job records the last artifact it uploaded. If the remote no longer lists it, something deleted it;
    # a rollback to an older genuine backup would otherwise look healthy while that older one is still fresh.
    if [ -s "$STATE_DIR/last-upload-artifact" ]; then
      uploaded="$(head -1 "$STATE_DIR/last-upload-artifact")"
      grep -qxF "$uploaded" <<<"$listing" || problems+=("the last uploaded backup is missing from the remote: $uploaded")
    fi
  fi
fi

if [ "${#problems[@]}" -gt 0 ]; then
  summary="$(printf '%s; ' "${problems[@]}")"
  log "ALERT: $summary"
  notify "Science Bank backups stale or unverifiable" "$summary Check the timers and $LOG_FILE on this host." urgent
  exit 1
fi
log "OK: local $(marker_age_hours last-local-success)h, upload $(marker_age_hours last-upload-success)h since last success"
