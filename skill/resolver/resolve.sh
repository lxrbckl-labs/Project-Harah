#!/usr/bin/env bash
# harah resolver: a scheduled Harah SESSION that actually resolves dependency
# alerts — the thing groom.sh structurally cannot do.
#
# groom.sh merges the narrow safe class or queues; it contains no resolution
# logic and never will. POLICY.md's resolve-and-verify mandate presupposes an
# agent session, so this runner provides one on a schedule: launchd -> headless
# `claude -p` with the standing brief in prompt.md.
#
# Pass --dry-run to have the session ANALYSE and REPORT ONLY — no branches, no
# pushes, no merges, no comments. Use it to verify the plumbing.
#
# Single-flight; logs to ~/Library/Logs/harah-resolver.log.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROMPT="$HERE/prompt.md"
LOG="$HOME/Library/Logs/harah-resolver.log"
LOCK="${TMPDIR:-/tmp}/harah-resolver.lock"
CLAUDE="/opt/homebrew/bin/claude"

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

# Single-flight: a resolution run can take a long time. Never stack two agents
# on the same repos — concurrent merges on one branch is exactly how history
# gets mangled.
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') skip: a resolver run is still active" >> "$LOG"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

command -v gh >/dev/null || { echo "$(date '+%F %T') ERROR: gh missing" >> "$LOG"; exit 0; }
gh auth status >/dev/null 2>&1 || { echo "$(date '+%F %T') ERROR: gh not authenticated" >> "$LOG"; exit 0; }
[ -x "$CLAUDE" ] || { echo "$(date '+%F %T') ERROR: claude CLI missing at $CLAUDE" >> "$LOG"; exit 0; }

{
  echo "===== $(date '+%FT%T%z') START harah-resolver$([ "$DRY" = 1 ] && echo ' (DRY RUN)') ====="
  # Strip YAML frontmatter: passed to `claude -p` as an argument, a leading
  # '---' is parsed as a CLI option and claude aborts with "unknown option".
  BODY="$(awk 'NR==1 && /^---$/{fm=1; next} fm && /^---$/{fm=0; next} !fm' "$PROMPT")"
  if [ "$DRY" = "1" ]; then
    BODY="$BODY

## THIS RUN IS A DRY RUN — REPORT ONLY
Do NOT create branches, push, open PRs, comment, or merge anything. Read the
doctrine and the alert list, then report what you WOULD do this run and why,
in priority order. Making no change is the whole point of this mode."
  fi
  "$CLAUDE" --dangerously-skip-permissions -p "$BODY"
  code=$?
  echo "===== $(date '+%FT%T%z') END harah-resolver (exit $code) ====="
} >> "$LOG" 2>&1
