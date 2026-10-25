#!/usr/bin/env bash
# Remove the harah prove launchd job. State in ~/.harah/prove-state.json is kept.
set -uo pipefail
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-prove.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ harah prove removed"
