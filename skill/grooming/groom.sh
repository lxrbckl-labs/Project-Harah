#!/usr/bin/env bash
# harah repo grooming: keep Alex's repos current amid dependabot.
#
# Policy (the ONLY standing merge authorization — see harah/SKILL.md):
#   - repos owned by lxRbckl or lxrbckl-labs, not archived
#   - PR author is dependabot
#   - patch/minor bump only (parsed from the title) — NEVER major
#   - checks passing where checks exist; failing/errored disqualifies
#   Everything else is left open and reported for Alex.
#
# Runs manually from any Mac with gh auth, or on the mini via launchd
# (enable.sh). Pass --dry-run to report verdicts without merging anything.
# Single-flight; logs to ~/Library/Logs/harah-grooming.log.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

LOG="$HOME/Library/Logs/harah-grooming.log"
LOCK="${TMPDIR:-/tmp}/harah-grooming.lock"
# Keep the log bounded — runs can be long and nothing else rotates this.
# 5 MB, one previous generation kept.
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv "$LOG" "$LOG.1"
OWNERS=(lxRbckl lxrbckl-labs)
log(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

if ! mkdir "$LOCK" 2>/dev/null; then log "skip: another grooming pass is running"; exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

command -v gh >/dev/null || { log "ERROR: gh not installed"; exit 0; }
gh auth status >/dev/null 2>&1 || { log "ERROR: gh not authenticated"; exit 0; }

DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1 && log "DRY RUN — no merges"
STATE_DIR="$HOME/.harah"; STATE="$STATE_DIR/grooming-state.json"
ROWS="$(mktemp)"; trap 'rmdir "$LOCK" 2>/dev/null; rm -f "$ROWS"' EXIT
merged=0; queued=0; checked=0
for owner in "${OWNERS[@]}"; do
  for repo in $(gh repo list "$owner" --no-archived --limit 200 --json nameWithOwner --jq '.[].nameWithOwner'); do
    prs=$(gh pr list -R "$repo" --author "app/dependabot" --state open \
          --json number,title,mergeable,statusCheckRollup 2>>"$LOG") || continue
    [ "$prs" = "[]" ] && continue
    checked=$((checked+1))
    while IFS=$'\t' read -r num title verdict; do
      [ -z "${num:-}" ] && continue
      if [ "$verdict" = "MERGE" ]; then
        if [ "$DRY" = "1" ]; then
          log "would-merge  $repo#$num  $title"; merged=$((merged+1))
          printf 'merged\t%s\t%s\t%s\t%s\n' "$repo" "$num" "$title" "dry-run" >> "$ROWS"
        elif gh pr merge "$num" -R "$repo" --squash >/dev/null 2>>"$LOG"; then
          log "merged  $repo#$num  $title"; merged=$((merged+1))
          printf 'merged\t%s\t%s\t%s\t%s\n' "$repo" "$num" "$title" "" >> "$ROWS"
        else
          log "QUEUED  $repo#$num  $title  (merge attempt failed — needs Alex)"; queued=$((queued+1))
          printf 'queued\t%s\t%s\t%s\t%s\n' "$repo" "$num" "$title" "merge attempt failed - needs Alex" >> "$ROWS"
        fi
      else
        log "QUEUED  $repo#$num  $title  ($verdict)"; queued=$((queued+1))
        printf 'queued\t%s\t%s\t%s\t%s\n' "$repo" "$num" "$title" "$verdict" >> "$ROWS"
        # Leave one signed, self-explanatory comment per reason (skip in dry runs;
        # if the reason changes between passes, a new comment explains the change).
        if [ "$DRY" != "1" ]; then
          marker="Queued for Alex: $verdict"
          existing=$(gh pr view "$num" -R "$repo" --json comments --jq '[.comments[].body] | join("\n")' 2>>"$LOG")
          if ! printf '%s' "$existing" | grep -qF "$marker"; then
            gh pr comment "$num" -R "$repo" --body "$marker. Not auto-mergeable under the grooming policy (patch/minor bumps with green checks only). — Harah" >/dev/null 2>>"$LOG" \
              && log "commented $repo#$num" || log "comment FAILED $repo#$num"
          fi
        fi
      fi
    done < <(printf '%s' "$prs" | python3 -c '
import json, re, sys
for pr in json.load(sys.stdin):
    title = pr.get("title") or ""
    m = re.search(r"[Bb]ump .* from (\S+) to (\S+)", title)
    if not m:
        verdict = "no version parse - needs Alex"
    elif "-" in m.group(1) or "-" in m.group(2):
        verdict = "prerelease involved - needs Alex"
    elif m.group(1).split(".")[0] != m.group(2).split(".")[0]:
        verdict = "MAJOR bump - needs Alex"
    elif pr.get("mergeable") == "CONFLICTING":
        verdict = "merge conflict - needs Alex"
    else:
        checks = pr.get("statusCheckRollup") or []
        bad = [c for c in checks if (c.get("conclusion") or c.get("state") or "").upper()
               in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED")]
        pending = [c for c in checks if (c.get("conclusion") or c.get("state") or "").upper()
                   in ("", "PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED")]
        if bad: verdict = "failing checks - needs Alex"
        elif pending: verdict = "checks still running - retry next pass"
        else: verdict = "MERGE"
    n = pr["number"]
    print(f"{n}\t{title}\t{verdict}")
')
  done
done
log "pass done: $merged merged, $queued queued for Alex, $checked repo(s) had dependabot PRs"

# Machine-readable state for the Harah dashboard (/api/grooming).
mkdir -p "$STATE_DIR"
ROWS="$ROWS" STATE="$STATE" DRY="$DRY" MERGED="$merged" QUEUED="$queued" CHECKED="$checked" python3 - <<'PYEOF'
import json, os, time
rows = []
with open(os.environ["ROWS"]) as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 5:
            kind, repo, num, title, reason = parts
            rows.append({"kind": kind, "repo": repo, "pr": int(num), "title": title, "reason": reason})
# Preserve keys this script does not own. The resolver records its merges under
# "resolver_actions" (POLICY: "every fix lands in the UI"), and this writer used to
# rebuild the file from scratch and os.replace() it -- silently destroying that record
# on the next grooming pass. Carry forward anything we did not produce ourselves.
OWNED = {"last_run", "dry_run", "merged", "queued", "totals"}
loaded = {}
try:
    with open(os.environ["STATE"]) as f:
        maybe = json.load(f)
    if isinstance(maybe, dict):
        loaded = maybe
except (OSError, ValueError):
    pass

prior = {k: v for k, v in loaded.items() if k not in OWNED}

totals = {"merged": int(os.environ["MERGED"]), "queued": int(os.environ["QUEUED"]),
          "repos_with_prs": int(os.environ["CHECKED"])}
# the resolver's cumulative alert tally is its own; grooming must not reset it
prior_totals = loaded.get("totals")
if isinstance(prior_totals, dict) and "alerts_closed_by_resolver" in prior_totals:
    totals["alerts_closed_by_resolver"] = prior_totals["alerts_closed_by_resolver"]

state = {
    "last_run": time.time(),
    "dry_run": os.environ["DRY"] == "1",
    "merged": [r for r in rows if r["kind"] == "merged"],
    "queued": [r for r in rows if r["kind"] == "queued"],
    "totals": totals,
}
state.update(prior)
tmp = os.environ["STATE"] + ".tmp"
with open(tmp, "w") as f:
    json.dump(state, f, indent=2)
os.replace(tmp, os.environ["STATE"])
PYEOF
