#!/usr/bin/env bash
# Install the harah mention listener (every 5 min). Run on the MINI.
# GUI domain: the dispatched `claude -p` session needs the login Keychain.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.alex.harah-mentions.plist"

case "$HERE" in
  "$HOME"/Documents/*|"$HOME"/Desktop/*|"$HOME"/Downloads/*)
    echo "ERROR: TCC-protected directory — launchd cannot run scripts here (exit 126)." >&2
    echo "  Move the checkout (e.g. ~/lxrbckl-dev/Project-Harah) and re-run." >&2
    exit 2 ;;
esac

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.alex.harah-mentions</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string>
    <string>$HERE/listen.sh</string>
  </array>
  <key>StartInterval</key><integer>300</integer>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/harah-mentions.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/harah-mentions.log</string>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl list | grep harah-mentions && echo "✓ harah mention listener installed (every 5 min, @harah)"
