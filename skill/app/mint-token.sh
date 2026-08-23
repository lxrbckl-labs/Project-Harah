#!/usr/bin/env bash
# Mint a GitHub App installation token for harah-bot.
#
# Usage: mint-token.sh <owner>     (lxRbckl | lxrbckl-labs)
# Prints a 1-hour installation token; caches it for 50 min so routines can
# call this freely. Requires ~/.harah/app/app-id and ~/.harah/app/private-key.pem
# (chmod 600 — placed by Alex after registering the app; see README.md here).
# Exit 1 with a clear message when credentials are absent — callers fall back
# to the legacy identity (gh's own auth + the — Harah signature).
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
OWNER="${1:?usage: mint-token.sh <owner>}"
APP_DIR="$HOME/.harah/app"
CACHE="$APP_DIR/token-cache-$OWNER"

[ -s "$APP_DIR/app-id" ] && [ -s "$APP_DIR/private-key.pem" ] || {
  echo "no app credentials in $APP_DIR (app-id + private-key.pem) — see skill/app/README.md" >&2; exit 1; }

# Fresh cached token?
if [ -s "$CACHE" ]; then
  age=$(( $(date +%s) - $(stat -f %m "$CACHE") ))
  [ "$age" -lt 3000 ] && { cat "$CACHE"; exit 0; }
fi

APP_ID="$(tr -d '[:space:]' < "$APP_DIR/app-id")"
b64() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
now=$(date +%s)
header=$(printf '{"alg":"RS256","typ":"JWT"}' | b64)
payload=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' "$((now-60))" "$((now+540))" "$APP_ID" | b64)
sig=$(printf '%s.%s' "$header" "$payload" | openssl dgst -sha256 -sign "$APP_DIR/private-key.pem" -binary | b64)
JWT="$header.$payload.$sig"

INST_ID=$(curl -fsS -H "Authorization: Bearer $JWT" -H "Accept: application/vnd.github+json" \
  https://api.github.com/app/installations | python3 -c "
import json,sys
o=sys.argv[1].lower()
for i in json.load(sys.stdin):
    if i['account']['login'].lower()==o: print(i['id']); break
" "$OWNER")
[ -n "$INST_ID" ] || { echo "app not installed on $OWNER — install it (README)" >&2; exit 1; }

TOKEN=$(curl -fsS -X POST -H "Authorization: Bearer $JWT" -H "Accept: application/vnd.github+json" \
  "https://api.github.com/app/installations/$INST_ID/access_tokens" | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])")
umask 077; printf '%s' "$TOKEN" > "$CACHE"
printf '%s' "$TOKEN"
