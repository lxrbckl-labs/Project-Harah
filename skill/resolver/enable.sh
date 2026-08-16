#!/usr/bin/env bash
# Install the harah resolver launchd job (daily 05:30, after grooming). Run on
# the MINI. Self-locating: the plist points at resolve.sh beside THIS script.
#
# Runs in the GUI domain deliberately — headless `claude -p` needs the login
# Keychain for its OAuth subscription token; a system-domain daemon cannot
# reach it and the agent dies silently.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-resolver.plist"

case "$HERE" in
  "$HOME"/Documents/*|"$HOME"/Desktop/*|"$HOME"/Downloads/*)
    echo "ERROR: this checkout is under a TCC-protected directory." >&2
    echo "  launchd cannot run scripts from there (exit 126, 'Operation not permitted')." >&2
    echo "  Move the checkout (e.g. ~/lxrbckl-dev/Project-Harah) and re-run." >&2
    exit 2 ;;
esac

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alex.harah-resolver</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>$HERE/resolve.sh</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>5</integer><key>Minute</key><integer>30</integer>
  </dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/harah-resolver.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/harah-resolver.log</string>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl list | grep harah-resolver && echo "✓ harah resolver installed (daily 05:30)"
