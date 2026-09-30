#!/usr/bin/env bash
# Dead-man's switch for the Science Bank backups. Alerts when no successful backup has landed recently, which
# catches the case the backup script cannot: the script (or its timer) never ran at all.
#
# Usage: check-backup-health.sh [--check-remote]
#   --check-remote   also list the remote and require its newest artifact to be fresh, so an upload that "succeeds"
#                    into the wrong place, or remote files that were deleted, are noticed too.
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
  newest="$(rclone lsf "$RCLONE_REMOTE" --files-only 2>>"$LOG_FILE" | grep -E "$ARTIFACT_RE" | sort | tail -1)"
  if [ -z "$newest" ]; then
    problems+=("remote $RCLONE_REMOTE: no backups listed (or the remote could not be reached)")
  else
    remote_age=$(awk -v now="$(date +%s)" -v then="$(name_epoch "$newest")" 'BEGIN { printf "%.1f", (now - then) / 3600 }')
    stale "$remote_age" && problems+=("remote newest backup is ${remote_age}h old (limit ${MAX_AGE_HOURS}h): $newest")
  fi
fi

if [ "${#problems[@]}" -gt 0 ]; then
  summary="$(printf '%s; ' "${problems[@]}")"
  log "ALERT: $summary"
  notify "Science Bank backups stale or unverifiable" "$summary Check the timers and $LOG_FILE on this host." urgent
  exit 1
fi
log "OK: local $(marker_age_hours last-local-success)h, upload $(marker_age_hours last-upload-success)h since last success"
