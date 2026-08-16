#!/usr/bin/env bash
# Write/refresh the harah grooming launchd job at a given cadence.
#
# This is the single owner of the grooming plist — enable.sh delegates here, and
# the alerts routine calls it to correlate cadence with open alert severity:
#
#   baseline  -> daily 04:30            (no critical/high alerts open)
#   43200     -> every 12h              (high-severity alerts open)
#   21600     -> every 6h               (critical alerts open)
#
# Escalating the cadence only makes grooming run SOONER. It does not change what
# grooming may merge — grooming/POLICY.md remains the only merge authorization.
#
# Self-locating: the plist points at groom.sh beside THIS script.
# Usage: set-cadence.sh <baseline|SECONDS> [reason] [--force]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:?usage: set-cadence.sh <baseline|SECONDS> [reason] [--force]}"
REASON="${2:-}"
FORCE=0
for a in "$@"; do [ "$a" = "--force" ] && FORCE=1; done

PLIST="$HOME/Library/LaunchAgents/com.alex.harah-grooming.plist"
MARK="$HOME/.harah/grooming-cadence"
LOG="$HOME/Library/Logs/harah-alerts.log"

case "$MODE" in
  baseline) ;;
  ''|*[!0-9]*) echo "ERROR: cadence must be 'baseline' or an integer of seconds" >&2; exit 2 ;;
  *) [ "$MODE" -ge 3600 ] || { echo "ERROR: refusing a cadence faster than 1h" >&2; exit 2; } ;;
esac

mkdir -p "$(dirname "$MARK")"
current="$(cat "$MARK" 2>/dev/null || echo "")"
if [ "$FORCE" != "1" ] && [ "$current" = "$MODE" ] && [ -f "$PLIST" ]; then
  exit 0   # already at this cadence — stay quiet
fi

if [ "$MODE" = "baseline" ]; then
  SCHED='  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>4</integer><key>Minute</key><integer>30</integer>
  </dict>'
  HUMAN="daily 04:30"
else
  SCHED="  <key>StartInterval</key><integer>$MODE</integer>"
  HUMAN="every $((MODE / 3600))h"
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alex.harah-grooming</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>$HERE/groom.sh</string>
  </array>
$SCHED
  <key>StandardOutPath</key><string>$HOME/Library/Logs/harah-grooming.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/harah-grooming.log</string>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "$MODE" > "$MARK"

msg="grooming cadence -> $HUMAN"
[ -n "$REASON" ] && msg="$msg ($REASON)"
[ -n "$current" ] && [ "$current" != "$MODE" ] && msg="$msg [was: $current]"
echo "  $msg"
echo "$(date '+%F %T') $msg" >> "$LOG"
