#!/usr/bin/env bash
# Stop and uninstall the harah alert-watch launchd job.
# Note: this leaves grooming at whatever cadence the last alert pass set. To
# return grooming to daily 04:30, run: skill/grooming/set-cadence.sh baseline
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-alerts.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ harah alert watch stopped and uninstalled"
