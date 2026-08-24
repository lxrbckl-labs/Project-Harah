#!/usr/bin/env bash
# harah doctor — one read-only pass over every routine: is it installed, is it
# firing, when did it last actually do something, and what did it last say.
# Run ON THE MINI. Changes nothing; exit code 0 always (it reports, you decide).
#
# Born 2026-08-22 after Alex called the system "disappointing — I have to
# babysit it": the routines fail SILENTLY (Keychain-starved claude -p, dead
# launchd agents, stale checkouts), and nothing said so. Now something says so.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
UID_="$(id -u)"
now=$(date +%s)

hdr() { printf '\n── %s ─────────────────────────────\n' "$1"; }
age() { # age of a file in human terms, or "never"
  local f="$1"
  [ -e "$f" ] || { echo "never"; return; }
  local m; m=$(stat -f %m "$f" 2>/dev/null || echo 0)
  local d=$(( now - m ))
  if   [ "$d" -lt 3600 ];   then echo "$(( d / 60 ))m ago"
  elif [ "$d" -lt 86400 ];  then echo "$(( d / 3600 ))h ago"
  else                           echo "$(( d / 86400 ))d ago"; fi
}

check_routine() { # name label log expected_max_age_hours [state_file]
  # state_file is for TRANSITION-ONLY routines (watchdog, mentions): they log
  # only when something happens, so a quiet log is health, not silence. Their
  # real liveness signal is the state file they rewrite every pass. Without
  # this, doctor reported both ⚠ STALE forever while they ran perfectly —
  # flagged in dev-notes for two sessions before being traced (2026-08-24).
  local name="$1" label="$2" log="$3" max_h="$4" state="${5:-}"
  local loaded="NOT LOADED" lastexit=""
  local row; row=$(launchctl list 2>/dev/null | grep "$label" || true)
  if [ -n "$row" ]; then
    lastexit=$(echo "$row" | awk '{print $2}')
    loaded="loaded (last exit $lastexit)"
  fi
  local a; a=$(age "$log")
  local verdict="?"
  if [ -z "$row" ]; then verdict="✗ DEAD — agent not loaded (run its enable.sh)"
  elif [ "$a" = "never" ]; then
    # Loaded but no log yet: a calendar routine awaiting its first scheduled
    # fire is HEALTHY, not dead — cry-wolf softening (2026-08-23) so the
    # heartbeat's first-night text isn't a false red.
    verdict="⚠ pending — loaded, no log yet (first scheduled run hasn't fired)"
  else
    local m; m=$(stat -f %m "$log" 2>/dev/null || echo 0)
    local sm=0
    [ -n "$state" ] && [ -e "$state" ] && sm=$(stat -f %m "$state" 2>/dev/null || echo 0)
    if [ $(( now - m )) -gt $(( max_h * 3600 )) ] && [ "$sm" -gt 0 ] \
       && [ $(( now - sm )) -le $(( max_h * 3600 )) ]; then
      # Quiet log, fresh state: the routine ran and had nothing to report.
      verdict="✓ alive (quiet — logs only on events; $(basename "$state") $(age "$state"))"
    elif [ $(( now - m )) -gt $(( max_h * 3600 )) ]; then
      verdict="⚠ STALE — no log activity in >$max_h h (expected cadence violated)"
    elif [ -n "$lastexit" ] && [ "$lastexit" != "0" ] && [ "$lastexit" != "-" ]; then
      verdict="⚠ ERRORING — last exit $lastexit (read the log tail below)"
    else
      verdict="✓ alive"
    fi
  fi
  printf '%-10s %-34s log: %-8s %s\n' "$name" "$loaded" "$a" "$verdict"
  if [[ "$verdict" == ✗* || "$verdict" == ⚠* ]] && [ -f "$log" ]; then
    tail -3 "$log" 2>/dev/null | sed 's/^/           | /'
  fi
}

hdr "launchd routines (label · state · last log write · verdict)"
check_routine "watchdog"  "com.alex.harah-watchdog"  "$HOME/Library/Logs/harah-watchdog.log"  1 "$HOME/.harah/watchdog-state.json"
check_routine "mentions"  "com.alex.harah-mentions"  "$HOME/Library/Logs/harah-mentions.log"  1 "$HOME/.harah/mentions-state.json"
check_routine "alerts"    "com.alex.harah-alerts"    "$HOME/Library/Logs/harah-alerts.log"    7
check_routine "grooming"  "com.alex.harah-grooming"  "$HOME/Library/Logs/harah-grooming.log"  26
check_routine "resolver"  "com.alex.harah-resolver"  "$HOME/Library/Logs/harah-resolver.log"  26
check_routine "heartbeat" "com.alex.harah-heartbeat" "$HOME/Library/Logs/harah-heartbeat.log" 26

hdr "the silent killers"
# 1. Keychain: headless claude -p dies without the login keychain. Proxy check:
#    does the LATEST pass show auth-shaped failures?
#
# Two bugs fixed here 2026-08-24, because between them they manufactured the
# false evidence that sent a session chasing a phantom OAuth failure for a day
# (the real cause was a CLI arg-parsing bug — see dev-notes):
#
#   1. NO TIME WINDOW. The old grep scanned the whole log, so a RESOLVED
#      incident was re-reported as a current "silent killer" forever. The 8
#      real failures here were a closed cluster from 2026-08-20..22; every
#      session since has authed fine, and doctor kept crying about them.
#   2. IT COUNTED ITS OWN PROSE. The pattern matched the bare word "oauth",
#      so a session that WROTE ABOUT the problem in its report — which lands
#      in this same log — incremented the count. 8 real errors read as 9, then
#      10, each session's write-up corroborating the last. Evidence must not
#      be able to breed.
#
# Now: only the most recent pass (text after the last `===== ` banner, a
# marker all three logs share), and only anchored real error shapes, which
# markdown prose about them cannot match.
AUTH_RE='^([0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9:]+ )?(ERROR: gh not authenticated|Failed to authenticate|Invalid API key|Please run /login|Not logged in)'
for lg in harah-resolver harah-grooming harah-mentions; do
  f="$HOME/Library/Logs/$lg.log"
  [ -f "$f" ] || continue
  latest=$(awk '/^===== /{buf=""} {buf=buf $0 "\n"} END{printf "%s", buf}' "$f" 2>/dev/null)
  hits=$(printf '%s' "$latest" | grep -cE "$AUTH_RE" 2>/dev/null || true)
  if [ "${hits:-0}" -gt 0 ]; then
    echo "⚠ $lg.log: $hits auth-shaped error line(s) in the LATEST pass — the Keychain gotcha (scheduler skill):"
    printf '%s' "$latest" | grep -E "$AUTH_RE" | tail -2 | sed 's/^/   | /'
  else
    older=$(grep -cE "$AUTH_RE" "$f" 2>/dev/null || true)
    [ "${older:-0}" -gt 0 ] && echo "✓ $lg.log: latest pass authed fine (${older} historical auth failure(s) earlier in the log — resolved, not current)"
  fi
done
# 2. gh auth (routines read GitHub read-only, but dead auth = empty passes)
gh auth status >/dev/null 2>&1 && echo "✓ gh authenticated" || echo "✗ gh NOT authenticated — alerts/mentions/grooming see nothing"
# 3. Checkout freshness: routines run from this checkout; a stale one runs old code
git -C "$REPO_ROOT" fetch -q origin 2>/dev/null || true
behind=$(git -C "$REPO_ROOT" rev-list HEAD..origin/main --count 2>/dev/null || echo "?")
[ "$behind" = "0" ] && echo "✓ checkout current with origin/main" || echo "⚠ checkout is $behind commit(s) behind origin/main — routines run OLD code (git pull)"
# 4. Cadence state
echo "cadence: grooming=$(cat "$HOME/.harah/grooming-cadence" 2>/dev/null || echo '(default baseline)') resolver=$(cat "$HOME/.harah/resolver-cadence" 2>/dev/null || echo '(default daily)')"

hdr "did the machinery actually produce anything lately?"
for f in "$HOME/.harah"/*; do
  [ -e "$f" ] || continue
  printf '  %-40s %s\n' "$(basename "$f")" "$(age "$f")"
done 2>/dev/null || echo "  (no ~/.harah state at all — machinery has never run here)"

echo
echo "Verdict legend: ✗ needs its enable.sh · ⚠ read the log · ✓ leave it alone."
echo "This script changes nothing. Fix-forward lives in each routine's dir."
exit 0
