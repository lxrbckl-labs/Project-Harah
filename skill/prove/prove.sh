#!/usr/bin/env bash
# harah prove (layer 3): every 10 minutes, did a deploy land, and if so does the
# app still do what it did before? prove.py acts only on an image change and
# compares against the last known-good baseline. Logs only on events, like the
# watchdog, so a quiet estate stays quiet.
#
# On a REGRESSION: log it and hand the container to incident/respond.py, whose
# scope is confirm -> restart -> roll BACK -> escalate. Never ships forward.
# Alex decides the durable fix. No text: Harah does not message Alex (2026-11-14).
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/Library/Logs/harah-prove.log"
LOCK="${TMPDIR:-/tmp}/harah-prove.lock"
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv "$LOG" "$LOG.1"
if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

out="$(python3 "$HERE/prove.py" "$@" 2>&1)"; code=$?


regressed=""
while IFS= read -r line; do
  case "$line" in
    "REGRESSION: "*)
      rest="${line#REGRESSION: }"; ctr="${rest%% *}"
      case " $regressed " in *" $ctr "*) ;; *)
        regressed="$regressed $ctr"
        echo "--- regression, responding: $ctr" >> "$LOG"
        nohup python3 "$HERE/../incident/respond.py" "$ctr" >> "$LOG" 2>&1 &
      esac ;;
  esac
done <<< "$out"

if [ -n "$regressed" ]; then
  n="$(printf '%s' "$out" | grep -c '^REGRESSION: ')"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) 🔴 Harah prove: a deploy lost functionality on$regressed ($n check(s) regressed). Incident response running; rollback only, no forward ship." >> "$HOME/Library/Logs/harah-prove.log"
fi

if [ "$code" -ne 0 ] || printf '%s' "$out" | grep -qE '^(REGRESSION|PROVED|BASELINE|WARNING):'; then
  { echo "===== $(date '+%FT%T%z') prove ====="; printf '%s\n' "$out"; } >> "$LOG"
fi
exit 0
