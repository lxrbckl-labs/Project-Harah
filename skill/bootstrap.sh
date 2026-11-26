#!/usr/bin/env bash
# Harah self-deploy — one idempotent command that takes a mini from "doctrine
# on disk" to "machinery running 24/7". Standing-authorized (Alex, 2026-08-23):
# ANY Harah session on the mini that finds routines dead runs this (mentions retired 2026-10-25) — the
# machinery being down is itself a maintenance failure Harah owns.
# Safe to re-run any time; enable scripts are idempotent.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(cat "$HOME/.claude/machine-identity" 2>/dev/null)" != "Alexs-Mac-mini" ]; then
  echo "✗ Not the mini ($(cat "$HOME/.claude/machine-identity" 2>/dev/null || echo unknown)) — the routines run ONLY there. Nothing done."
  exit 1
fi

# Fresh-machine proofing (sandbox drill 2026-08-23): four enable scripts
# write plists assuming these dirs exist — true only on an aged machine.
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs" "$HOME/.harah"

git -C "$HERE/.." pull --rebase --autostash 2>/dev/null || echo "⚠ pull failed — deploying the code already on disk"

for r in watchdog prove alerts grooming resolver; do
  echo "── enabling $r"
  bash "$HERE/$r/enable.sh" || echo "⚠ $r enable failed — doctor will show it; keep going"
done

# No texts: Alex (2026-11-14) wants Harah to do its job in the background and
# never message him about it. The heartbeat routine is retired and nothing here
# writes ~/.harah/heartbeat-target; a leftover copy is moved aside so the
# remaining routines' text paths stay dark.
if [ -s "$HOME/.harah/heartbeat-target" ]; then
  mv "$HOME/.harah/heartbeat-target" "$HOME/.harah/heartbeat-target.off"
  echo "✓ heartbeat-target moved aside: Harah does not text"
fi
launchctl bootout "gui/$(id -u)/com.alex.harah-heartbeat" 2>/dev/null && echo "✓ retired heartbeat routine unloaded" || true
rm -f "$HOME/Library/LaunchAgents/com.alex.harah-heartbeat.plist"
echo "── doctor verdict:"
bash "$HERE/doctor.sh"
