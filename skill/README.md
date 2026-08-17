# Harah — the operating doctrine (consult on demand)

This directory is the version-controlled home of the Harah agent doctrine
(moved here from the operator's private config repo, 2026-08-16):

- **[SKILL.md](SKILL.md)** — the role, environment map, hard guardrails,
  gotchas, and the grooming summary + policy gate. Consult on demand for
  the task at hand (grep/read the relevant section) — there is no
  start-of-session read mandate.
- **[WORKFLOWS.md](WORKFLOWS.md)** — standard procedures (Caddy change,
  add a subdomain, traffic investigation, backups, ship a change). Read
  when actually doing the task.
- **[OPEN-ITEMS.md](OPEN-ITEMS.md)** — mutable status; read when planning
  server work, keep it current.
- **[grooming/](grooming/)** — the dependabot grooming machinery:
  `POLICY.md` (the ONLY standing merge authorization — read before any
  merge decision), `groom.sh` (one pass), `enable.sh`/`disable.sh`
  (launchd install on the mini; self-locating, re-run after moving the
  checkout), `set-cadence.sh` (single owner of the grooming plist —
  schedules the job; the alerts routine drives it).
- **[mentions/](mentions/)** — `@harah` listener: polls Alex's repos every
  5 min and dispatches a scoped session to the PR he mentioned. Allowlisted
  authors only (this repo is public); a mention authorises looking, never
  merging.
- **[resolver/](resolver/)** — the scheduled Harah *session* that actually
  resolves alerts and queued PRs (launchd → headless `claude -p`; cadence and
  manual triggers are set from the dashboard's Security Alerts panel). `prompt.md` is its standing brief and re-reads
  POLICY.md every run. This is where resolution lives; `groom.sh` has none.
- **[incident/](incident/)** — the responder the watchdog fires on a new
  failure: confirm → diagnose → restart (cheap, reversible) → verify →
  escalate to a thinking session. Guards against the ways auto-remediation
  goes wrong: blips, crash-loops, thrashing, and stateful services.
- **[watchdog/](watchdog/)** — every 10 min, is everything Harah touches still
  serving? Checks every deployed target regardless of cause and records
  ok→down / down→ok **transitions** so a long-broken thing doesn't shout
  forever. **Read-only** — it reports; it never restarts or rolls back.
- **[deploy-check/](deploy-check/)** — after a merge: did it actually reach the
  running app? Walks merge → CI → image → container → real HTTPS request and
  reports how many days behind `main` the live code is. `targets.json` is the
  measured repo→container→URL map.
- **[alerts/](alerts/)** — the security-alert watch: `collect.py` (reads
  open Dependabot alerts, diffs against the last pass, decides grooming's
  cadence), `alerts.sh` (one pass), `enable.sh`/`disable.sh` (launchd, every
  6h). **Read-only against GitHub** — it never merges or comments, and it
  never widens POLICY.md's merge authority.

An agent asked to work the homelab should read SKILL.md, then pull the
specific file the task needs. Changes to doctrine are commits to this
repo — push them.

**Extending the machinery is different from doing a task.** Before adding or
changing a routine, script, or policy here, read SKILL.md (especially
*Standing rules for changing this system*), `grooming/POLICY.md`, and
[`docs/dev-notes.md`](../docs/dev-notes.md) **first** — the on-demand stance
above applies to using this system, not to building on it.
