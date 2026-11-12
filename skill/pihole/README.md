# Pi-hole — the LAN DNS ad blocker (2026-11-12)

Alex: *"setup a pi hole docker container and route all my internet traffic
through my Mac mini so we can aim to block ads. Add a few lists and then maybe
a skill to occasionally observe history and look for ads that made it through
we can add to the list."*

## Where it is

| | |
|---|---|
| Stack | `~/docker-bare-run/pihole/docker-compose.yml` on the mini, container `pihole`, image `pihole/pihole:latest` (v6) |
| DNS | `192.168.1.200:53` TCP+UDP (every interface; the gateway forwards only 80/443, so it is LAN-only) |
| Admin UI / API | `http://192.168.1.200:8753` (LAN only; never put it behind Caddy on a public name) |
| Password | `PIHOLE_PASSWORD` in `~/docker-bare-run/pihole/.env`, mode 600. Alex reads it there; Harah never prints it |
| Data | `~/docker-bare-run/pihole/etc-pihole/` (gravity DB, query DB, config). Small; not on the NVMe volumes |
| Upstreams | the AT&T gateway `192.168.1.254` first (keeps `attlocal.net` names and reverse lookups working), then `1.1.1.1` |
| Blocklists | StevenBlack unified (Pi-hole's default), HaGeZi Pro, OISD big, HaGeZi TIF medium (malware/phishing). Chosen for low breakage; add aggressive lists only on Alex's word |

## The tool: `pihole.py`

Stdlib Python over the Pi-hole v6 REST API (`http://127.0.0.1:8753/api`),
same shape as `../network/gateway.py`. `pihole.py --help` is the reference;
the everyday verbs:

```sh
python3 skill/pihole/pihole.py status                 # blocking on? gravity size, 24h counts
python3 skill/pihole/pihole.py lists                  # the blocklists
python3 skill/pihole/pihole.py lists add <url> "why"  # then: gravity
python3 skill/pihole/pihole.py gravity                # rebuild after list changes
python3 skill/pihole/pihole.py deny ads.example.com "seen in audit 2026-11-12"
python3 skill/pihole/pihole.py allow cdn.example.com "false positive broke X"
python3 skill/pihole/pihole.py rm deny ads.example.com
python3 skill/pihole/pihole.py top [--blocked] 25     # last 24h
python3 skill/pihole/pihole.py leaks --since 168      # permitted hosts shaped like ads
python3 skill/pihole/pihole.py blocking off 10        # pause blocking 10 min (debug a broken site)
```

Every write takes `--dry-run`. Each run logs its API session out again (Pi-hole
caps sessions, like the gateway). Exact allow/deny only; regex entries are a
UI job and rare.

## The routine: weekly leak audit (`audit.sh`, `com.alex.harah-pihole`)

Sundays 20:00, GUI-domain LaunchAgent, installed by `enable.sh` (idempotent,
self-locating). Log `~/Library/Logs/harah-pihole.log` (banner per run);
state `~/.harah/pihole-state.json` (what `doctor.sh` reads, max age 8 days);
report `~/.harah/pihole-audit-report.md`.

1. `pihole.py leaks --since 168 --json` shortlists what the Pi-hole
   **permitted** over the week that is shaped like an ad, tracker or telemetry
   host (label heuristics in `pihole.py`; recall over precision).
2. A clean week ends there: report says so, no text (silence here is fine;
   the heartbeat is the alarm, and `doctor.sh` sees the state file).
3. Otherwise a headless `claude -p` run with `audit-prompt.md` judges each
   host DENY / KEEP / UNSURE, writes the report, and prints
   `HARAH_PIHOLE: deny=N keep=N unsure=N applied=N`.
4. **Propose mode (default):** nothing changes; Alex gets one 🟡 text with
   the count and the report path, and denies with `pihole.py deny` or by
   saying so in a session. **Apply mode:** when the file
   `~/.harah/pihole-audit-apply` exists, the agent runs `pihole.py deny` for
   clear-cut DENY verdicts and the report says which. Alex creates or
   removes that file; Harah never does.

Verify the way launchd runs it: `launchctl kickstart -k gui/$(id -u)/com.alex.harah-pihole`,
then `tail -20 ~/Library/Logs/harah-pihole.log`. `bash audit.sh --dry-run`
gathers the shortlist and prints the prompt without calling the agent.

## Routing: how traffic actually reaches the Pi-hole

A DNS blocker only filters the devices that ask it. Measured 2026-11-12:

- **The BGW320 cannot point clients at it.** Its DHCP form (`dhcpserver.ha`,
  behind the access code) has only the DHCP on/off switch, the pool range and
  the lease time. No DNS field exists, so "set the router's DNS" is not an
  option on AT&T's gateway.
- **An unprivileged DHCP server on the mini cannot run.** `dnsmasq` (Homebrew
  2.93) as a user process fails on the ICMP raw socket and, with `--no-ping`,
  on the DHCP BPF socket (`/dev/bpf*` is root-only). Pi-hole's own DHCP is out
  too: Docker Desktop on macOS has no real host networking or broadcast.

So the choices, each Alex's call, cheapest first:

1. **Per-device DNS = `192.168.1.200`** (Wi-Fi settings on the phone, the
   Macs, the TV). Works today, reversible per device, no new single point of
   failure. Not "all traffic", but all of Alex's.
2. **DHCP moves to the mini as root** — **Alex's choice, 2026-11-12.** dnsmasq
   (DHCP only, `port=0`) as a root LaunchDaemon hands out the gateway's own
   pool with DNS = `192.168.1.200`, then the gateway's DHCP goes off. The
   config is `../network/dnsmasq.conf`, the switch is `gateway.py dhcp off`,
   and `../network/dhcp-takeover.sh steps` is the runbook (preflight, the two
   sudo lines Alex runs, the switch, the proof, the rollback). Every device
   then depends on the mini for an address; the gateway's guest Wi-Fi loses
   DHCP; dual-stack devices still see the gateway's IPv6 resolver until
   `gateway.py ipv6lan dhcpv6 off` (second decision).
3. **Alex's own router in IP Passthrough** (the Deco from the previous
   network) with its DHCP DNS set to `.200`. Cleanest for "all traffic",
   biggest change.

Whichever is chosen, keep the **mini itself** on the gateway's resolver
(`192.168.1.254`, as DHCP gives it today): if the mini resolved through its
own container, a Docker restart would take its own routines' DNS down with it.

## Caveats

- **Clients are indistinguishable.** Docker Desktop NATs every LAN query to
  one source address, so the Pi-hole's client view, and step 3 of the network
  plan ("what each device talks to"), do not work here. Docker Desktop ≥ 4.34
  offers `network_mode: host` that claims to keep the source IP; untested,
  and it would need the `53:53` port lines removed.
- **If the mini is down, so is DNS** for every device pointed at it. Devices
  with a secondary resolver set (the gateway, `192.168.1.254`) fall back on
  their own, but then bypass the filter; that is the right trade for a phone.
- **A blocked page looks like a dead site.** Before blaming a service, check
  `pihole.py top --blocked`, and `pihole.py allow` the false positive, or
  `pihole.py blocking off 10` to prove it.
- The compose has no watchtower label; image bumps are a Harah PR like the
  other stacks.
