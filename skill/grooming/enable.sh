#!/usr/bin/env bash
# Install the harah repo-grooming launchd job (daily 04:30). Run on the MINI.
# Self-locating: the plist points at groom.sh beside THIS script, so it works
# from any checkout of Project-Harah (re-run me after moving the checkout).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-grooming.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alex.harah-grooming</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>$HERE/groom.sh</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>4</integer><key>Minute</key><integer>30</integer>
  </dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/harah-grooming.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/harah-grooming.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl list | grep harah-grooming && echo "✓ harah grooming installed (daily 04:30)"
