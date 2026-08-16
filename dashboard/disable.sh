#!/usr/bin/env bash
# Stop and uninstall the ServerManager dashboard launchd service.
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.lxrbckl.servermanager-dashboard.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ dashboard service stopped and uninstalled (plist removed)"
