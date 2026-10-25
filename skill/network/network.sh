#!/usr/bin/env bash
# harah network routine: every 10 minutes, who joined or left the apartment
# network? Once a day, refresh the roster in the vault. Texts Alex on a NEW
# device (a MAC never seen before), the one event worth a phone buzz.
# READ-ONLY against the gateway. Logs only on events, like the watchdog.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HOME/Library/Logs/harah-network.log"
LOCK="${TMPDIR:-/tmp}/harah-network.lock"
STAMP="$HOME/.harah/network-vault-stamp"
[ -f "$LOG" ] && [ "$(stat -f%z "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ] && mv "$LOG" "$LOG.1"
if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
mkdir -p "$HOME/.harah"

out="$(python3 "$HERE/gateway.py" diff 2>&1)"; code=$?

text_alex() {
  local target_file="$HOME/.harah/heartbeat-target" msg="$1"
  [ -s "$target_file" ] || return 0
  local to; to="$(head -1 "$target_file" | tr -d '[:space:]')"
  local esc; esc="$(printf '%s' "$msg" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
  osascript -e "tell application \"Messages\" to send \"$esc\" to buddy \"$to\" of (service 1 whose service type is iMessage)" >/dev/null 2>&1 || true
}

new="$(printf '%s\n' "$out" | grep '^NEW ' || true)"
if [ -n "$new" ]; then
  n="$(printf '%s\n' "$new" | wc -l | tr -d ' ')"
  text_alex "🟡 Harah network: $n new device(s) on the apartment Wi-Fi: $(printf '%s\n' "$new" | sed -E 's/^NEW +//' | cut -c1-70 | paste -sd ';' -). Roster: Homelab/Network/Devices.md — Harah"
fi

# daily roster refresh in the vault (first pass of each day)
today="$(date +%F)"
if [ "$(cat "$STAMP" 2>/dev/null)" != "$today" ]; then
  VAULT=""
  for v in "$HOME/Obsidian" "$HOME/lxrbckl/Obsidian"; do [ -d "$v/Homelab" ] && VAULT="$v" && break; done
  if [ -n "$VAULT" ]; then
    vout="$(python3 "$HERE/gateway.py" vault --vault "$VAULT/Homelab/Network/Devices.md" 2>&1)" && \
      git -C "$VAULT" add Homelab/Network/Devices.md >/dev/null 2>&1 && \
      git -C "$VAULT" -c user.name=Harah -c user.email=harah@users.noreply.github.com commit -qm "Homelab/Network: daily roster refresh — Harah" >/dev/null 2>&1 && \
      git -C "$VAULT" push -q origin HEAD >/dev/null 2>&1 || true
    out="$out"$'\n'"$vout"
  else
    out="$out"$'\n'"vault: no Obsidian checkout found; roster not refreshed"
  fi
  echo "$today" > "$STAMP"
fi

if [ "$code" -ne 0 ] || printf '%s' "$out" | grep -qE '^(NEW|GONE|IP MOVED|ONLINE|OFFLINE|vault:|baseline)'; then
  { echo "===== $(date '+%FT%T%z') network ====="; printf '%s\n' "$out"; } >> "$LOG"
fi
exit 0
