# Open items (keep this current; also rendered by the dashboard where noted)

- ⚠️ **Exposed GitHub PATs** — live `ghp_…` tokens in plaintext in
  `~/.zsh_history` and in `~/docker-bare-run/*/docker-compose.yml`.
  Recommend rotating at github.com/settings/tokens.
- 🔴 **Alert remediation is Harah's standing assignment (Alex, 2026-08-16):**
  "get all the alerts resolved — that's your issue now." Work the list down
  under `grooming/POLICY.md`; the resolve-and-verify mandate governs.
  **Two findings that redirect the obvious plan — the open dependabot PRs
  are the WRONG tool for both criticals:**
  - `Project-Jordyn` critical (**Authorization Bypass in Next.js
    Middleware**) is patched in **next 14.2.25** — a plain patch on the
    current 14.2.4 line. Dependabot's PR #11 proposes **15.5.21**, a major
    that grooming rightly refuses. **The auth bypass can be closed today
    with a patch bump; the major upgrade is separate and optional.** Don't
    let #11 hold the security fix hostage.
  - `reactive-resume` critical (**better-auth OAuth refresh-token replay**)
    needs **better-auth 1.6.11**. The prepared branch on PR #9 targets
    **1.6.2** — so completing that whole coupled migration as planned would
    still leave the critical OPEN. Retarget to 1.6.11 before the sitting.
  - Remaining criticals are transitive and look cheap: `seroval` → 1.5.3,
    `basic-ftp` → 5.2.0 (both `reactive-resume`).
- ⚠️ **228 open Dependabot alerts** (first full count, 2026-08-16):
  **6 critical, 98 high**, 103 medium, 21 low. Concentrated in
  `reactive-resume` (127 open, 4 critical) and `Project-Jordyn` (95 open,
  2 critical). Grooming can't clear these on its own — most have no
  dependabot PR behind them, and the two `reactive-resume` PRs that do
  exist are correctly queued as prerelease-risky. **Needs Alex's call on a
  deliberate upgrade pass.** Alert watch now runs every 6h and has
  escalated grooming to a 6h cadence while criticals are open.
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
