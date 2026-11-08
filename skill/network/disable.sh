#!/usr/bin/env bash
# Remove the harah network launchd job. State in ~/.harah/network-state.json is kept.
set -uo pipefail
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-network.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ harah network removed"
