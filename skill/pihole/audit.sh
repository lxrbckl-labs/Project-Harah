#!/usr/bin/env bash
# Pi-hole leak audit — weekly (Sunday 20:00), on the MINI, launchd label
# com.alex.harah-pihole. Looks at what the Pi-hole PERMITTED over the past week,
# picks out the hostnames shaped like ads, trackers or telemetry (pihole.py
# leaks), and hands that shortlist to a headless Claude agent (audit-prompt.md)
# to judge and write up. Default posture is PROPOSE: the report lands in
# ~/.harah/pihole-audit-report.md and Alex gets one text; nothing is denied.
# Alex (2026-11-12): "a skill to occasionally observe history and look for ads
# that made it through we can add to the list". The knob for APPLY mode is the
# file ~/.harah/pihole-audit-apply (Alex creates it; the agent may then run
# `pihole.py deny` for clear-cut ad hosts and must say so in the report).
# Quiet routine: logs a banner only when it runs; state in pihole-state.json
# tells doctor.sh when it last ran. Always exits 0 (launchd keeps the schedule).
#   --dry-run   gather the shortlist and print the prompt; no agent, no text.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/Library/Logs/harah-pihole.log"
STATE="$HOME/.harah/pihole-state.json"
REPORT="$HOME/.harah/pihole-audit-report.md"
APPLY_KNOB="$HOME/.harah/pihole-audit-apply"
LOCK="${TMPDIR:-/tmp}/harah-pihole.lock"
CLAUDE="/opt/homebrew/bin/claude"
WINDOW_H=168
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

mkdir -p "$HOME/.harah" "$(dirname "$LOG")"
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv "$LOG" "$LOG.1"
if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
# Append to the log only; launchd already captures stdout into the same file, so
# tee would double every line (groom.sh scar, docs/dev-notes.md). Echo for a human.
log() { printf '%s\n' "$*" >> "$LOG"; [ -t 1 ] && printf '%s\n' "$*"; return 0; }
log "===== $(date '+%FT%T%z') pihole audit (window ${WINDOW_H}h, $([ -f "$APPLY_KNOB" ] && echo apply || echo propose) mode$([ $DRY = 1 ] && echo ', dry run')) ====="

text_alex() {
  local target_file="$HOME/.harah/heartbeat-target" msg="$1"
  [ -s "$target_file" ] || return 0
  local to; to="$(head -1 "$target_file" | tr -d '[:space:]')"
  local esc; esc="$(printf '%s' "$msg" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
  osascript -e "tell application \"Messages\" to send \"$esc\" to buddy \"$to\" of (service 1 whose service type is iMessage)" >/dev/null 2>&1 || true
}
write_state() {  # $1 outcome, $2 candidates, $3 note; a dry run leaves the real state alone
  [ $DRY = 1 ] && return 0
  printf '{"last_run":"%s","outcome":"%s","candidates":%s,"mode":"%s","report":"%s","note":"%s"}\n' \
    "$(date '+%FT%T%z')" "$1" "${2:-0}" "$([ -f "$APPLY_KNOB" ] && echo apply || echo propose)" "$REPORT" "$3" > "$STATE"
}

health="$(docker inspect -f '{{.State.Health.Status}}' pihole 2>/dev/null || echo missing)"
if [ "$health" != "healthy" ]; then
  log "ERROR: pihole container is $health; skipping the audit"
  write_state error 0 "pihole container $health"
  text_alex "🔴 Pi-hole is $health on the mini; the weekly ad audit skipped. docker ps / docker logs pihole. — Harah"
  exit 0
fi

SHORTLIST="$(python3 "$HERE/pihole.py" leaks --since "$WINDOW_H" --json 60 2>>"$LOG")" || {
  log "ERROR: pihole.py leaks failed (see above)"; write_state error 0 "pihole.py leaks failed"; exit 0; }
COUNT="$(printf '%s' "$SHORTLIST" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)["candidates"]))' 2>/dev/null || echo 0)"
log "shortlist: $COUNT permitted hostnames shaped like ads/trackers in the last ${WINDOW_H}h"

if [ "$COUNT" = "0" ]; then
  write_state clean 0 "nothing leaked"
  { echo "# Pi-hole audit $(date '+%F')"; echo; echo "Nothing permitted in the last ${WINDOW_H}h looked like an ad or tracker. — Harah"; } > "$REPORT"
  log "clean week; no text"
  exit 0
fi

PROMPT="$(cat "$HERE/audit-prompt.md")
MODE: $([ -f "$APPLY_KNOB" ] && echo APPLY || echo PROPOSE)
REPORT PATH: $REPORT
TOOL: python3 $HERE/pihole.py
CURRENT ALLOW/DENY ENTRIES:
$(python3 "$HERE/pihole.py" domains 2>/dev/null || echo '(unavailable)')
SHORTLIST (JSON, from pihole.py leaks --since ${WINDOW_H} --json):
$SHORTLIST"

if [ $DRY = 1 ]; then
  log "dry run: prompt is $(printf '%s' "$PROMPT" | wc -c | tr -d ' ') bytes; first candidates:"
  printf '%s' "$SHORTLIST" | python3 -c 'import sys,json; [print("  ", c["queries"], c["domain"], c["signals"]) for c in json.load(sys.stdin)["candidates"][:10]]' | tee -a "$LOG"
  write_state dry-run "$COUNT" "dry run, no agent"
  exit 0
fi

if [ ! -x "$CLAUDE" ]; then
  log "ERROR: $CLAUDE missing; shortlist written without judgment"
  { echo "# Pi-hole audit $(date '+%F') — unjudged shortlist (claude CLI missing)"; echo; printf '%s\n' "$SHORTLIST"; } > "$REPORT"
  write_state error "$COUNT" "claude CLI missing"
  text_alex "🟡 Pi-hole audit: $COUNT permitted hosts look like ads, but the claude CLI is missing on the mini; raw list in $REPORT. — Harah"
  exit 0
fi

OUT="$("$CLAUDE" --dangerously-skip-permissions -p "$PROMPT" 2>>"$LOG")"
rc=$?
printf '%s\n' "$OUT" | tail -n 20 >> "$LOG"
STATUS="$(printf '%s\n' "$OUT" | /usr/bin/grep -Eo 'HARAH_PIHOLE: .*' | tail -n 1)"
if [ $rc -ne 0 ] || [ -z "$STATUS" ]; then
  log "ERROR: agent exit $rc, status line ${STATUS:-missing}"
  write_state error "$COUNT" "agent exit $rc"
  text_alex "🟡 Pi-hole audit ran into trouble (agent exit $rc); $COUNT candidates waiting in $REPORT. — Harah"
  exit 0
fi
log "$STATUS"
write_state ok "$COUNT" "$STATUS"
if [ -f "$APPLY_KNOB" ]; then
  text_alex "🟢 Pi-hole audit: $STATUS. Report: $REPORT — Harah"
else
  text_alex "🟡 Pi-hole audit: $COUNT permitted hosts look like ads/trackers; proposals in $REPORT. Say the word and Harah denies them (pihole.py deny). — Harah"
fi
exit 0
