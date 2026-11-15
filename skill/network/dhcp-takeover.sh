#!/usr/bin/env bash
# DHCP was moved from the BGW320 to the mini on 2026-11-12 and moved BACK on
# 2026-11-14, at Alex's word (the Pi-hole it served was removed). Run on the MINI.
# This script never runs sudo and never touches the gateway: it only reads.
# Do not use it to move DHCP to the mini again; that needs a new decision from Alex.
#
#   dhcp-takeover.sh status           who serves DHCP and DNS right now (read-only)
#   dhcp-takeover.sh steps            what the reversal was, and what is still pending
#   dhcp-takeover.sh preflight        same text as steps, exits 1 (there is no switch to prepare)
#   dhcp-takeover.sh install-config   copy the transition dnsmasq.conf (this dir) to /opt/homebrew/etc
#
# State since 2026-11-14: the gateway serves DHCP (healthy); the mini's dnsmasq is
# DNS-only and temporary until step 2.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/dnsmasq.conf"
DST="/opt/homebrew/etc/dnsmasq.conf"
DM="/opt/homebrew/sbin/dnsmasq"
ok()   { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
bad()  { echo "✗ $*"; }

install_config() {
  [ -f "$SRC" ] || { bad "no $SRC"; return 1; }
  "$DM" --test -C "$SRC" >/dev/null 2>&1 || { bad "dnsmasq rejects $SRC"; "$DM" --test -C "$SRC"; return 1; }
  if [ -f "$DST" ] && ! cmp -s "$SRC" "$DST"; then
    cp "$DST" "$DST.bak-$(date +%Y%m%d-%H%M%S)"; ok "kept a backup of the previous $DST"
  fi
  cp "$SRC" "$DST" && ok "installed $DST (owned by $(stat -f%Su "$DST"); brew's plist points here)"
}

reversed() {
cat <<TXT
The DHCP takeover was reversed on 2026-11-14 at Alex's word ("I want you to disintegrate and
remove pihole the application entirely. It's more of a burden than useful."). The apartment network
is back on the AT&T gateway for DHCP and DNS. Nothing here moves DHCP to the mini.

Step 1, ran on <DATE-STEP1> (Alex, on the mini: bash ~/pihole-removal/step1.sh, one sudo):
  - the gateway serves DHCP again (gateway.py dhcp on); every new lease names the gateway as DNS
  - the mini's dnsmasq restarted with the DNS-only transition config (dnsmasq.conf here, no DHCP)
  - the pihole container and image removed, ~/docker-bare-run/pihole moved to the Trash,
    the weekly audit routine (com.alex.harah-pihole) removed

Step 2, pending, on or after 2026-11-16 (the last old lease expires 2026-11-15 23:01):
  Alex runs bash ~/pihole-removal/step2.sh, which is: sudo brew services stop dnsmasq, with checks.
  After that nothing on the network depends on the mini.

Fixed addresses live on the gateway again: python3 $HERE/gateway.py static <mac> <ip>
(mini .200, MacBook-Pro .201, P1S-379 .210, P1S-130 .211). Details: network/README.md.
TXT
}

preflight() { reversed; echo; bad "preflight refused: there is no DHCP switch to prepare. See network/README.md."; return 1; }
steps() { reversed; }

status() {
  echo "── mini"
  if netstat -an -p udp 2>/dev/null | /usr/bin/grep -qE '\.67 ' && pgrep -x dnsmasq >/dev/null; then
    bad "dnsmasq is serving DHCP on the mini (pid $(pgrep -x dnsmasq | head -1)); unexpected since 2026-11-14, the gateway is the DHCP server"
  else
    ok "the mini is not serving DHCP"
  fi
  if pgrep -x dnsmasq >/dev/null; then
    warn "dnsmasq is still running (DNS-only transition; stops at step 2, on or after 2026-11-16)"
  else
    ok "dnsmasq is not running (step 2 done, or step 1 not yet run)"
  fi
  dig +short +time=3 example.com @192.168.1.200 >/dev/null 2>&1 && ok "192.168.1.200:53 answers (transition resolver)" || warn "no DNS answer from 192.168.1.200:53 (expected once step 2 is done)"
  echo "── gateway"
  gw="$(python3 "$HERE/gateway.py" dhcp 2>/dev/null | /usr/bin/grep -E '^dhcp ' | sed 's/^/   /')"
  [ -n "$gw" ] && echo "$gw" || warn "could not read the gateway's DHCP state"
  echo "$gw" | /usr/bin/grep -qiE 'dhcp +(on|enabled|true|1)' && ok "gateway DHCP is on (the healthy state)" || warn "gateway DHCP does not read as on; check gateway.py dhcp"
}

case "${1:-}" in
  install-config) install_config ;;
  preflight) preflight ;;
  steps) steps ;;
  status) status ;;
  *) sed -n 2,15p "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
