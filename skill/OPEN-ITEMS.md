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
  OPERATOR-BLOCKED `dockerhub-pat-dead` (day 7) and texted daily.
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
  **Last measured 2026-08-23 19:45 CDT: 0 open alerts across all 39 owned
  non-archived repos** (coverage re-swept the same minute: 39/39 have
  Dependabot alerts enabled, 0 dark). Nothing is queued and nothing is blocked
  behind a human PR.
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
- **`showalter` reports unhealthy** (has for a while).
- **Auto-defense**: `immich_server` and `vaultwarden` are armed, but the
  master switch is **off**, so nothing auto-stops. LAN IPs are
  trusted/exempt.
