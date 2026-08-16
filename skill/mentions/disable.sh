#!/usr/bin/env bash
# Stop and uninstall the harah mention listener.
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-mentions.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ harah mention listener stopped and uninstalled"
