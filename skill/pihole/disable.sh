#!/usr/bin/env bash
# Remove the weekly Pi-hole leak audit. Run on the MINI.
set -uo pipefail
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-pihole.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ harah pihole audit removed"
