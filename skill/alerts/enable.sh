#!/usr/bin/env bash
# Install the harah alert-watch launchd job (every 6h). Run on the MINI.
# Self-locating: the plist points at alerts.sh beside THIS script, so it works
# from any checkout of Project-Harah (re-run me after moving the checkout).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-alerts.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alex.harah-alerts</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>$HERE/alerts.sh</string>
  </array>
  <key>StartInterval</key><integer>21600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/harah-alerts.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/harah-alerts.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl list | grep harah-alerts && echo "✓ harah alert watch installed (every 6h)"
