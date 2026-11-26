#!/usr/bin/env bash
# login-limits.sh [caddyfile] — read-only audit: which hosted sites have a login
# and which of those carry a Caddy rate_limit. Changes nothing. Doctrine:
# skill/SERVER.md (guardrail) and skill/WORKFLOWS.md (Audit login rate limits).
set -euo pipefail
CADDYFILE="${1:-$HOME/caddyfile}"
[ -r "$CADDYFILE" ] || { echo "cannot read $CADDYFILE" >&2; exit 2; }

# Known login endpoints per site: the path the login form POSTs to (+ admin
# prefixes). "none" = the site has no login. Add a line when a new app with a
# login is hosted; a site missing here prints as unknown.
known() {
  case "$1" in
    vaultwarden.lxrbckl.com)   echo "/identity/connect/token /admin /admin/*" ;;
    immich.lxrbckl.com)        echo "/api/auth/login" ;;
    ds.lxrbckl.com)            echo "LOGIN endpoint unconfirmed (site redirects / to a login page)" ;;
    notes.hannahporras.app)    echo "LOGIN endpoint unconfirmed (has a sign-in)" ;;
    lucidindex.lxrbckl.com)    echo "LOGIN endpoint unconfirmed (forum accounts)" ;;
    resume.lxrbckl.com)        echo "none (static)" ;;
    sawyer.showalter.business) echo "none (static)" ;;
    relay.hivedeck.app|relay-b.hivedeck.app) echo "none (relay; its own token auth)" ;;
    lxrbckl.com)               echo "none (redirect/static)" ;;
    *)                         echo "unknown" ;;
  esac
}

gap=0
printf '%-28s %-11s %s\n' SITE RATE_LIMIT LOGIN_ENDPOINT
awk '
  /^[A-Za-z0-9*.-]+(, *[A-Za-z0-9*.-]+)* \{[ \t]*$/ { site=$1; depth=0; has=0; insite=1 }
  insite { n=gsub(/\{/,"{"); m=gsub(/\}/,"}"); depth+=n-m
           if ($0 ~ /^[ \t]*rate_limit([ \t]|$)/) has=1
           if (depth<=0) { print site, (has?"yes":"no"); insite=0 } }
' "$CADDYFILE" | while read -r site has; do
  k="$(known "$site")"
  flag=""
  case "$k" in
    none*) ;;
    unknown) flag="  <- unknown app: check it" ;;
    *) [ "$has" = no ] && { flag="  <- GAP: login without rate_limit"; gap=1; } ;;
  esac
  printf '%-28s %-11s %s%s\n' "$site" "$has" "$k" "$flag"
done
echo
echo "Legend: GAP = a site with a login and no rate_limit (take to Alex, apply on his word);"
echo "        unknown = not in this script's table yet. This script changes nothing."
