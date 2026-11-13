#!/usr/bin/env bash
# DHCP moves from the BGW320 to the mini (Alex, 2026-11-12). Run on the MINI.
# This script never runs sudo and never touches the gateway: it prepares,
# checks and prints. The two root steps are Alex's at the keyboard; the gateway
# switch is `gateway.py dhcp off`, on his word, logged in the vault.
#
#   dhcp-takeover.sh install-config   copy dnsmasq.conf (this dir) to /opt/homebrew/etc, keep a backup
#   dhcp-takeover.sh preflight        everything that must be true before the switch
#   dhcp-takeover.sh steps            the exact commands, in order, for switch day
#   dhcp-takeover.sh status           who is serving DHCP right now, recent leases
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/dnsmasq.conf"
DST="/opt/homebrew/etc/dnsmasq.conf"
DM="/opt/homebrew/sbin/dnsmasq"
LEASES="/opt/homebrew/var/lib/misc/dnsmasq/dnsmasq.leases"
ok()   { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
bad()  { echo "✗ $*"; FAIL=1; }
FAIL=0

install_config() {
  [ -f "$SRC" ] || { bad "no $SRC"; return 1; }
  "$DM" --test -C "$SRC" >/dev/null 2>&1 || { bad "dnsmasq rejects $SRC"; "$DM" --test -C "$SRC"; return 1; }
  if [ -f "$DST" ] && ! cmp -s "$SRC" "$DST"; then
    cp "$DST" "$DST.bak-$(date +%Y%m%d-%H%M%S)"; ok "kept a backup of the previous $DST"
  fi
  cp "$SRC" "$DST" && ok "installed $DST (owned by $(stat -f%Su "$DST"); brew's plist points here)"
}

preflight() {
  [ -x "$DM" ] && ok "dnsmasq $("$DM" --version | head -1 | awk '{print $3}') installed" || bad "dnsmasq missing: brew install dnsmasq"
  if [ -f "$DST" ] && cmp -s "$SRC" "$DST"; then ok "$DST matches the repo copy"; else bad "$DST differs from the repo copy: run install-config"; fi
  "$DM" --test -C "$DST" >/dev/null 2>&1 && ok "config syntax ok" || bad "config syntax error"
  local ip; ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
  [ "$ip" = "192.168.1.200" ] && ok "mini is at 192.168.1.200 on en0" || bad "mini is at ${ip:-nothing} on en0, expected 192.168.1.200"
  if networksetup -getinfo Ethernet 2>/dev/null | /usr/bin/grep -q '^Manually Using DHCP\|^Manual Configuration'; then
    ok "mini's Ethernet is on a manual IP (does not depend on any DHCP server)"
  else
    warn "mini's Ethernet is still a DHCP client: step 1 below (sudo networksetup) is pending"
  fi
  # netstat sees root-owned sockets without sudo; lsof does not.
  if netstat -an -p udp 2>/dev/null | /usr/bin/grep -qE '\.67 '; then ok "something already listens on UDP 67 on the mini: $(pgrep -x dnsmasq >/dev/null && echo dnsmasq || echo 'not dnsmasq')"; else warn "nothing listens on UDP 67 yet (expected before step 2)"; fi
  if /usr/bin/grep -q 'option:dns-server,192.168.1.200' "$DST"; then ok "clients will get DNS 192.168.1.200 (the Pi-hole)"; else bad "config does not hand out the Pi-hole as DNS"; fi
  dig +short +time=3 example.com @127.0.0.1 -p 5335 >/dev/null 2>&1 && ok "the Pi-hole answers on 127.0.0.1:5335 (behind dnsmasq)" || bad "the Pi-hole does not answer on 127.0.0.1:5335; do not switch"
  if dig +short +time=3 example.com @192.168.1.200 >/dev/null 2>&1; then
    ok "dnsmasq answers DNS on 192.168.1.200:53 (forwarding to the Pi-hole)"
  elif netstat -an -p udp 2>/dev/null | /usr/bin/grep -qE '192\.168\.1\.200\.53 '; then
    bad "something holds 192.168.1.200:53 but does not answer: dnsmasq is probably forwarding to a dead port; check 'server=' in $DST and restart the service"
  else
    warn "nothing answers DNS on 192.168.1.200:53 yet (expected before the service runs with the new config)"
  fi
  echo "── gateway (read-only)"
  python3 "$HERE/gateway.py" dhcp 2>/dev/null | /usr/bin/grep -E '^(dhcp|pool|lease)' | sed 's/^/   /'
  python3 "$HERE/gateway.py" ipv6lan 2>/dev/null | /usr/bin/grep -E '^(ipv6|dhcpv6) ' | sed 's/^/   /'
  [ $FAIL = 0 ] && ok "preflight clean" || warn "preflight has ✗ items; fix them before switch day"
  return $FAIL
}

steps() {
cat <<TXT
Switch day, in this order. Alex runs the sudo lines on the mini; Harah runs gateway.py on Alex's word.

1. Alex (mini, sudo): pin the mini's own address so it never needs a DHCP server
     sudo networksetup -setmanual Ethernet 192.168.1.200 255.255.255.0 192.168.1.254
     sudo networksetup -setdnsservers Ethernet 192.168.1.254
   (the mini keeps resolving through the gateway, not through its own container)

2. Alex (mini, sudo): start dnsmasq as a root LaunchDaemon (DHCP needs the BPF socket)
     sudo brew services start dnsmasq
     sudo lsof -nP -iUDP:67        # dnsmasq should hold *:67
     tail -5 /opt/homebrew/var/log/dnsmasq-dhcp.log

3. Harah, on Alex's word (logged in the vault): turn the gateway's DHCP off
     python3 $HERE/gateway.py dhcp off --dry-run
     python3 $HERE/gateway.py dhcp off

4. Prove it from any device: renew its lease (Wi-Fi off/on) and check its DNS is 192.168.1.200
     macOS: ipconfig getpacket en0 | grep domain_name_server      (or en1 on Wi-Fi)
     then open a site with ads and watch: python3 $HERE/../pihole/pihole.py top --blocked

5. Harah: bash $0 status; add the change-log line to Homelab/Network/Apartment.md.

IPv6 note: the gateway still advertises itself as an IPv6 resolver (RA/DHCPv6), and dual-stack
devices will send some queries there, around the Pi-hole. Closing that is a second decision:
     python3 $HERE/gateway.py ipv6lan dhcpv6 off --dry-run     (or ipv6 off for the whole LAN)

Rollback (any time, in reverse): python3 $HERE/gateway.py dhcp on; sudo brew services stop dnsmasq.
Leases are 24 h; devices move over as they renew (half-life 12 h) or when they rejoin Wi-Fi.
Guest Wi-Fi on the BGW320 loses DHCP once the gateway stops serving it.
TXT
}

status() {
  echo "── mini"
  if netstat -an -p udp 2>/dev/null | /usr/bin/grep -qE '\.67 ' && pgrep -x dnsmasq >/dev/null; then ok "dnsmasq is serving DHCP on the mini (pid $(pgrep -x dnsmasq | head -1))"; else warn "dnsmasq is not listening on UDP 67"; fi
  dig +short +time=3 example.com @192.168.1.200 >/dev/null 2>&1 && ok "dnsmasq answers DNS on 192.168.1.200:53" || warn "no DNS answer from 192.168.1.200:53"
  dig +short +time=3 example.com @127.0.0.1 -p 5335 >/dev/null 2>&1 && ok "the Pi-hole answers on 127.0.0.1:5335" || warn "the Pi-hole does not answer on 127.0.0.1:5335"
  sudo -n true 2>/dev/null && true
  if [ -r "$LEASES" ]; then
    echo "   leases ($(wc -l < "$LEASES" | tr -d ' ')):"; awk '{ cmd="date -r "$1" +%H:%M"; cmd | getline t; close(cmd); printf "   %-16s %-18s %s (until %s)\n", $3, $2, $4, t }' "$LEASES" | head -n 40
  else
    echo "   no lease file yet at $LEASES (root-owned until the service has run)"
  fi
  echo "── gateway"
  python3 "$HERE/gateway.py" dhcp 2>/dev/null | /usr/bin/grep -E '^dhcp ' | sed 's/^/   /'
}

case "${1:-}" in
  install-config) install_config ;;
  preflight) preflight ;;
  steps) steps ;;
  status) status ;;
  *) sed -n 2,12p "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
