# Open items (keep this current; also rendered by the dashboard where noted)

- ⚠️ **Exposed GitHub PATs** — live `ghp_…` tokens in plaintext in
  `~/.zsh_history` and in `~/docker-bare-run/*/docker-compose.yml`.
  Recommend rotating at github.com/settings/tokens.
- 🔴 **Alert remediation is Harah's standing assignment (Alex, 2026-08-16):**
  "get all the alerts resolved — that's your issue now." Work the list down
  under `grooming/POLICY.md`; the resolve-and-verify mandate governs.
  **Status after the 2026-08-16 06:16 resolver run — all 4 remaining
  criticals now sit behind ALEX's own PRs; none are Harah's to act on:**
  - ✅ **DONE** — `reactive-resume` `seroval` 1.4.2→1.6.2 and `basic-ftp`
    5.1.0→5.3.1, pinned via `pnpm.overrides`, merged as **PR #16**.
    Closed **2 critical + 3 high** (alerts #181, #20, #83, #86, #95),
    confirmed `fixed` by the API. Note the yield lesson: the critical only
    demanded basic-ftp 5.2.0, but 5.3.1 (same major) closed three more.
  - ⏸️ `Project-Jordyn` next criticals → **Alex's PR #16** (next
    14.2.4→15.5.21 + React 19, build+lint green, supersedes dependabot
    #11). Human-authored: **hands off, Alex merges.** The 14.2.35 patch
    route recorded earlier is now the WRONG move — it would duplicate and
    conflict with #16.
  - ⏸️ `reactive-resume` better-auth criticals (#148/#149, need ≥1.6.11)
    → **Alex's PR #15**, which lands **1.6.26** and supersedes dependabot
    #9's 1.6.2. Human-authored: hands off.
  - **Next run should skip criticals entirely** (nothing actionable) and
    start on `reactive-resume` highs: `hono` (4 high + 29 medium) and
    `undici` (5 high + 9 medium) are the biggest transitive clusters, same
    `pnpm.overrides` mechanism as PR #16.
- 🔴 **`reactive-resume` `main` cannot build — CI has been red since at
  least 2026-08-15** (found 2026-08-16). `pnpm build` dies before compiling:
  the unbounded `"h3": ">=2.0.1-rc.17"` override floated to `h3@2.0.1-rc.20`,
  which dropped `resolveDotSegments`, so `h3-rules` fails to import and
  `vite.config.ts` won't load. **Every merge to `main` therefore produces no
  new image** — the live containers are still on a 6-week-old build. Fix =
  bound the `h3`/`h3-v2` overrides. Until then `pnpm typecheck` (green) is
  the only usable verification signal in that repo.
- ⚠️ **223 open Dependabot alerts** (re-derived 2026-08-16 after PR #16):
  **4 critical, 95 high**, 103 medium, 21 low — down from 228/6 critical.
  Concentrated in `reactive-resume` (122 open, 2 critical) and
  `Project-Jordyn` (95 open, 2 critical). Grooming can't clear these on its
  own — most have no dependabot PR behind them. Alert watch runs every 6h
  and has escalated grooming to a 6h cadence while criticals are open.
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
