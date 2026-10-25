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
  to find by address (`gateway.py static <mac> <ip>`). The BGW320 only
  offers addresses **inside its DHCP pool** (`.64`–`.253` here) as fixed;
  nothing outside it can be assigned. Convention: servers and project boxes
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
(`192.168.68.200`) is from the previous network. Until it is up and
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
