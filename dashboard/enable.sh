#!/usr/bin/env bash
# Install the ServerManager dashboard as a launchd service. Run on the MINI.
#
# Why this exists: the dashboard used to be hand-started in a terminal, so it
# was an orphan process (parent = launchd, nothing managing it) — it did not
# survive a reboot and nothing restarted it if it died. KeepAlive + RunAtLoad
# fix both.
#
# Self-locating: the plist points at the backend beside THIS script, so it
# works from any checkout of Project-Harah (re-run me after moving it).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$HERE/backend"
UVICORN="$BACKEND/.venv/bin/uvicorn"
PLIST="$HOME/Library/LaunchAgents/com.lxrbckl.servermanager-dashboard.plist"
LOG="$HOME/Library/Logs/servermanager-dashboard.log"
PORT=8770

if [ ! -x "$UVICORN" ]; then
  echo "ERROR: no venv at $UVICORN" >&2
  echo "  fix: python3 -m venv $BACKEND/.venv && $BACKEND/.venv/bin/pip install -r $BACKEND/requirements.txt" >&2
  exit 1
fi
if [ ! -d "$HERE/web/dist" ]; then
  echo "WARN: $HERE/web/dist missing — the API will serve but the UI will 404."
  echo "      fix: (cd $HERE/web && npm install && npm run build)"
fi

# Release :$PORT from any hand-started uvicorn so launchd can own it.
for pid in $(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t 2>/dev/null || true); do
  if ps -p "$pid" -o command= | grep -q uvicorn; then
    echo "stopping hand-started uvicorn (pid $pid) holding :$PORT"
    kill "$pid" 2>/dev/null || true
  fi
done

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.lxrbckl.servermanager-dashboard</string>
  <key>ProgramArguments</key><array>
    <string>$UVICORN</string>
    <string>app:app</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>$PORT</string>
    <string>--log-level</string><string>warning</string>
  </array>
  <key>WorkingDirectory</key><string>$BACKEND</string>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

# Verify it actually came up rather than trusting bootstrap's exit code.
# 40s, not 15 — under launchd the first bind observed ~20s here (2026-08-16).
for _ in $(seq 1 40); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/api/health" 2>/dev/null; then
    echo "✓ dashboard service installed and healthy on :$PORT (KeepAlive, RunAtLoad)"
    exit 0
  fi
  sleep 1
done
echo "ERROR: service installed but /api/health never answered — see $LOG" >&2
exit 1
