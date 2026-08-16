# Project-Harah — dev notes

Development knowledge for **this** repository, kept **in-repo** rather than in
Alex's Obsidian vault: the project owns its own history, and notes that travel
with the code can't drift from it or go missing when the vault isn't at hand.
(Moved out of the vault 2026-08-16 — see SKILL.md, "Project dev notes".)

`lxrbckl-labs/Project-Harah` (**public**; was `lxRbckl/ServerManager`,
transferred + renamed 2026-08-15). Checked out on the mini at
**`~/lxrbckl-dev/Project-Harah`**, beside the other project checkouts. There is
only ever **one** checkout; never clone a second copy.

It lived at `~/Documents/ServerManager` until 2026-08-16 and was moved for a
hard reason: **macOS TCC will not let launchd run scripts out of `~/Documents`**,
so every scheduled routine in this repo failed with `Operation not permitted`
(exit 126) while passing every manual test. Don't move it back.

## What this repo is

1. **The ServerManager dashboard** — FastAPI backend (`dashboard/backend/app.py`)
   + Vite/React-TS frontend (`dashboard/web/`). FastAPI serves the built
   `web/dist` *and* the API from one origin on **port 8770** (canonical — don't
   change it). Deliberately **not** behind Caddy, and it has **no auth**.
2. **The Harah agent doctrine** (`skill/`) — moved out of the operator's config
   repo 2026-08-16 so that repo never names this project. Entry point:
   `skill/README.md`.

## Stack

Backend: Python 3.14 (system Python — FastAPI/psutil/pydantic wheels do install
on it), venv at `dashboard/backend/.venv`. Frontend: Vite 8 + React 19 +
TypeScript; `npm run build` → `web/dist`. No Drizzle/pnpm/Postgres here — the
backend reads Docker and the Caddy access log.

## How it runs on the mini

| launchd job | Schedule | Installed by |
|---|---|---|
| `com.lxrbckl.servermanager-dashboard` | KeepAlive + RunAtLoad | `dashboard/enable.sh` |
| `com.alex.harah-grooming` | dynamic (see below) | `skill/grooming/set-cadence.sh` |
| `com.alex.harah-alerts` | every 6h | `skill/alerts/enable.sh` |

Every installer is **self-locating** (the plist points at the script beside it),
so re-run them after moving the checkout. Logs:
`~/Library/Logs/harah-{grooming,alerts}.log`,
`~/Library/Logs/servermanager-dashboard.log`. State lives in `~/.harah/`.

## The grooming ↔ alerts correlation

`groom.sh` only sees dependabot **PRs**. Alerts fire with or without a PR — the
measured gap on 2026-08-16 was **3 PRs vs 228 alerts** (6 critical, 98 high). So
`skill/alerts/` reads alerts every 6h and sets grooming's cadence: critical →
6h, high → 12h, otherwise daily 04:30. `set-cadence.sh` is the **single owner of
the grooming plist** (grooming's `enable.sh` delegates to it) and is idempotent.

**Cadence is not authority** — escalation makes grooming run sooner, never merge
more. `skill/grooming/POLICY.md` remains the sole merge authorization.

## Scar tissue

- **macOS TCC blocks launchd from running scripts inside `~/Documents`.** A
  launchd-spawned interpreter gets `Operation not permitted` (exit 126) reading
  a script there — so a routine can pass every manual test and still never fire
  on schedule. Verified 2026-08-16: the identical script exits 0 from outside
  `~/Documents`. **Test a scheduled job with `launchctl kickstart`, never only
  by running the script by hand.**
- **launchd's PATH excludes `/usr/local/bin`**, where Docker Desktop symlinks
  `docker`. When the dashboard moved from hand-started to launchd, `/api/health`
  kept returning 200 while every Docker call failed and the UI showed 0
  containers. The plist now sets `EnvironmentVariables → PATH`. **Health ≠
  Docker reachability — check `/api/containers` after any launch change.**
- The dashboard was a **hand-started orphan for 34 days** (parent = launchd,
  nothing managing it) and would not have survived a reboot. Never start it in a
  terminal; use `dashboard/enable.sh`.
- Frontend changes need `cd dashboard/web && npm run build` **and** a service
  restart, or the stale bundle keeps being served.
- `~/docker-bare-run/` holds **plaintext secrets** — never commit it.
- Guardrail enforced in code: `ALLOWED_ACTIONS = {start, stop, restart}`; the
  API returns 400 for remove/rm/kill/delete. Keep that invariant.
- `groom.sh` logs via `tee` while launchd also captures stdout to the same
  file, so scheduled passes double-log each line. Cosmetic; don't read it as
  two passes.

## Conventions

Ship a change = build if the frontend changed → `git add -A && git commit &&
git push`, **automatically, without being asked**. Outward-facing writes (PR and
issue comments, non-merge commits) are signed `— Harah`.
