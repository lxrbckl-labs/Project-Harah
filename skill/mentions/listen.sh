#!/usr/bin/env bash
# harah mention listener: poll Alex's repos for `@harah` and dispatch a scoped
# Harah session for each new one. Effectively an event listener at ~5 min
# latency, without exposing a webhook endpoint to the internet.
#
# Pass --dry-run to report what it WOULD pick up without dispatching a session.
# Single-flight; logs to ~/Library/Logs/harah-mentions.log.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LOG="$HOME/Library/Logs/harah-mentions.log"
LOCK="${TMPDIR:-/tmp}/harah-mentions.lock"

if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi   # quiet: this polls often
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

command -v gh >/dev/null || { echo "$(date '+%F %T') ERROR: gh missing" >> "$LOG"; exit 0; }
gh auth status >/dev/null 2>&1 || { echo "$(date '+%F %T') ERROR: gh not authenticated" >> "$LOG"; exit 0; }

out="$(python3 "$HERE/scan.py" "$@" 2>&1)"
# Only write a log entry when something actually happened — this runs every
# 5 minutes and a heartbeat line per poll would bury the real events.
if [ -n "$out" ] && ! printf '%s' "$out" | grep -q '^no new @harah mentions$'; then
  { echo "===== $(date '+%FT%T%z') mention pass ====="; printf '%s\n' "$out"; } >> "$LOG"
fi
