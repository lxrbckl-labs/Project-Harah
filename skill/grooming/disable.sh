#!/usr/bin/env bash
# Remove the harah repo-grooming launchd job.
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-grooming.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null && echo "grooming job unloaded" || echo "(was not loaded)"
rm -f "$PLIST" && echo "plist removed"
