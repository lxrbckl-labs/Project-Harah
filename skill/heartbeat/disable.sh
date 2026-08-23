#!/usr/bin/env bash
set -uo pipefail
LABEL="com.alex.harah-heartbeat"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && echo "✓ heartbeat removed" || echo "was not loaded"
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
