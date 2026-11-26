# Open items (measured, dated; re-measure before acting)

**2026-11-26, gateway IPv6 and Pi-hole (mini):**

- 🟡 **`gateway.py ipv6lan dhcpv6 off` does not stick on the BGW320.** Alex's word 2026-11-26 02:41 ("turn it off"), so dual-stack devices stop being handed the gateway (`2600:1700:181f:210::1`) as IPv6 resolver and bypassing the Pi-hole. Two attempts: 02:41:59 the POST was accepted (page showed `dhcpv6 = off`) and had reverted to `on` by 02:43:03; 02:44 the POST was accepted again, held through +45 s of re-reads, and had reverted by 02:58:02. `ipv6lan` and `dhcpv6pd` stayed `on` both times; the form is three selects plus nonce and Save, no hidden fields, no error text. The page itself says DHCPv6 "configuration details are configured by your service provider", so the likely cause is the provider-managed config (or a PD-requires-DHCPv6 rule) restoring it. Not retried further. Options, Alex's call: (a) one attempt with `dhcpv6` and `dhcpv6pd` off together (PD serves only downstream routers asking for a prefix; nothing on this LAN does); (b) `ipv6lan off` (LAN loses IPv6 entirely; every hosted name is IPv4-only, A records on 99.109.232.114, no AAAA, so nothing hosted breaks); (c) accept the IPv6 bypass. Measured: the mini's own DHCPv6 lease (`::46`, DNS `::1`) was still being renewed at 02:58.
- 🟡 **`.local` SOA loop between the Pi-hole and the host dnsmasq.** Measured 02:50: of 1,448 queries since 02:22, 993 were `SOA local` from the MacBook (`192.168.1.201`, mDNSResponder's unicast probe, ~50/min), all forwarded by FTL to `192.168.1.200` because Pi-hole's revServers setting also emits `server=//192.168.1.200` (single-label names go to the conditional forwarder); the host dnsmasq has `domain-needed` and never answers, so the MacBook retries forever. Harmless noise, but it is two thirds of the query log. Fix, Alex's word (needs his `sudo brew services restart dnsmasq`): add `local=/local/` to `skill/network/dnsmasq.conf` (and the live `/opt/homebrew/etc/dnsmasq.conf`) so `.local` gets an authoritative NXDOMAIN and never leaves the host, per RFC 6762.

**2026-11-26, headless Claude on the mini:**

- ✅ **`claude -p` on the mini failed with `OAuth session expired` — CLOSED 2026-11-26 02:32 CST.** Measured 02:24 interactively and in `~/Library/Logs/harah-pihole.log` (the weekly Pi-hole audit's agent step exited 1 on 2026-11-15 and 2026-11-22). The scheduler skill's gotcha, not launchd: Alex re-ran `/login` at the mini at 02:3x; `claude -p "reply OK"` then printed OK and `launchctl kickstart -k gui/$(id -u)/com.alex.harah-pihole` ran the audit end to end (exit 0, 26 shortlisted, 0 DENY / 18 KEEP / 8 UNSURE, propose mode, state `ok`). Dark since 11-15, so 11 days of audits were lost; the proof-of-life is `doctor.sh` reading `pihole-state.json`. Residual: the run logs `[claude-code:unrecognized_model] claude-fable-5-2`, i.e. `audit.sh` asks for a model slug this CLI does not know and falls back; harmless today, worth pinning to a current slug.

**2026-11-13, Docker networking (mini):**

- ✅ **Containers cannot reach the LAN (192.168.1.0/24) — CLOSED 2026-11-26 02:22 CST.**
  Root cause: the Docker network `caddy_default` (created 2026-07-03) had been
  given `192.168.0.0/20` by the engine's automatic address pool, a range that
  contains the LAN. Inside the VM that is a connected route on the caddy
  bridge, so every container's LAN-bound packet (TCP, UDP, ICMP) died there and
  never reached macOS. Ruled out by measurement first: the dual-homing (`en1`),
  the macOS 15 Local Network permission (toggled, then a full reboot: no
  change), the firewall. Fix, on Alex's word: `~/docker-bare-run/caddy/
  docker-compose.yml` now declares `networks.default.ipam.config.subnet:
  10.90.0.0/24` (backup `docker-compose.yml.bak-20261126-pre-subnet`); `docker
  compose up -d` recreated the network and the container with a sub-second
  blink. Verified after: every public site answers; from a container
  `192.168.1.254:80`, `.67:6466`, `.220:22`, `.200:8123` all open; the
  Pi-hole's upstream `192.168.1.254:53` and revServers `192.168.1.200:53` are
  reachable and reverse lookups return LAN names again. No Pi-hole config
  change was needed. Vault change log: `Homelab/Network/Apartment.md`
  (2026-11-26). The original 2026-11-13 measurement is in git history.
- 🟡 **Docker's automatic address pool can hand a stack a LAN-overlapping
  subnet again.** The fix above pins only Caddy's network. Hygiene, Alex's
  call: `~/.docker/daemon.json` gets `"default-address-pools":
  [{"base":"172.17.0.0/12","size":16},{"base":"10.200.0.0/16","size":24}]`
  (keeps `192.168/16` out of Docker entirely); takes effect after a Docker
  Desktop restart (every container blinks); existing networks keep their
  subnets. Until then, a new stack whose network lands in `192.168.0.0/20`
  would re-create the outage: check `docker network inspect` subnets against
  `192.168.1.0/24` when adding a stack.

**2026-11-12, Pi-hole (mini):**

- 🟢 **DHCP moved to the mini (2026-11-12 23:59 CST).** Gateway DHCP off via
  `gateway.py dhcp off` on Alex's word; the mini's root dnsmasq serves DHCP on
  `:67` and DNS on `:53` (front door for the Pi-hole on `127.0.0.1:5335`). First
  lease proven: MacBook-Pro `192.168.1.201`, 23:59:44. Devices still holding a
  gateway lease roll over within their 1-day lease. **Open follow-on decision:**
  `gateway.py ipv6lan dhcpv6 off` so dual-stack devices stop using the
  gateway's IPv6 resolver (today they can bypass the Pi-hole over IPv6).
  Rollback: `gateway.py dhcp on` + `sudo brew services stop dnsmasq`.
- 🟢 **Per-client visibility** (2026-11-12): solved by putting the root dnsmasq
  in front of the Pi-hole on the LAN's `:53` with EDNS0 Client Subnet; the
  container moved to `127.0.0.1:5335` (5353 is mDNSResponder's). Verify after
  the switch that the Pi-hole admin page shows `192.168.1.x` clients.

**2026-11-08, measured on the mini (security sweep, Caddy up, fleet stopped):**

- 🔴 **No `scan/` routine.** POLICY's deployed-app security maintenance
  (2026-11-08) is hand-run: Trivy over running images + default-branch
  lockfiles, feeding Layer 2. Needs a runner (schedule, log, state file)
  or the resolver prompt grows the scan step. Until then it only
  happens in a hand-run session.
- 🔴 **Merged, not deployed:** Project-DS#48, Project-LucidIndex#142,
  Project-Showalter#92, Project-Fenaverat#16 (V5) landed 2026-11-08 with
  build runs `skipped`. Images on the mini are months old (DS 19C/233H,
  reactive-resume 21C/260H by Trivy). Publish + deploy per stack now run
  under POLICY without asking (Alex, same day); check the session's record
  in the vault, `Homelab/Security-Sweep-2026-11-08.md`, for what landed.
- 🟢 **reactive-resume: build repaired and deployed 2026-11-08** (#37 build
  repair, #36 security deps, #38 runtime fixes). The image after #37+#36
  built but answered 500 on every route; running each build in the live
  stack found four layered causes (tsyringe needs `reflect-metadata` →
  `NODE_OPTIONS=--import=reflect-metadata`; better-auth 1.7 twoFactor
  columns → drizzle migration; `@tanstack/start-server-core` XSS override
  vs `react-start` 1.168 → moved to 1.169/1.170; `inputValidator` →
  `validator`). Rolled back to the 2026-02-07 Hub image between attempts
  (POLICY layer 3). **Lesson for the resolver: a passing `docker build` is
  not verification for this repo; swap the image into the stack and request
  `/`, `/auth/login`, `/api/auth/ok`.** Residual: each SSR render logs
  `router.serverSsr?.isDehydrated is not a function` (react-start-server
  1.167.52 vs router-core 1.171) while still returning 200; watch for the
  TanStack release that aligns them.
- 🟡 **reactive-resume compose: `seaweedfs-create-bucket` uses
  `quay.io/minio/mc:latest`, which is gone** (quay returns 401 anonymously,
  Docker Hub `minio/mc` removed). The bucket already exists, so the stack was
  brought up with `--no-deps` around it (2026-11-08). Replace the helper
  (e.g. `amazon/aws-cli` or SeaweedFS's own `weed shell`) or drop the service.
- 🟢 **Showalter healthcheck fixed** (#93, issue #91 closed): dials 127.0.0.1;
  container healthy for the first time since deploy. Image built locally.
- 🟢 **Probing the public URL from the mini does not hairpin** on the
  apartment AT&T gateway. Fixed in both probes: `deploy-check/verify.py`
  resolves the host to 127.0.0.1 (where Caddy listens), and as of 2026-11-08
  `prove/prove.py` does the same through a loopback `HTTPSConnection`
  (SNI, Host and certificate verification stay on the real name; set
  `HARAH_PROVE_LOOPBACK=0` to probe the public path from elsewhere). The
  `ds` /mcp check now expects the app's own `401 unauthorized`. A hand run
  is not proof of the scheduled path (SERVER.md rule 2): kickstart it when
  prove is re-enabled.
- 🟢 **deploy-check targets** gained Project-Fenaverat (V5, `lxrbckl.com`) and
  Project-LucidIndex (four images, `lucidindex.lxrbckl.com`).
- 🟡 **Watchtower image is from 2023-11, project archived, 5C/54H.** Replace
  (Alex's call; it is a third-party image under `~/docker-bare-run/`).
- 🟢 **Stale Dependabot alerts to dismiss:** ~80 on Project-Fenaverat cite a
  `Pipfile.lock` that no longer exists; 5 on SelfStack cite a missing
  `requirements.txt`. Project-DS keeps 5 low (SvelteKit 3 major, deepmerge
  no fix).
- 🔴 **DockerHub org token still dead, re-measured 2026-11-08** (correcting
  the same-day note that called the item stale: the Showalter build that
  succeeded on 2026-04-29 predates the August failures). Today's publishes:
  Project-Fenaverat run 42530675666 and Project-Showalter run 42530758069
  failed at "Log in to DockerHub" with `unauthorized: incorrect username or
  password`; Project-DS run 42530828076 failed with "Username and password
  required" (private repo; org secrets do not reach it on this plan).
  **Project-LucidIndex builds**: it has REPO-level `DOCKERHUB_TOKEN` /
  `DOCKERHUB_USERNAME` set 2026-08-08, so a working token exists. Alex's
  one action: put that token in the org secrets (or in each repo). Until
  then the mini builds its own images from the merged commits and runs them
  under the compose tags (done 2026-11-08 for DS, Showalter, Fenaverat,
  reactive-resume); Docker Hub stays stale, so Watchtower must stay off or
  it would roll them back to the old Hub images.
- Harah's 22 launchd routines were **disabled by Alex on 2026-11-07** for mini
  maintenance. Do not `ensure.sh`/`bootstrap.sh` until he says the mini is
  back in service.

**2026-10-25, measured from the MacBook (mini unreachable):**

- 🔴 **Harah is down.** Heartbeat texts stopped **9/6** (last: 🟡, 5 alive, 1
  warning). Grooming kept merging on its 6h cadence until **10/10 7:32am**,
  then nothing. The home IP answers ping but 80/443 are closed, so the mini
  is off, Docker/Caddy stopped, or the port forward is gone. Nobody noticed
  for two weeks. First move: on the mini, `bash skill/doctor.sh`, then
  `bootstrap.sh`. Then find out what happened on 10/10.
- 🔴 **Backlog while down:** 355 open Dependabot alerts in `lxrbckl-labs`
  (27 critical, 161 high, 143 medium, 24 low) vs 0 on 8/25; **39 open
  dependabot PRs**, oldest 4/13 (Project-ACLG). Layers 1 and 2 clear this
  once alive.
- 🔴 **DockerHub token dead since 10/2025** (org secrets `DOCKERHUB_TOKEN` /
  `DOCKERHUB_USERNAME`). No `publish` can build an image. Alex's to rotate
  (or move the shared workflow to ghcr.io with `GITHUB_TOKEN`). Until then,
  merges land on `main` and nothing reaches the containers; layer 3 has
  nothing to prove.
- 🟡 **project-harah App (ID 4689872)**: pem still on the MacBook, not the
  mini. Optional; routines run as the legacy identity until moved.
- 🟡 **`ds.lxrbckl.com` 502** at the site root (Caddy routes `/` to a
  Project-DS `app` service with no container). Decision for Alex: bring
  `app` up, or narrow the Caddy block to `/mcp*`.
- 🟡 **`reactive-resume` `main` cannot `pnpm build`** (TanStack Start skew;
  a framework migration, not a bump). `pnpm typecheck` is that repo's signal.
- 🟢 **Showalter healthcheck is cosmetic** (IPv6 probe vs IPv4 bind); fix
  filed as Project-Showalter#91, needs a publish to reach the container.
- **No scheduled DB backups, and since 2026-11-26 no button either.** The
  dashboard that ran them was retired; the command is in WORKFLOWS.md.
- **Stale Caddy blocks**: `msymmonds.app`, `resume.msymmonds.app`,
  `jupyter.lxrbckl.com` (containers gone).
- **Exposed PATs** in `~/.zsh_history` and `~/docker-bare-run/*/docker-compose.yml`
  on the mini. Alex's to rotate.
