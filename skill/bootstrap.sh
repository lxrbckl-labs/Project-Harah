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

git -C "$HERE/.." pull --rebase --autostash 2>/dev/null || echo "⚠ pull failed — deploying the code already on disk"

for r in watchdog mentions alerts grooming resolver heartbeat; do
  echo "── enabling $r"
  bash "$HERE/$r/enable.sh" || echo "⚠ $r enable failed — doctor will show it; keep going"
done

if [ ! -s "$HOME/.harah/heartbeat-target" ]; then
  echo "⚠ ~/.harah/heartbeat-target is empty — heartbeat texts can't send."
  echo "  Write Alex's own iMessage handle there (the Aug-21 alerter's target"
  echo "  in ~/.imessage-watchdog/run.sh is the reference). Notification-only until then."
fi

echo "── first heartbeat (proof of life to Alex's phone):"
bash "$HERE/heartbeat/beat.sh"
echo "── doctor verdict:"
bash "$HERE/doctor.sh"
