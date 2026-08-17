#!/usr/bin/env bash
# Ship what's on main to the running container, and prove it landed.
#
# Alex, 2026-08-17: "nothing stays parked... you use the publish command and
# update docker images as you NEED."
#
# The pipeline builds only when the head commit message starts with `publish`,
# so shipping = an empty `publish:` commit on main. Then the image builds,
# watchtower rolls it (300s poll), and we verify a real request.
#
# Usage: publish.sh <owner/repo> ["reason"] [--dry-run]
#
# Safety, in order:
#   PRE   refuse if main's CI can't even resolve its workflow, if the repo has
#         no deploy target, or if a publish is already in flight. Record the
#         currently-running image ID first — that is the rollback anchor.
#   BUILD watch the run. A failed build means NO new image, so nothing rolled
#         and the live service is untouched. That is a safe failure; stop.
#   ROLL  wait for watchtower to swap the container (image ID changes).
#   PROVE verify.py + a real HTTPS request.
#   BACK  if it does not come back: immediately restore the previous image
#         locally, then escalate. See the watchtower caveat below.
#
# ROLLBACK CAVEAT, stated plainly: watchtower re-pulls `:main` every 300s, so a
# local retag only holds until the next poll. It buys minutes, not a fix. The
# durable rollback is reverting the bad commit on main and publishing again —
# which needs judgment, so it escalates to a session rather than firing blind.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

REPO="${1:?usage: publish.sh <owner/repo> [reason] [--dry-run]}"
REASON="${2:-dependency security updates}"
DRY=0; for a in "$@"; do [ "$a" = "--dry-run" ] && DRY=1; done

LOG="$HOME/Library/Logs/harah-publish.log"
LOCK="${TMPDIR:-/tmp}/harah-publish-$(echo "$REPO" | tr '/' '-').lock"
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv "$LOG" "$LOG.1"

say(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

if ! mkdir "$LOCK" 2>/dev/null; then say "skip: a publish for $REPO is already in flight"; exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

CONTAINER="$(python3 -c "
import json,sys,pathlib
cfg=json.loads(pathlib.Path('$ROOT/deploy-check/targets.json').read_text())
t=cfg.get('$REPO') or {}
print((t.get('containers') or [''])[0])
")"
[ -n "$CONTAINER" ] || { say "ERROR: $REPO has no deploy target in targets.json — nothing to publish to"; exit 2; }

say "=== publish $REPO ($REASON)$([ "$DRY" = 1 ] && echo ' [DRY RUN]') ==="

# PRE — can this repo even build? Check the BUILD workflow's `uses:` reference
# resolves, deterministically. Reading "the latest run on main" is wrong: that
# is often Dependabot's own run, not the publish pipeline. And a stale org in
# `uses:` is invisible to the REST API (it follows rename redirects) while
# Actions refuses it — so every run dies before starting a job.
WF="$(gh api "/repos/$REPO/contents/.github/workflows/dockerhub-build-push.yml" --jq '.content' 2>/dev/null | base64 -d 2>/dev/null | grep -m1 'uses:' | sed 's/.*uses:[[:space:]]*//')"
if [ -n "$WF" ]; then
  WF_ORG="${WF%%/*}"
  REPO_ORG="${REPO%%/*}"
  if [ "$WF_ORG" != "$REPO_ORG" ] && ! gh api "/orgs/$WF_ORG" --jq '.login' >/dev/null 2>&1; then
    say "REFUSING: build workflow references \`$WF_ORG\`, which does not resolve."
    say "  Actions cannot find it (the REST API follows rename redirects, Actions does not)."
    say "  Every run dies before starting a job, so publishing would build nothing."
    say "  Fix the \`uses:\` org reference first."
    exit 1
  fi
  say "build workflow uses: $WF"
fi

OLD_IMG="$(docker inspect -f '{{.Image}}' "$CONTAINER" 2>/dev/null)"
say "rollback anchor: $CONTAINER currently on ${OLD_IMG:0:20}"

if [ "$DRY" = "1" ]; then say "DRY RUN — would push a publish commit to $REPO main"; exit 0; fi

# BUILD
TMPD="$(mktemp -d)"; trap 'rmdir "$LOCK" 2>/dev/null; rm -rf "$TMPD"' EXIT
gh repo clone "$REPO" "$TMPD/r" -- --depth 1 -q 2>/dev/null || { say "ERROR: clone failed"; exit 1; }
git -C "$TMPD/r" commit -q --allow-empty -m "publish: $REASON

Shipping already-merged and verified changes to the running image.
— Harah" || { say "ERROR: commit failed"; exit 1; }
git -C "$TMPD/r" push -q origin HEAD:main || { say "ERROR: push failed"; exit 1; }
say "publish commit pushed; waiting for the build"

sleep 20
RUN=""; for i in $(seq 1 40); do
  RUN="$(gh run list -R "$REPO" --branch main --limit 1 --json databaseId,status,conclusion --jq '.[0] | "\(.databaseId) \(.status) \(.conclusion // "")"')"
  st="$(echo "$RUN" | awk '{print $2}')"; cc="$(echo "$RUN" | awk '{print $3}')"
  [ "$st" = "completed" ] && break
  sleep 20
done
say "build: $RUN"
if [ "$cc" != "success" ]; then
  say "BUILD FAILED ($cc) — no image produced, live service untouched. Stopping."
  exit 1
fi

# ROLL — watchtower polls every 300s.
say "waiting for watchtower to roll $CONTAINER (up to 10 min)"
NEW_IMG="$OLD_IMG"
for i in $(seq 1 40); do
  sleep 20
  NEW_IMG="$(docker inspect -f '{{.Image}}' "$CONTAINER" 2>/dev/null)"
  [ "$NEW_IMG" != "$OLD_IMG" ] && { say "rolled: ${OLD_IMG:0:20} -> ${NEW_IMG:0:20}"; break; }
done
[ "$NEW_IMG" = "$OLD_IMG" ] && say "WARNING: container never rolled after 10 min — image may be unchanged"

# PROVE
sleep 20
if python3 "$ROOT/deploy-check/verify.py" "$REPO" 2>&1 | tee -a "$LOG" | grep -q "^== PASS"; then
  say "=== PUBLISHED AND VERIFIED: $REPO ==="
  exit 0
fi

# BACK
say "!!! VERIFICATION FAILED after publish — restoring previous image"
if [ -n "$OLD_IMG" ] && [ "$NEW_IMG" != "$OLD_IMG" ]; then
  docker stop "$CONTAINER" >/dev/null 2>&1
  docker run -d --name "${CONTAINER}-rollback" "$OLD_IMG" >/dev/null 2>&1 \
    && say "started ${CONTAINER}-rollback on the previous image" \
    || { docker start "$CONTAINER" >/dev/null 2>&1; say "could not start a rollback container; restarted the original"; }
fi
say "ESCALATING — watchtower will re-pull :main within 300s, so this is minutes of"
say "cover, not a fix. The durable rollback is reverting the bad commit on main."
nohup python3 "$ROOT/incident/respond.py" "$CONTAINER" >> "$LOG" 2>&1 &
exit 1
