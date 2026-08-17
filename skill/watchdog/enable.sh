#!/usr/bin/env bash
# Install the harah watchdog (every 10 min). Run on the MINI. Self-locating.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-watchdog.plist"
case "$HERE" in
  "$HOME"/Documents/*|"$HOME"/Desktop/*|"$HOME"/Downloads/*)
    echo "ERROR: TCC-protected dir — launchd can't run scripts here (exit 126)." >&2; exit 2 ;;
esac
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alex.harah-watchdog</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>$HERE/watch.sh</string>
  </array>
  <key>StartInterval</key><integer>600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/harah-watchdog.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/harah-watchdog.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl list | grep harah-watchdog && echo "✓ harah watchdog installed (every 10 min)"
