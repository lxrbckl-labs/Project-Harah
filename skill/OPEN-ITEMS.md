# Open items (measured, dated; re-measure before acting)

**2026-11-08, measured on the mini (security sweep, Caddy up, fleet stopped):**

- 🔴 **No `scan/` routine.** POLICY's deployed-app security maintenance
  (2026-11-08) is hand-run: Trivy over running images + default-branch
  lockfiles, feeding Layer 2. Needs a runner (schedule, log, dashboard
  state) or the resolver prompt grows the scan step. Until then it only
  happens in a hand-run session.
- 🔴 **Merged, not deployed:** Project-DS#48, Project-LucidIndex#142,
  Project-Showalter#92, Project-Fenaverat#16 (V5) landed 2026-11-08 with
  build runs `skipped`. Images on the mini are months old (DS 19C/233H,
  reactive-resume 21C/260H by Trivy). A `publish` per repo on Alex's word,
  then `compose pull && up` once he brings the fleet back.
- 🟡 **reactive-resume#36 open:** 16 packages fixed, lockfile scans clean,
  but `main` cannot build (h3 pin → nitro export error; raising h3 exposes a
  better-auth 1.7.7 vs `@better-auth/*` 1.6.30 split). Deployed image is from
  2026-02-07. Repair underway in its own session.
- 🟡 **Watchtower image is from 2023-11, project archived, 5C/54H.** Replace
  (Alex's call; it is a third-party image under `~/docker-bare-run/`).
- 🟢 **Stale Dependabot alerts to dismiss:** ~80 on Project-Fenaverat cite a
  `Pipfile.lock` that no longer exists; 5 on SelfStack cite a missing
  `requirements.txt`. Project-DS keeps 5 low (SvelteKit 3 major, deepmerge
  no fix).
- 🟢 **The 10/2025 "DockerHub token dead" item below is stale:** org secrets
  were rotated 2025-10-18 and Project-Showalter's `publish` built successfully
  on 2026-04-29. A publish should build; verify on the first one.
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
