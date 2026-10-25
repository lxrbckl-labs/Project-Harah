# Open items (measured, dated; re-measure before acting)

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
