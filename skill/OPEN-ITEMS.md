# Open items (keep this current; also rendered by the dashboard where noted)

- 🔴 **DEPLOYS ARE DEAD ORG-WIDE — the DockerHub token is rejected.** Found
  2026-08-17 by the first real publish. The build fails at *Log in to
  DockerHub*: `unauthorized: incorrect username or password`. Org secrets
  `DOCKERHUB_TOKEN` / `DOCKERHUB_USERNAME` were last updated **2025-10-18** —
  ten months ago — and Docker Hub PATs expire. **No `publish` on any repo can
  produce an image until Alex rotates that token**, which is why every stack is
  running months-old code (Jordyn 9d, reactive-resume 44d) no matter what gets
  merged. Harah cannot fix this: rotating credentials is a hard stop.
  Fix: new Read/Write PAT at hub.docker.com → org secret `DOCKERHUB_TOKEN`.
  **This is now the single highest-value action on the board** — it unblocks
  every deploy at once. Safe failure mode confirmed: a failed build produces no
  image, so the live containers were never touched.
- 🟡 **project-harah REGISTERED (App ID 4689872) — pem still on the MacBook.**
  Created + installed on both owners 2026-08-23; token mint + first [bot]
  comment verified. Remaining: Alex moves app-id + private-key.pem to the
  MINI's ~/.harah/app/ (then deletes the MacBook copies in ~/Downloads and
  ~/.harah/app — mini-only rule). Until then, mini routines use the legacy
  identity fallback. Trigger reminder: `@project-harah`, never plain `@harah`.
- ⚠️ **Exposed GitHub PATs** — live `ghp_…` tokens in plaintext in
  `~/.zsh_history` and in `~/docker-bare-run/*/docker-compose.yml`.
  Recommend rotating at github.com/settings/tokens.
- 🔴 **Alert remediation is Harah's standing assignment (Alex, 2026-08-16):**
  "get all the alerts resolved — that's your issue now." Work the list down
  under `grooming/POLICY.md`; the resolve-and-verify mandate governs.
  **Status after the 2026-08-16 20:xx resolver session — 93 open, and every
  single one is BLOCKED. Nothing is actionable by Harah right now:**
  - ✅ **DONE** — `Project-Jordyn` **PR #17**: 29 transitive alerts closed
    (15 high, 13 medium, 1 low) via major-scoped `pnpm.overrides` —
    brace-expansion, flatted, glob, js-yaml, mdast-util-to-hast, minimatch,
    picomatch, postcss, yaml. Verified `pnpm install --frozen-lockfile`,
    `pnpm run build`, `pnpm run lint` all exit 0, build output
    byte-identical to the `main` baseline. Took Jordyn 95 → 66.
    **Merged, NOT deployed** — CI `skipped` (publish gate); container
    `project-jordyn` still on the 8-day-old image, serving HTTP 200.
  - ⏸️ **`Project-Jordyn` — 66 alerts, ALL `next`** (2 critical, 24 high,
    32 medium, 8 low) → **Alex's PR #16** (14.2.4→15.5.21 + React 19).
    Human-authored: hands off. **Merging #16 clears all 66** — the single
    highest-value action left anywhere on the board, and it's Alex's.
    ⚠️ **Merging #17 flipped #16 to CONFLICTING.** Only `pnpm-lock.yaml`
    conflicts (`package.json` merges clean); resolve by regenerating.
    Harah test-merged this locally and confirmed #16 + #17 build green
    together — see the signed comment on #16 for the exact recipe.
  - ⏸️ `reactive-resume` — **20 of its 22 alerts are better-auth** (2
    critical, 12 high, 2 medium, 2 low, all closed by ≥1.6.22) →
    **Alex's PR #15**, which lands 1.6.26. Human-authored: hands off, and
    it is currently **CONFLICTING** so it needs his rebase. Harah must not
    do this one independently anyway: 1.5.0-beta.9→1.6.x is a
    **prerelease→stable transition with DB migrations**, which POLICY
    disqualifies by name.
  - ⛔ `reactive-resume` `extract-zip` (high, #209) — **no published fix
    exists**; latest is 2.0.1 and that is the vulnerable version. Reachable
    only via `@puppeteer/browsers@2.11.1`. The one escape is
    `puppeteer-core` **24.36.0 → 25.7.0** (a MAJOR), whose
    `@puppeteer/browsers@3.2.0` drops extract-zip entirely. Queued, not
    forced: it's the PDF-rendering engine, `pnpm build` is broken on `main`,
    so only `typecheck` is available and that cannot exercise a browser
    launch. Note the real exposure is likely nil — this deployment uses
    `puppeteer-core` against a separate Chrome container and never runs the
    browser-download path where the symlink traversal lives.
  - ⛔ `reactive-resume` `drizzle-orm` (high, #75) — patched **only in
    `1.0.0-beta.20`, a prerelease**, from a prerelease. POLICY disqualifies
    prereleases on either side. Dependabot #4 wants `1.0.0-rc.1`: same
    problem. Needs Alex.
  - ⛔ `Project-ASBC` (4: 2 medium torch/pytest, 2 low torch) and
    `Project-RCoD` (1 medium pytest) — **no verification signal exists in
    either repo**: no CI, no `.github/workflows`, no test suite, and poetry
    isn't installed on the mini. The fix itself is trivial (`poetry lock`
    refresh; `torch ^2.8.0` already admits the patched 2.13.0), but POLICY
    forbids merging what can't be verified. **Unblocking these is Alex's
    call, and it's cheap** — even a CI job running `poetry check && poetry
    install` would make all 5 mergeable. Until then more sessions cannot
    help.
- 🔴 **`reactive-resume` `main` cannot build — CI has been red since at
  least 2026-08-15** (found 2026-08-16). `pnpm build` dies before compiling:
  the unbounded `"h3": ">=2.0.1-rc.17"` override floated to `h3@2.0.1-rc.20`,
  which dropped `resolveDotSegments`, so `h3-rules` fails to import and
  `vite.config.ts` won't load. **Every merge to `main` therefore produces no
  new image** — the live containers are still on a 6-week-old build. Fix =
  bound the `h3`/`h3-v2` overrides. Until then `pnpm typecheck` (green) is
  the only usable verification signal in that repo.
- ⚠️ **93 open Dependabot alerts** (re-derived 2026-08-16 ~20:30 after
  Jordyn PR #17): **4 critical, 40 high**, 37 medium, 12 low — down from
  122 at the start of that session, and from 228 at the round's start.
  `Project-Jordyn` 66, `reactive-resume` 22, `Project-ASBC` 4,
  `Project-RCoD` 1. Grooming can't clear these on its own — most have no
  dependabot PR behind them. Alert watch runs every 6h and has escalated
  grooming to a 6h cadence while criticals are open.
  **All 93 are currently blocked** (see the remediation item above): 86
  behind Alex's human PRs #16/#15, 2 with no published fix or prerelease-only
  fixes, 5 in repos with no verification signal. The loop has nothing left
  to resolve until Alex acts.
- **Dependabot alerts are DISABLED** on the personal repos `lxRbckl/.claude`,
  `lxRbckl/Obsidian`, `lxRbckl/lxRbckl`, `lxRbckl/roulette-skill` — they will
  never alert. Enabling is a repo-settings change, so it's Alex's to make.
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
