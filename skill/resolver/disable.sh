#!/usr/bin/env bash
# Stop and uninstall the harah resolver launchd job.
# Grooming and the alert watch are unaffected — this only stops the session
# that does resolution work.
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-resolver.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✓ harah resolver stopped and uninstalled"
