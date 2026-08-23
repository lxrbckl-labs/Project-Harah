#!/usr/bin/env bash
# Run a gh/git command AS harah-bot[bot]. Usage:
#   as-bot.sh <owner> gh pr comment 5 -R owner/repo -b "…"
#   as-bot.sh <owner> git push https://github.com/owner/repo.git branch
# Falls through (exit 1, clear message) when app credentials are absent —
# callers keep the legacy identity. For git pushes it rewrites the remote URL
# to token auth on the fly; nothing is stored.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OWNER="${1:?usage: as-bot.sh <owner> <cmd…>}"; shift
TOKEN="$("$HERE/mint-token.sh" "$OWNER")"
case "${1:-}" in
  gh)  shift; GH_TOKEN="$TOKEN" gh "$@";;
  git) shift
       args=(); for a in "$@"; do
         case "$a" in https://github.com/*) a="https://x-access-token:${TOKEN}@github.com/${a#https://github.com/}";; esac
         args+=("$a")
       done
       git "${args[@]}";;
  *) echo "as-bot.sh: command must be gh or git" >&2; exit 2;;
esac
