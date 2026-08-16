# Harah — the operating doctrine (read before touching the mini)

This directory is the version-controlled home of the Harah agent doctrine
(moved here from the operator's private config repo, 2026-08-16):

- **[SKILL.md](SKILL.md)** — the role, environment map, hard guardrails,
  gotchas, and the grooming summary + policy gate. Read it at the start
  of any session touching the Mac mini.
- **[WORKFLOWS.md](WORKFLOWS.md)** — standard procedures (Caddy change,
  add a subdomain, traffic investigation, backups, ship a change). Read
  when actually doing the task.
- **[OPEN-ITEMS.md](OPEN-ITEMS.md)** — mutable status; read when planning
  server work, keep it current.
- **[grooming/](grooming/)** — the dependabot grooming machinery:
  `POLICY.md` (the ONLY standing merge authorization — read before any
  merge decision), `groom.sh` (one pass), `enable.sh`/`disable.sh`
  (launchd install on the mini; self-locating, re-run after moving the
  checkout).

An agent asked to work the homelab should read SKILL.md, then pull the
specific file the task needs. Changes to doctrine are commits to this
repo — push them.
