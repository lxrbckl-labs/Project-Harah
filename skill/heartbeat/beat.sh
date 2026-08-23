#!/usr/bin/env bash
# Harah heartbeat — the dead-man's switch (Alex, 2026-08-23: "if I found out a
# week from now that it did nothing... I'm going to quit my hobby of clauding").
# Once a day: run doctor.sh, distill one line, and TEXT it to Alex's self-chat.
# The guarantee is two-layer: an unhealthy system texts its failures loudly;
# and if the daily text ever just STOPS, that absence is itself the alarm.
# Read-only apart from the message + log. Always exits 0.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/Library/Logs/harah-heartbeat.log"
mkdir -p "$HOME/Library/Logs" "$HOME/.harah"
TARGET_FILE="$HOME/.harah/heartbeat-target"   # iMessage handle (Alex's own), one line
ts() { date '+%Y-%m-%d %H:%M:%S'; }

report="$(bash "$HERE/../doctor.sh" 2>&1 || true)"
dead=$(printf '%s' "$report" | grep -c '✗' || true)
warn=$(printf '%s' "$report" | grep -c '⚠' || true)
alive=$(printf '%s' "$report" | grep -c '✓ alive' || true)
blocked=""
[ -f "$HOME/.harah/operator-blocked.json" ] && blocked=" · operator-blocked items open"

if [ "${dead:-0}" -gt 0 ]; then
  msg="🔴 HARAH UNHEALTHY: $dead routine(s) DEAD, $warn warning(s), $alive alive$blocked. Run doctor.sh on the mini. — Harah"
elif [ "${warn:-0}" -gt 0 ]; then
  msg="🟡 Harah: $alive routine(s) alive, $warn warning(s)$blocked. doctor.sh has details. — Harah"
else
  msg="🟢 Harah alive: $alive/$alive routines healthy$blocked. — Harah"
fi

echo "$(ts) $msg" >> "$LOG"
printf '%s\n' "$report" >> "$LOG"

sent=0
if [ -f "$TARGET_FILE" ]; then
  TARGET="$(head -1 "$TARGET_FILE" | tr -d '[:space:]')"
  if [ -n "$TARGET" ]; then
    if osascript -e "tell application \"Messages\" to send \"$msg\" to buddy \"$TARGET\" of (service 1 whose service type is iMessage)" >/dev/null 2>&1; then
      sent=1
    else
      echo "$(ts) iMessage send FAILED (automation permission? target?)" >> "$LOG"
    fi
  fi
fi
if [ "$sent" = 0 ]; then
  osascript -e "display notification \"$msg\" with title \"Harah heartbeat\"" 2>/dev/null || true
  echo "$(ts) no heartbeat-target configured — notification fallback only. Write Alex's iMessage handle to $TARGET_FILE" >> "$LOG"
fi
exit 0
