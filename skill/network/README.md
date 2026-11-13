# Network — Harah's first physical-space duty (2026-10-25)

Alex: *"Harah is also going to maintain my physical space, starting with my
local internet... responsible for the internet management so it can provide
static IPs and anything else I need for projects... watch my network and
know how to interact with it with me, keeping a dialog in Obsidian of what
devices are and their configurations."*

## What Harah owns here

- **Knowing the network.** The gateway (make, firmware, WAN, LAN, DHCP pool,
  radios) and every device on it, kept current in the vault:
  `Homelab/Network/Apartment.md` (facts, decisions, change log) and
  `Homelab/Network/Devices.md` (the roster; generated table, hand-kept
  Owner/Purpose columns).
- **Noticing change.** New devices, devices gone, addresses moved
  (`gateway.py diff`). A new MAC on the network is news; say so.
- **Providing addresses.** Fixed allocations for anything a project needs
  to find by address (`gateway.py static <mac> <ip>`; `gateway.py static
  --list` shows which hosts are fixed). The BGW320 only
  offers addresses **inside its DHCP pool** (`.64`–`.253` here) as fixed;
  nothing outside it can be assigned. Note `gateway.py devices` reports
  the lease kind from `devices.ha`, where a fixed allocation still reads
  `dhcp`; only `ipalloc.ha` (behind the access code) tells fixed from
  dynamic. Convention: servers and project boxes
  take `.200`–`.253` (the mini keeps `.200`); phones, laptops and the rest
  stay dynamic.
- **Port forwards and the rest** (NAT/Gaming pinholes for Caddy, DHCP range,
  Wi-Fi) are configuration changes Alex approves per change; Harah performs
  and records them. Nothing here reboots, factory-resets, or changes Wi-Fi
  security on its own.

Every change to the gateway, by whoever, gets a dated line in the vault
note's change log. That log is the dialog Alex asked for.

## The tool

`gateway.py` (this directory). Read side needs nothing; write side needs the
gateway's **Device Access Code**:

> **The access code** (printed on the gateway's label, the line above the QR
> code) lives, one line, in `~/.harah/gateway-access-code` with `chmod 600`
> on the machine that runs `gateway.py`. In place on the MacBook since
> 2026-10-25; the mini needs its own copy when it comes up. Harah reads it
> from there and never prints, logs, or copies it. Login and the allocation
> form were verified against the real gateway the same day; `static` posts
> for real, `--dry-run` stops before Save.

## Runner

The pass belongs on the **Mac mini** like every other Harah routine. The mini
is at the apartment but powered off (2026-10-25), and its recorded address
(`192.168.68.200`) was from the previous network; it is `192.168.1.200` since 2026-11-07. Until it was up and
re-addressed here, the network pass is **hand-run from the MacBook**:

```sh
python3 skill/network/gateway.py diff     # anything new since last time?
python3 skill/network/gateway.py vault    # refresh the roster in the vault
```

When the mini is up: a `network/enable.sh` on the watchdog pattern
(`diff` every 10 min, `vault` once a day), added to `bootstrap.sh` and
`doctor.sh` like the others. Not written until there is a machine to run it
on; doctrine rule 1 (name the runner or say it's hand-run) applies.

## Gateway facts worth not re-deriving

HUMAX BGW320-500, AT&T Fiber. Status pages open on the LAN: `devices.ha`,
`lanstatistics.ha`, `broadbandstatistics.ha`, `sysinfo.ha`, `firewall.ha`.
Behind the access code: `ipalloc.ha` (fixed allocations), `dhcpserver.ha`,
`wconfig.ha`, `pinholes.ha`. A cold `login.ha` renders "Cookies must be
enabled"; any prior request fixes it. Login posts `nonce`, blank `password`,
`hashpassword = md5(code + nonce)`, `Continue`, exactly as the page's own
`hashpwd()` does. TLS is self-signed.

## What devices are doing, not just who is here (parked 2026-10-25; step 1 done 2026-11-12)

The gateway reports presence only: who joined, who left, who moved. It keeps
no per-device traffic or DNS log and has no API for one. To see *what* a
device does on the internet, add a DNS layer on the mini once it is up:

1. Run **AdGuard Home** (or Pi-hole) as one more Docker stack on the mini,
   DNS on `:53`, admin UI behind Caddy on the LAN only (never public).
2. Point the gateway's DHCP DNS at the mini (`dhcpserver.ha`, access code),
   so every device resolves through it. Keep AT&T's resolvers as the
   upstream.
3. Harah reads AdGuard's query log per client (its API is simple) and the
   roster gains a "what it talks to" view; blocking lists are a bonus.

Status 2026-11-12: step 1 is done as **Pi-hole** (`../pihole/README.md`), with
four blocklists and the weekly leak audit. Step 2 as written is impossible: the
BGW320's `dhcpserver.ha` form has **no DNS field** (verified against the live
page: only the enable switch, the pool range and the lease time), so the
gateway cannot hand clients a different resolver. The ways to route the whole
LAN through the mini are in `../pihole/README.md` ("Routing"), each Alex's call.
Until one is chosen, devices are pointed at `192.168.1.200` one by one. Step 3
(per-device view) needs the dnsmasq DNS front door described below, because
Docker Desktop NATs every LAN client to one address.

## DHCP on the mini (Alex's decision 2026-11-12; switched 2026-11-12 23:59)

The Pi-hole only filters devices that ask it, and the BGW320 cannot name it as
the DNS server, so DHCP itself moves to the mini: `dnsmasq` (Homebrew) runs as a **root** LaunchDaemon (`sudo brew services start
dnsmasq`; DHCP needs the BPF socket, measured: a user process fails on it) with
`dnsmasq.conf` from this directory, same pool `.64–.253`, same 1-day lease,
router `.254`, DNS `.200`, and the fixed allocations copied from `ipalloc.ha`.
`gateway.py dhcp off` ran 2026-11-12 23:59 on Alex's word; the first lease (MacBook-Pro, `.201`) followed within a minute. The mini itself sits on a manual IP first
(`networksetup -setmanual`) so it never waits on a DHCP server, and keeps the
gateway as its own resolver.

The same dnsmasq is also the LAN's **DNS front door** (added 2026-11-12 for
per-client stats): it listens on `192.168.1.200:53` and `127.0.0.1:53`,
forwards every query uncached to the Pi-hole container on `127.0.0.1:5335`
(`5353` is taken by macOS mDNSResponder, learned the hard way) and adds the
real client address as EDNS0 Client Subnet, which Pi-hole FTL logs as the
client. LAN names and PTRs (`attlocal.net`, `1.168.192.in-addr.arpa`) are
answered from the leases and never forwarded, which is also what keeps the
Pi-hole's conditional forwarding back to `.200` from looping. Changing
`server=` or ports needs `sudo brew services restart dnsmasq`.

`dhcp-takeover.sh` is the runbook: `install-config` (repo → `/opt/homebrew/etc`),
`preflight`, `steps` (the exact commands, who runs which), `status` (who serves
DHCP, current leases). It never runs `sudo` and never posts to the gateway;
the two sudo lines are Alex's, the gateway switch is Harah's on his word, and
both land in the vault's change log. Rollback is the reverse: `gateway.py dhcp
on`, `sudo brew services stop dnsmasq`. Known costs: the gateway's guest Wi-Fi
loses DHCP; the gateway no longer learns hostnames, so `devices.ha` names go
blank over time (`dnsmasq.leases` on the mini has them instead); dual-stack
devices still get the gateway's IPv6 resolver by RA/DHCPv6 until `gateway.py
ipv6lan dhcpv6 off`, a separate decision.

`gateway.py dhcp` / `gateway.py ipv6lan` read those pages; `dhcp on|off` and
`ipv6lan ipv6|dhcpv6 on|off` post the whole form back with one select flipped
and `Save`, `--dry-run` shows the payload (verified read side and dry run
2026-11-12; the first real `dhcp off` is the switch itself).

## On the mini

Same script, Python stdlib only, same LAN, nothing to install. What the mini
needs that the MacBook already has: its own `~/.harah/gateway-access-code`
(Alex writes it once) and a routine. `network/enable.sh` on the watchdog
pattern (`diff` every 10 min, `vault` once a day, a text on `NEW`), wired into
`bootstrap.sh` and `doctor.sh`, gets written the day the mini is up, then
the MacBook stops being the runner.
