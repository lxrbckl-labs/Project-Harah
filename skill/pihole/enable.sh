#!/usr/bin/env bash
# Install the weekly Pi-hole leak audit (Sunday 20:00). Run on the MINI. Idempotent.
# The plist points at audit.sh beside this script, so the checkout can move.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$HERE" in "$HOME"/Documents/*|"$HOME"/Desktop/*|"$HOME"/Downloads/*)
  echo "ERROR: TCC-protected dir; launchd cannot run scripts from $HERE" >&2; exit 2 ;; esac
LABEL="com.alex.harah-pihole"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.harah"
cat > "$PLIST" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$HERE/audit.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>20</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/harah-pihole.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/harah-pihole.log</string>
</dict></plist>
XML
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl enable "gui/$(id -u)/$LABEL" 2>/dev/null || true   # a disabled label fails bootstrap with "5: Input/output error"
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl list | /usr/bin/grep -q harah-pihole && echo "✓ harah pihole audit installed (Sundays 20:00). Test: launchctl kickstart -k gui/$(id -u)/$LABEL; tail -20 ~/Library/Logs/harah-pihole.log"
