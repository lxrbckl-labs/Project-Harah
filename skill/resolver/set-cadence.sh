#!/usr/bin/env bash
# Single owner of the harah RESOLVER plist — same pattern as grooming's.
# enable.sh delegates here, and the dashboard's Resolver panel calls it via
# POST /api/resolver/cadence/{choice}.
#
# Usage: set-cadence.sh <daily|SECONDS> [reason] [--force]
#
# A resolver pass is a full Claude session doing real migration work, and on
# this host a merge deploys within ~5 minutes. So the cadence is floored at 6h
# deliberately: nothing may schedule unattended migration work more often than
# that, from the UI or anywhere else.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:?usage: set-cadence.sh <daily|SECONDS> [reason] [--force]}"
REASON="${2:-}"
FORCE=0
for a in "$@"; do [ "$a" = "--force" ] && FORCE=1; done

PLIST="$HOME/Library/LaunchAgents/com.alex.harah-resolver.plist"
MARK="$HOME/.harah/resolver-cadence"
LOG="$HOME/Library/Logs/harah-resolver.log"
FLOOR=21600   # 6h

case "$MODE" in
  daily) ;;
  ''|*[!0-9]*) echo "ERROR: cadence must be 'daily' or an integer of seconds" >&2; exit 2 ;;
  *) [ "$MODE" -ge "$FLOOR" ] || { echo "ERROR: refusing a resolver cadence faster than 6h" >&2; exit 2; } ;;
esac

case "$HERE" in
  "$HOME"/Documents/*|"$HOME"/Desktop/*|"$HOME"/Downloads/*)
    echo "ERROR: TCC-protected directory — launchd cannot run scripts here." >&2; exit 2 ;;
esac

mkdir -p "$(dirname "$MARK")"
current="$(cat "$MARK" 2>/dev/null || echo "")"
if [ "$FORCE" != "1" ] && [ "$current" = "$MODE" ] && [ -f "$PLIST" ]; then
  echo "resolver cadence already $MODE"; exit 0
fi

if [ "$MODE" = "daily" ]; then
  SCHED='  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>5</integer><key>Minute</key><integer>30</integer>
  </dict>'
  HUMAN="daily 05:30"
else
  SCHED="  <key>StartInterval</key><integer>$MODE</integer>"
  HUMAN="every $((MODE / 3600))h"
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alex.harah-resolver</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>$HERE/resolve.sh</string>
  </array>
$SCHED
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "$MODE" > "$MARK"

msg="resolver cadence -> $HUMAN"
[ -n "$REASON" ] && msg="$msg ($REASON)"
[ -n "$current" ] && [ "$current" != "$MODE" ] && msg="$msg [was: $current]"
echo "$msg"
echo "$(date '+%F %T') $msg" >> "$LOG"
