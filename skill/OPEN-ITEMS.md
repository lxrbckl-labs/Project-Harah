# Open items (keep this current; also rendered by the dashboard where noted)

- ⚠️ **Exposed GitHub PATs** — live `ghp_…` tokens in plaintext in
  `~/.zsh_history` and in `~/docker-bare-run/*/docker-compose.yml`.
  Recommend rotating at github.com/settings/tokens.
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
