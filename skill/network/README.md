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

## DHCP and DNS: the gateway's, since 2026-11-14

The BGW320 serves DHCP and is every device's DNS, as it was before 2026-11-12.
Every new lease names the gateway (`192.168.1.254`) as its DNS. The gateway
reports presence only (who joined, who left, who moved); it keeps no
per-device traffic or DNS log and has no API for one. Nothing on the network depends on the mini for addressing or name
resolution once step 2 below is done.

**Fixed addresses** live on the gateway's reservations again, set with
`gateway.py static <mac> <ip>` (MACs are in the vault roster and in
`gateway.py static --list`): the mini `.200`, MacBook-Pro `.201`, P1S-379
`.210`, P1S-130 `.211`. The mini's own Ethernet stays on a manual IP,
`192.168.1.200`, with DNS `192.168.1.254`, so it never waits on a DHCP server.

**Removal in two steps, no outage** (Alex, 2026-11-14):

1. *Step 1, ran on <DATE-STEP1>.* Alex ran `bash ~/pihole-removal/step1.sh` on
   the mini (one sudo). The gateway serves DHCP again (`gateway.py dhcp on`).
   The mini's `dnsmasq` was restarted with the DNS-only transition config in
   `dnsmasq.conf` (this directory; no DHCP): it forwards to the gateway
   `192.168.1.254`, then `1.1.1.1`, so devices still holding an old lease that
   names `192.168.1.200` as their DNS keep resolving. The same config holds two
   local records, `relay.hivedeck.app` and `relay-b.hivedeck.app` to
   `192.168.1.200` (the HiveDeck relays live on the mini). The `pihole`
   container and image were removed, `~/docker-bare-run/pihole` went to the
   Trash, and the weekly audit routine was removed.
2. *Step 2, pending: on or after 2026-11-16* (the last old lease expires
   2026-11-15 23:01). Alex runs `bash ~/pihole-removal/step2.sh`, which is
   `sudo brew services stop dnsmasq` with checks. `dnsmasq.conf` and the daemon
   go away at this step.

Consequence recorded in `../OPEN-ITEMS.md`: once dnsmasq stops, LAN devices
get the public address for `relay.hivedeck.app` from the gateway's DNS, so
reaching the relays from the LAN depends on the gateway's NAT loopback, which
is untested.

`dhcp-takeover.sh` is what is left of the 2026-11-12 runbook. `status` is
read-only and truthful for this state (gateway DHCP on is healthy; dnsmasq
serving DHCP is unexpected). `steps` prints the reversal and the two steps
above; `preflight` prints the same and exits 1. Nothing in it moves DHCP.

`gateway.py dhcp` / `gateway.py ipv6lan` read the gateway's DHCP and IPv6 pages;
`dhcp on|off` and `ipv6lan ipv6|dhcpv6 on|off` post the whole form back with one
select flipped and `Save`; `--dry-run` shows the payload.

## History: DHCP on the mini, 2026-11-12 to 2026-11-14

On 2026-11-12 Alex had DHCP and DNS moved to the mini so a Pi-hole container
could filter the LAN: a root `dnsmasq` LaunchDaemon served DHCP and was the
DNS front door on `192.168.1.200:53`, forwarding every query to a `pihole`
container on `127.0.0.1:5335` (stack `~/docker-bare-run/pihole`), with the
gateway's DHCP off (`gateway.py dhcp off`, 23:59 that night). A weekly leak
audit (`com.alex.harah-pihole`) and a CRUD tool (`pihole/pihole.py`) went with
it. The BGW320's DHCP form has no DNS field, which is why DHCP itself had to
move. On 2026-11-14 Alex: *"I want you to disintegrate and remove
pihole the application entirely. It's more of a burden than useful."* The
network went back to the gateway, as above. The code is in git history.

## On the mini

Same script, Python stdlib only, same LAN, nothing to install. What the mini
needs that the MacBook already has: its own `~/.harah/gateway-access-code`
(Alex writes it once) and a routine. `network/enable.sh` on the watchdog
pattern (`diff` every 10 min, `vault` once a day, a text on `NEW`), wired into
`bootstrap.sh` and `doctor.sh`, gets written the day the mini is up, then
the MacBook stops being the runner.
