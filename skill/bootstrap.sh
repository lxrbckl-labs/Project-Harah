#!/usr/bin/env bash
# Harah self-deploy — one idempotent command that takes a mini from "doctrine
# on disk" to "machinery running 24/7". Standing-authorized (Alex, 2026-08-23):
# ANY Harah session on the mini that finds routines dead runs this — the
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

for r in watchdog mentions alerts grooming resolver heartbeat; do
  echo "── enabling $r"
  bash "$HERE/$r/enable.sh" || echo "⚠ $r enable failed — doctor will show it; keep going"
done

if [ ! -s "$HOME/.harah/heartbeat-target" ]; then
  # Auto-derive from the Aug-21 alerter, which already texts Alex's self-chat:
  # first +1XXXXXXXXXX-shaped handle in its run.sh is the target.
  derived=""
  if [ -f "$HOME/.imessage-watchdog/run.sh" ]; then
    derived="$(grep -oE '\+1[0-9]{10}' "$HOME/.imessage-watchdog/run.sh" 2>/dev/null | head -1)"
  fi
  if [ -n "$derived" ]; then
    printf '%s\n' "$derived" > "$HOME/.harah/heartbeat-target"
    echo "✓ heartbeat-target derived from the alerter: $derived"
  else
    echo "⚠ ~/.harah/heartbeat-target is empty and could not be derived — heartbeat"
    echo "  texts can't send (notification-only). Write Alex's iMessage handle there."
  fi
fi

echo "── first heartbeat (proof of life to Alex's phone):"
bash "$HERE/heartbeat/beat.sh"
echo "── doctor verdict:"
bash "$HERE/doctor.sh"
