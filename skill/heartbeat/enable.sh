#!/usr/bin/env bash
# Install the daily Harah heartbeat (09:00). Run on the MINI. Idempotent.
# First run: write Alex's iMessage handle to ~/.harah/heartbeat-target so the
# beat arrives as a text; without it, macOS-notification fallback only.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.alex.harah-heartbeat"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.harah"
cat > "$PLIST" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$HERE/beat.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/harah-heartbeat.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/harah-heartbeat.log</string>
</dict>
</plist>
XML
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "✓ heartbeat installed (daily 09:00). Test now: bash $HERE/beat.sh"
[ -s "$HOME/.harah/heartbeat-target" ] || echo "⚠ no ~/.harah/heartbeat-target yet — texts won't send until Alex's handle is written there"
