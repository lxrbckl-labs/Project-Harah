# Harah — the doctrine (read on demand)

Harah is the housekeeper of Alex's GitHub estate: it keeps the repos current
against Dependabot, resolves what the safe sweep can't, and proves that each
deploy still works. Simplified 2026-10-25; the previous, broader doctrine is
in git history.

- **[SKILL.md](SKILL.md)** — the role in one page: the three layers, what
  Harah does on its own, what it never does, how it reports.
- **[grooming/POLICY.md](grooming/POLICY.md)** — the only standing merge
  authorization. Read before any merge or resolution decision.
- **[SERVER.md](SERVER.md)** — the mini: machine map, hard guardrails,
  gotchas, standing rules for changing this system. Read when the task
  touches the machine. **[WORKFLOWS.md](WORKFLOWS.md)** has the procedures
  (Caddy change, add a subdomain, add a routine).
- **[OPEN-ITEMS.md](OPEN-ITEMS.md)** — what's blocked or undecided right now.
  Counts go stale; measure live with `gh` before acting on one.

## The layers and their machinery

| | dir | runner | cadence |
|---|---|---|---|
| 1 Sweep | `grooming/` | `groom.sh` (`--dry-run`) | daily 4:30am, escalated by `alerts/` |
| 2 Resolve | `resolver/` | `resolve.sh` → `claude -p prompt.md` (`--dry-run`) | daily 5:30am (dashboard: 6h / 12h) |
| 3 Prove | `prove/` | `prove.sh` → `prove.py` (`--force`, `--repo`, `--dry-run`) | every 10 min, acts on image change |

Supporting: `alerts/` (sensor, every 6h, read-only), `watchdog/` + `incident/`
(serving? confirm → restart → escalate), `heartbeat/` (daily 9:00am text; its
absence is the alarm), `deploy-check/` (`verify.py <owner/repo>` and
`targets.json`, the measured repo → container → URL → checks map),
`publish/` (hand-run by Alex only; not scheduled), `app/` (the
`project-harah` GitHub App identity, optional).

`doctor.sh` — one read-only health pass over every routine. Run it first when
anything seems silent. `bootstrap.sh` — installs all routines on the mini;
standing-authorized whenever doctor shows ✗.

Retired 2026-10-25, code kept for history: `mentions/` (the `@project-harah`
listener; no longer scheduled or installed by bootstrap).

## Recovery chain

1. The mini's hourly config-repo auto-pull runs a post-pull hook that
   bootstraps dead routines (it keys on the heartbeat agent).
2. Any Harah session on the mini runs `doctor.sh` and then `bootstrap.sh` on ✗.
3. Full rebuild: `gh auth login` as lxRbckl → config repo per the
   `synchronizer` skill → `gh repo clone lxrbckl-labs/Project-Harah
   ~/lxrbckl-dev/Project-Harah` (that exact path) → layer 1 does the rest
   within the hour, or `bash skill/bootstrap.sh` now. Manual gates that
   remain: Full Disk Access + Messages automation for the heartbeat text, the
   login Keychain for headless `claude -p`.
4. Proof of life is the daily text. 2026-10-25: it had been silent since 9/6
   and merges since 10/10 before anyone measured. Silence is the outage.

Doctrine changes are PRs to this repo. Before extending the machinery, read
SKILL.md, POLICY.md and `SERVER.md`'s standing rules, then
[`docs/dev-notes.md`](../docs/dev-notes.md).
