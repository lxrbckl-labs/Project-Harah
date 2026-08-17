#!/usr/bin/env bash
# harah watchdog: every 10 minutes, is everything still serving?
# READ-ONLY — reports, never restarts or rolls back. Logs only on a change of
# state, so a healthy estate stays silent instead of burying real events.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/Library/Logs/harah-watchdog.log"
LOCK="${TMPDIR:-/tmp}/harah-watchdog.lock"
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv "$LOG" "$LOG.1"
if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
out="$(python3 "$HERE/watch.py" 2>&1)"; code=$?

# Alex, 2026-08-17: don't wait for him to look — investigate and fix.
# Only NEW failures trigger a response. respond.py re-confirms before acting,
# rate-limits itself, refuses to restart stateful services, and escalates to a
# thinking session rather than thrashing. Backgrounded so a slow incident
# response never stalls the 10-minute watchdog cadence.
while IFS= read -r line; do
  case "$line" in
    "WENT DOWN: "*)
      tgt="${line#WENT DOWN: }"; tgt="${tgt%% *}"
      echo "--- responding to: $tgt" >> "$LOG"
      nohup python3 "$HERE/../incident/respond.py" "$tgt" >> "$LOG" 2>&1 &
      ;;
  esac
done <<< "$out"
# Log transitions and problems; stay silent on an all-healthy pass.
if [ "$code" -ne 0 ] || printf '%s' "$out" | grep -qE "UNHEALTHY|WENT DOWN|RECOVERED"; then
  { echo "===== $(date '+%FT%T%z') watchdog ====="; printf '%s\n' "$out"; } >> "$LOG"
fi
exit 0
