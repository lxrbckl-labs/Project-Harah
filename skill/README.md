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
- **[alerts/](alerts/)** — the security-alert watch: `collect.py` (reads
  open Dependabot alerts, diffs against the last pass, decides grooming's
  cadence), `alerts.sh` (one pass), `enable.sh`/`disable.sh` (launchd, every
  6h). **Read-only against GitHub** — it never merges or comments, and it
  never widens POLICY.md's merge authority.

An agent asked to work the homelab should read SKILL.md, then pull the
specific file the task needs. Changes to doctrine are commits to this
repo — push them.
