# Open items (measured, dated; re-measure before acting)

**2026-11-12, Pi-hole (mini):**

- 🟡 **DHCP moves to the mini; the switch is pending.** Alex chose it
  2026-11-12 (the BGW320 has no DHCP DNS field). Prepared: `skill/network/
  dnsmasq.conf` installed to `/opt/homebrew/etc`, `gateway.py dhcp on|off`,
  `dhcp-takeover.sh` (preflight passes except the mini's manual IP). Waiting
  on Alex at the keyboard: `sudo networksetup -setmanual …`, `sudo brew
  services start dnsmasq`, then his word for `gateway.py dhcp off`. Until then
  only hand-pointed devices are filtered. Second decision after it: `gateway.py
  ipv6lan dhcpv6 off` so dual-stack devices stop using the gateway's IPv6
  resolver.
- 🟡 **Dashboard frontend still hardcodes the old LAN IP:** `dashboard/web/src/App.tsx` `SERVER_HOST = '192.168.68.200'`; needs the `.1.200` value, `npm run build` and a service restart (dev-notes). Doctrine files were corrected 2026-11-12.
- 🟢 **Per-client visibility** (2026-11-12): solved by putting the root dnsmasq
  in front of the Pi-hole on the LAN's `:53` with EDNS0 Client Subnet; the
  container moved to `127.0.0.1:5335` (5353 is mDNSResponder's). Verify after
  the switch that the dashboard shows `192.168.1.x` clients.

**2026-11-08, measured on the mini (security sweep, Caddy up, fleet stopped):**

- 🔴 **No `scan/` routine.** POLICY's deployed-app security maintenance
  (2026-11-08) is hand-run: Trivy over running images + default-branch
  lockfiles, feeding Layer 2. Needs a runner (schedule, log, dashboard
  state) or the resolver prompt grows the scan step. Until then it only
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
- **No scheduled DB backups.** The dashboard panel is manual-only.
- **Stale Caddy blocks**: `msymmonds.app`, `resume.msymmonds.app`,
  `jupyter.lxrbckl.com` (containers gone).
- **Exposed PATs** in `~/.zsh_history` and `~/docker-bare-run/*/docker-compose.yml`
  on the mini. Alex's to rotate.
