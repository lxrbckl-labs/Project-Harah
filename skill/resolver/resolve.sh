#!/usr/bin/env bash
# harah resolver: a scheduled Harah SESSION that actually resolves dependency
# alerts — the thing groom.sh structurally cannot do.
#
# groom.sh merges the narrow safe class or queues; it contains no resolution
# logic and never will. POLICY.md's resolve-and-verify mandate presupposes an
# agent session, so this runner provides one on a schedule: launchd -> headless
# `claude -p` with the standing brief in prompt.md.
#
# A RUN IS A LOOP, NOT ONE SESSION (Alex, 2026-08-16: "resolve everything, each
# run"). One `claude -p` session has finite context, so a single call cannot
# clear a 200-alert board. The runner therefore starts successive sessions and
# keeps going until a session reports nothing actionable is left. Each session
# re-reads the doctrine and re-derives the work from live data, so the loop
# always continues against current state.
#
# The loop stops on: EXHAUSTED / BLOCKED, no measurable progress across two
# consecutive sessions, or MAX_SESSIONS. Those are futility guards, not work
# quotas — they only fire when sessions have stopped resolving anything.
#
# Pass --dry-run for a single ANALYSE-AND-REPORT session (no branches, pushes,
# merges, or comments) — use it to verify plumbing.
#
# Single-flight; logs to ~/Library/Logs/harah-resolver.log.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROMPT="$HERE/prompt.md"
LOG="$HOME/Library/Logs/harah-resolver.log"
LOCK="${TMPDIR:-/tmp}/harah-resolver.lock"
CLAUDE="/opt/homebrew/bin/claude"
MAX_SESSIONS="${HARAH_MAX_SESSIONS:-12}"   # runaway guard, not a work quota
ORG="lxrbckl-labs"

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

# Single-flight. A run can now last hours; if the next 6h fire arrives while one
# is still going it skips rather than stacking two agents on the same branches.
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') skip: a resolver run is still active" >> "$LOG"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

command -v gh >/dev/null || { echo "$(date '+%F %T') ERROR: gh missing" >> "$LOG"; exit 0; }
gh auth status >/dev/null 2>&1 || { echo "$(date '+%F %T') ERROR: gh not authenticated" >> "$LOG"; exit 0; }
[ -x "$CLAUDE" ] || { echo "$(date '+%F %T') ERROR: claude CLI missing at $CLAUDE" >> "$LOG"; exit 0; }

open_alerts() {
  gh api "/orgs/$ORG/dependabot/alerts?state=open&per_page=100" --paginate \
     --jq '.[].number' 2>/dev/null | wc -l | tr -d ' '
}

{
  echo "===== $(date '+%FT%T%z') START harah-resolver$([ "$DRY" = 1 ] && echo ' (DRY RUN)') ====="
  # Strip YAML frontmatter: passed to `claude -p` as an argument, a leading
  # '---' is parsed as a CLI option and claude aborts with "unknown option".
  BASE="$(awk 'NR==1 && /^---$/{fm=1; next} fm && /^---$/{fm=0; next} !fm' "$PROMPT")"

  if [ "$DRY" = "1" ]; then
    "$CLAUDE" --dangerously-skip-permissions -p "$BASE

## THIS RUN IS A DRY RUN — REPORT ONLY
Do NOT create branches, push, open PRs, comment, or merge anything. Read the
doctrine and the alert list, then report what you WOULD do, in priority order.
Making no change is the whole point of this mode."
    echo "===== $(date '+%FT%T%z') END harah-resolver (dry run) ====="
    exit 0
  fi

  start_count="$(open_alerts)"
  echo "--- open alerts at start: $start_count ---"
  stale=0
  session=1
  while [ "$session" -le "$MAX_SESSIONS" ]; do
    before="$(open_alerts)"
    echo "----- session $session/$MAX_SESSIONS (open alerts: $before) -----"

    out="$("$CLAUDE" --dangerously-skip-permissions -p "$BASE

## Loop position
You are session $session of at most $MAX_SESSIONS in this run. Open alerts in
$ORG right now: $before. Earlier sessions in this run have already done work —
re-derive everything from live data and do not assume anything they reported." 2>&1)"
    code=$?
    printf '%s\n' "$out"

    status="$(printf '%s' "$out" | grep -Eo 'HARAH_STATUS:[[:space:]]*(MORE_WORK|EXHAUSTED|BLOCKED)' | tail -1 | awk '{print $2}')"
    after="$(open_alerts)"
    echo "--- session $session done (exit $code, status ${status:-NONE}, alerts $before -> $after) ---"

    if [ "$code" -ne 0 ]; then
      echo "STOP: session exited $code"; break
    fi
    case "$status" in
      EXHAUSTED) echo "STOP: nothing actionable left"; break ;;
      BLOCKED)   echo "STOP: session reported BLOCKED"; break ;;
    esac
    # Futility guard: if two sessions in a row change nothing, more sessions
    # won't either — a missing status line alone is not a reason to stop.
    if [ "$after" = "$before" ]; then
      stale=$((stale+1))
      if [ "$stale" -ge 2 ]; then echo "STOP: two consecutive sessions made no progress"; break; fi
    else
      stale=0
    fi
    session=$((session+1))
  done

  end_count="$(open_alerts)"
  echo "--- run complete: open alerts $start_count -> $end_count (closed $((start_count - end_count))) over $session session(s) ---"
  echo "===== $(date '+%FT%T%z') END harah-resolver ====="
} >> "$LOG" 2>&1
