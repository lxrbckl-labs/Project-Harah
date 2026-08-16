#!/usr/bin/env bash
# harah alert watch: read GitHub Dependabot alerts, flag what's NEW since the
# last pass, and set the grooming cadence to match the worst open severity.
#
# READ-ONLY against GitHub — no merges, no comments, no repo writes. The only
# side effect is local state plus grooming's schedule (see grooming/POLICY.md;
# this routine never widens what grooming may merge).
#
# Runs manually from any Mac with gh auth, or on the mini via launchd
# (enable.sh). Single-flight; logs to ~/Library/Logs/harah-alerts.log.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LOG="$HOME/Library/Logs/harah-alerts.log"
LOCK="${TMPDIR:-/tmp}/harah-alerts.lock"
# Keep the log bounded — runs can be long and nothing else rotates this.
# 5 MB, one previous generation kept.
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv "$LOG" "$LOG.1"
log(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

if ! mkdir "$LOCK" 2>/dev/null; then log "skip: another alert pass is running"; exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

command -v gh >/dev/null || { log "ERROR: gh not installed"; exit 0; }
gh auth status >/dev/null 2>&1 || { log "ERROR: gh not authenticated"; exit 0; }

log "alert pass start"
python3 "$HERE/collect.py" 2>&1 | while IFS= read -r line; do log "$line"; done
log "alert pass done"
