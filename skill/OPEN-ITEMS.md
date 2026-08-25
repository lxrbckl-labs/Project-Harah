# Open items (keep this current; also rendered by the dashboard where noted)

- 🔴 **DEPLOYS ARE DEAD ORG-WIDE — the DockerHub token is rejected.** Found
  2026-08-17 by the first real publish. The build fails at *Log in to
  DockerHub*: `unauthorized: incorrect username or password`. Org secrets
  `DOCKERHUB_TOKEN` / `DOCKERHUB_USERNAME` were last updated **2025-10-18** —
  ten months ago — and Docker Hub PATs expire. **No `publish` on any repo can
  produce an image until Alex rotates that token**, which is why every stack is
  running months-old code no matter what gets merged (re-measured 2026-08-23:
  **reactive-resume 50 days behind `main`**, both tenants healthy on an image
  built 2026-07-03). Harah cannot fix this: rotating credentials is a hard stop.
  Fix: new Read/Write PAT at hub.docker.com → org secret `DOCKERHUB_TOKEN`.
  **This is now the ONLY thing between Harah and a maintained estate** — as of
  2026-08-23 the alert board is empty and the publish authority question is
  settled, so this credential is the whole remaining gap. Tracked as
  OPERATOR-BLOCKED `dockerhub-pat-dead` (**day 9** as of 2026-08-25) and
  texted daily. The 2026-08-25 ping added a second option to offer:
  **ghcr.io**, which the shared workflow could publish to with the built-in
  `GITHUB_TOKEN` and no DockerHub credential at all — Alex's infrastructure
  call (it moves where images live and what watchtower pulls), not Harah's
  to execute.
  Contrast worth knowing: the PyPI token in `lxRbckl/lxRbckl`, also never
  rotated (2023-11-21), published fine on 2026-08-23 — this is Docker Hub's
  revocation, not a generic secrets problem. Safe failure mode confirmed: a
  failed build produces no image, so the live containers were never touched.
- 🟡 **project-harah REGISTERED (App ID 4689872) — pem still on the MacBook.**
  Created + installed on both owners 2026-08-23; token mint + first [bot]
  comment verified. Remaining: Alex moves app-id + private-key.pem to the
  MINI's ~/.harah/app/ (then deletes the MacBook copies in ~/Downloads and
  ~/.harah/app — mini-only rule). Until then, mini routines use the legacy
  identity fallback. Trigger reminder: `@project-harah`, never plain `@harah`.
- 🟢 **groom.sh wording lag (small, code):** its queue comments still say
  "Queued for Alex" — under the Mandate they queue for the RESOLVER. Reword
  the string (and wire its gh calls through app/as-bot.sh) next time the
  script is touched.
- ⚠️ **Exposed GitHub PATs** — live `ghp_…` tokens in plaintext in
  `~/.zsh_history` and in `~/docker-bare-run/*/docker-compose.yml`.
  Recommend rotating at github.com/settings/tokens.
- 🟢 **Alert remediation is Harah's standing assignment (Alex, 2026-08-16):**
  *"get all the alerts resolved — that's your issue now."* Work it under
  `grooming/POLICY.md`. **This file no longer carries alert counts** — POLICY's
  reporting section makes [`docs/dev-notes.md`](../docs/dev-notes.md)'s dated
  re-derivations the board of record, and every count previously listed here
  went stale within days and then contradicted live measurement (the 2026-08-22
  drill). Read dev-notes, then measure live with `gh`, in that order.
  **Last measured 2026-08-25: 0 open alerts AND 0 open dependabot PRs across
  all 39 owned non-archived repos, 0 dark.** Nothing is queued and nothing is
  blocked behind a human PR.
  **Coverage is two switches, and only one had ever been measured here.**
  `vulnerability-alerts` is the sensor; `automated-security-fixes` is the
  responder that opens the remediation PR. Alerts read 39/39 for weeks while
  security updates were **23/39** — sixteen repos, including the deployed
  Project-DS, Project-Showalter and Project-VoiceToColumn, could see a
  vulnerability and not propose the fix. Enabled on all sixteen 2026-08-25
  (POLICY: visibility); re-read afterwards, **39/39 on both switches**. When
  reporting coverage, say which switch was measured.
- 🟡 **`reactive-resume` `main` still cannot `pnpm build`** (since 2026-08-15).
  The original cause — the unbounded `"h3": ">=2.0.1-rc.17"` override floating
  to `h3@2.0.1-rc.20`, which dropped `resolveDotSegments` — is fixed by **PR
  #22** (open, Harah's, `MERGEABLE`). Landing it does *not* make the build
  green: it uncovers an independent **TanStack Start family skew** (1.157.14
  declared, ≥1.167.30 pulled in by an override added to close an alert), which
  is a framework migration, not a dependency bump. Until then `pnpm typecheck`
  (green) plus a real-Postgres harness are that repo's usable signals — and
  note the build gate is a *publish* gate, so a red `pnpm build` does not by
  itself explain why nothing ships. The dead PAT does.
- 🟢 **Dependabot alerts on personal repos** — the long-standing claim here
  that they were disabled on `lxRbckl/.claude`, `Obsidian`, `lxRbckl`,
  `roulette-skill` was **measured false**. All five personal repos report
  enabled and 0 open. Enabling alerts on owned repos is authorised by POLICY
  (visibility) and no longer needs Alex.
- **No scheduled DB backups** — the panel is manual-only; a cron/launchd
  schedule is the obvious next step (the newsroom app / Project-DS /
  rxresume have no automated dumps).
- ~~**Dashboard isn't persistent**~~ — **RESOLVED 2026-08-16.** It now runs
  as launchd job `com.lxrbckl.servermanager-dashboard` (KeepAlive +
  RunAtLoad), installed by `dashboard/enable.sh` (self-locating; re-run
  after moving the checkout). Log: `~/Library/Logs/servermanager-dashboard.log`.
  KeepAlive respawn was live-fire tested. Was previously a hand-started
  orphan with 34 days uptime that would not have survived a reboot.
- **Stale Caddyfile blocks** for `msymmonds.app` / `resume.msymmonds.app`
  and `jupyter.lxrbckl.com`, whose containers were removed; msymmonds also
  has corrupt ACME lockfiles in the caddy_data volume.
- 🟡 **`ds.lxrbckl.com` returns HTTP 502 — needs a decision, not a repair.**
  Found 2026-08-25. The Caddy block routes `/mcp*` to `:4000` (the running
  `project-ds-mcp-1`, fine) and **everything else to
  `host.docker.internal:3671`**, which is Project-DS's compose `app` service.
  That service has **no container on this mini** and `lxrbckl/project-ds-app:main`
  is not even pulled, so the site root has been 502 for at least as long as the
  watchdog has been blind to it (`targets.json` carried `urls: []` for this repo,
  and its note wrongly said there was no Caddy block at all). The access log
  shows no real traffic, so nobody has been hitting it. Two clean options, both
  Alex's call: **bring the `app` service up** (creating a container is outside
  Harah's incident scope of start/stop/restart, and the stack may have been left
  down deliberately — same shape as the spun-down msymmonds tenant), or
  **narrow the Caddy block to `/mcp*`** so the domain stops serving 502. Now
  listed unsuppressed in `deploy-check/targets.json`, so it shows in Estate
  Health until it is decided.
- ~~**`showalter` reports unhealthy**~~ — **DIAGNOSED 2026-08-25, and it is
  cosmetic.** `FailingStreak: 13614` — the healthcheck has never passed. The
  image's `HEALTHCHECK` dials `http://localhost:5827/api/health`; the container's
  `/etc/hosts` puts `::1` first and the Next server binds IPv4-only
  (`HOSTNAME=0.0.0.0`), so the probe is refused. `127.0.0.1` returns
  `{"ok":true}`, and `https://sawyer.showalter.business` serves 200 — including
  the very endpoint the probe cannot reach. One-line fix filed as
  **Project-Showalter#91** (no Dependabot lineage, so filed rather than patched);
  it only reaches the container on a new image, which is gated on
  `dockerhub-pat-dead`. The public URL is now a watchdog target, so this repo has
  a true serving signal regardless.
- **Auto-defense**: `immich_server` and `vaultwarden` are armed, but the
  master switch is **off**, so nothing auto-stops. LAN IPs are
  trusted/exempt.
