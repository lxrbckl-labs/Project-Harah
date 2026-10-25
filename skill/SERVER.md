# The server — machine map, guardrails, gotchas (read when touching the mini)

Everything below was the back half of `SKILL.md` until 2026-10-25, when the
doctrine was shortened to the three layers. Nothing here changed; it moved.
Read the section the task needs.

## The machine

| | |
|---|---|
| **Hardware** | Mac mini (2024), **Apple M4 Pro**, 12-core CPU (8P+4E), 16-core GPU, **48 GB** unified RAM |
| **OS** | macOS 15.x |
| **LAN IP** | `192.168.68.200` |
| **Public** | Domains (`*.lxrbckl.com`, `jbarger.app`, etc.) resolve **straight to the home IP** — no Cloudflare |
| **Docker** | Docker Desktop, containerd image store, ~35 containers; the Linux VM is allocated **~23.4 GB** |
| **Storage** | internal ~926 GB boot + **2× 4 TB external NVMe**: `/Volumes/NVME1` (immich photos), `/Volumes/NVME2` (vaultwarden data) |

Everything is fronted by a **Caddy** container doing automatic HTTPS + reverse proxy.

---

## Where things live

- **`~/lxrbckl-dev/Project-Harah`** — the project repo — **on the mini: one checkout only, this path** (the launchd routines run from it; a second mini clone invites split-brain). Other machines may hold their own clone for doctrine/dev work (the MacBook's lives at `~/lxrbckl-labs/Project-Harah`); routines never run there. Remote: `github.com/lxrbckl-labs/Project-Harah` (**public**; was `lxRbckl/ServerManager`, transferred + renamed 2026-08-15 — old URLs redirect, but update local remotes when convenient), `main` tracks origin. **Moved here from `~/Documents/ServerManager` 2026-08-16 — macOS TCC blocks launchd from running scripts inside `~/Documents`, which silently broke every scheduled routine in this repo (exit 126). Do not move it back under `~/Documents`, `~/Desktop`, or `~/Downloads`.**
  - `dashboard/backend/app.py` — FastAPI API (Docker control, stats, traffic, guardian, backups, pins)
  - `dashboard/web/` — Vite React-TS dashboard
  - `tools/caddy-traffic.py`, `tools/caddy-ensure-logging.py` — standalone CLI tools
  - `AGENT.md` — portable playbook for instrumenting *any* Docker+Caddy host
  - `docs/caddy-reverse-proxy-setup.md` — shareable Caddy setup guide
- **`~/caddyfile`** — the live Caddy config (bind-mounted into the container)
- **`~/docker-bare-run/`** — compose definitions for the non-compose containers (caddy, vaultwarden, watchtower, etc.). **Contains plaintext secrets — never commit.**
- **`~/servermanager-backups/`** — `pg_dumpall` output
- **`~/rxresume/`, `~/immich/`, `~/minecraft/`, `~/Project-*`** — individual stacks

### The dashboard

Runs on **port 8770** — this is the canonical, fixed port; don't change it without being told.

```sh
cd ~/lxrbckl-dev/Project-Harah/dashboard/web && npm run build     # after any frontend change
cd ../backend && .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8770
```

FastAPI serves the built `web/dist` **and** the API from one origin, so it's reachable at
`http://192.168.68.200:8770` from any device on the LAN. It is deliberately **not** behind Caddy.

---

## Hard guardrails

These aren't bureaucracy — each one exists because the downside is severe and irreversible.

**Never remove or delete containers, images, or volumes.** Stop / start / restart only.
Alex's data lives in named volumes and bind mounts; a stray `rm` is unrecoverable. The
dashboard API enforces this in code (`ALLOWED_ACTIONS = {start, stop, restart}`) and returns
400 for `remove`/`rm`/`kill`/`delete`. Keep that invariant if you extend the API.

**Don't expose the dashboard to the internet.** It controls Docker and has **no
authentication** (Alex's explicit choice for a trusted LAN). Adding it to the Caddyfile
would hand container control to anyone who can reach it.

**Back up and validate before changing `~/caddyfile`.** Caddy fronts Vaultwarden, Immich,
and every public site — a syntax error takes them all down. Copy the file, run
`caddy validate` against the *custom* image, and only then apply.

**Don't commit secrets.** `guardian_config.json`, `pins.json`, `resources.db`, `config.env`,
and everything in `~/docker-bare-run/` are gitignored or out-of-repo. Check `git status`
before committing.

**Confirm before user-facing disruption.** Stopping a service, recreating Caddy, or anything
with downtime: say what you're about to do and why. Reversible beats clever.

---

## Gotchas (hard-won — this is the real value here)

**Docker Desktop's single-file bind mount goes stale.** Edit `~/caddyfile` on the host and
`docker exec caddy caddy reload` will load a **stale copy** — validation passes on the host
file while reload errors on a phantom line. Two ways through:
- Write the file **in place** (truncate + write, preserving the inode) → `caddy reload` works.
- Or `docker compose -f ~/docker-bare-run/caddy/docker-compose.yml up -d --force-recreate`.
Certs live in external named volumes, so a recreate is safe.

**Caddy access logging is per-site.** There is no global "log everything" switch — an
unmapped host is silently absent from the log. Every site block needs `import accesslog`.
`tools/caddy-ensure-logging.py --check` reports gaps, `--fix` injects them. Treat "add a
subdomain" and "run the guard" as one action, or monitoring silently drifts.

**Docker Desktop masks external client IPs.** Published-port traffic is NAT'd, so Caddy sees
the gateway `192.168.65.1` as the source for *all* external clients (confirmed with a real
internet scanner in the logs). Consequence: **GeoIP, IP-banning, and attack attribution
cannot see real external IPs on this host.** The code is correct and works on a native Linux
Docker host or behind Cloudflare (trusting `CF-Connecting-IP`). Say this plainly whenever the
security features come up — don't imply protection that isn't there.

**macOS memory accounting is ambiguous.** psutil's `used` (active+wired) and `total −
available` (which includes ~6 GB compressed) differ by a lot. Use **`total − available`** —
it matches Activity Monitor's "Memory Used". The dashboard hero uses Alex's own formula:
`docker_used + (host_used − docker_alloc)` over total RAM, deliberately de-duplicating
Docker's reserved-but-unused allocation.

**`docker inspect .State.Health` errors** on containers without a healthcheck ("map has no
entry for key Health"). Parse health from the `docker ps` **Status** string instead
(`(healthy)` / `(unhealthy)`).

**Container logs often go to stderr** (Caddy does). `docker logs` writes them to *stderr*,
so a helper that only captures stdout returns empty. Merge the streams.

**Mobile scroll jank** came from three things stacking: a nested `.main` overflow scroller,
a fixed continuously-animating WebGL background, and a sticky header. On phones: scroll the
document naturally, drop the animated veil, un-stick the header.

**launchd's PATH does not include `/usr/local/bin`** — where Docker Desktop
symlinks the `docker` CLI. The dashboard ran for months as a hand-started
process inheriting Alex's shell PATH; the moment it became a launchd job the
API still answered `/api/health` **200** while every Docker call failed with
`docker not found on PATH` — containers, stats, top-load, and backups all
silently empty. The plist therefore sets `EnvironmentVariables → PATH`
explicitly. Health-checking a service is **not** the same as checking it can
still reach Docker; verify a Docker-backed endpoint (`/api/containers`) after
any change to how the dashboard is launched. (Hit and fixed 2026-08-16.)

**Python 3.14** is the system Python and FastAPI/psutil/pydantic wheels *do* install on it.

---

## Standard workflows → [WORKFLOWS.md](WORKFLOWS.md)

Read it when actually doing the task: Caddy config change (backup →
validate against the custom `caddy-ratelimit` image → recreate), add a
subdomain (+ accesslog guard), traffic investigation, DB backup (manual
only), ship a ServerManager change (build → commit → push, automatic).

---

## Working style Alex expects

Verify with real commands before asserting; surface findings even when
inconvenient; flag a tradeoff once, then do what he asked; build tools
into the repo, not throwaway shell; commit and push automatically after
meaningful work.

---

## Standing rules for changing this system

Each of these was paid for on 2026-08-16. They are cheap to follow and were
expensive to learn.

**1. Doctrine must name its mechanism, or say it's hand-run.**
This repo spent a day describing a resolve-and-verify mandate that *nothing
scheduled could execute* — `groom.sh` has no resolution logic, and the mandate
silently assumed a human-started agent session. Doctrine that describes what
"Harah does" without naming the script, the schedule, and the log that does it
is a wish, not a routine. When adding or editing a duty here: name the runner,
or write plainly that it only happens in a hand-run session. Then check the
runner actually exists.

**2. A scheduled job is verified by `launchctl kickstart`, never by hand.**
Running the script yourself proves nothing about the scheduled path — TCC
permissions, `PATH`, working directory and environment all differ. Both harah
routines were declared "live and verified" off manual runs while every real
fire failed with exit 126. **The only acceptable evidence is: kickstart it,
read the exit code, read the log.** Report the exit code you actually saw.

**3. Liveness is not function.** `/api/health` returning 200 said nothing about
whether the dashboard could reach Docker — it couldn't, and the UI showed zero
containers. After any change to how a service starts, exercise an endpoint that
*uses the dependency* (`/api/containers`), not just the one that proves the
process is breathing.

**4. Re-derive from live data; every brief goes stale — including this file.**
Version targets, alert counts, and "the fix is in X" age badly. The resolver's
own standing brief was wrong about two criticals within hours of being written:
a human PR already shipped a better version, and a higher patch on the same
line closed double the alerts. Before acting on any recorded target, re-check
it against the API. Treat numbers here as a starting point, never as truth.

**5. Enumerate human PRs before starting work.** Alex authors PRs too. Check
`gh pr list -R <repo> --state open` in full — not just dependabot's — or you
will duplicate finished work and collide with a branch you are forbidden to
touch.

**6. Merging is NOT deploying — the build is gated on a `publish` commit.**
(Corrected 2026-08-16 from the opposite claim, which was wrong and had been
driving sessions to queue safe work out of an imagined blast radius.) The shared
reusable workflow `lxrbckl-labs/.github/.github/workflows/dockerhub-build-push.yml`
builds only when the head commit message **starts with `publish`** (or is a
`Merge …` commit containing `publish`):

```yaml
if: startsWith(inputs.caller_commit_message, 'publish') ||
    (startsWith(inputs.caller_commit_message, 'Merge ') && contains(inputs.caller_commit_message, 'publish'))
```

So an ordinary merge to `main` reports `skipped`, produces **no image**, and
`watchtower` has nothing new to pull — the live container keeps running.
(Watchtower itself: defined under `~/docker-bare-run/watchtower/` on the
mini; poll interval and per-container scope are NOT yet recorded here —
[MINI-VERIFY 2026-08-22: read its compose/env and record both, so
merge-to-live latency stops being a guess].) Releases
are an explicit act: a commit literally named `publish` (see
`Project-FlyingGitman`'s history, which is a run of them).

Two consequences. **The post-merge deployment check still matters, but its usual
honest answer is "merged, not deployed"** — say that plainly instead of waiting
out a watchtower poll that will never fire. And **shipping is Alex's call**: never
author a `publish` commit unattended to make a merge take effect.

Verify per repo rather than assuming — check the run's conclusion (`skipped` vs
`success`) and the image's build date (`docker image inspect <img> --format
'{{.Created}}'`) against the container's uptime.

**7. Read the doctrine before extending the machinery, not after.** The
on-demand stance in [README.md](README.md) is right for *doing a task*. It is
wrong for *adding to this system*: read SKILL.md, POLICY.md, and
[docs/dev-notes.md](../docs/dev-notes.md) first, or you will rebuild something
that exists, contradict a rule, or miss the gate.

**8. Careful with bulk path edits.** A blanket find/replace across docs
corrupts *historical* statements — it rewrote "moved here from `<old path>`"
into the new path, making the record claim the repo moved from itself. After
any sweep, re-read the sentences that describe history.

---

## Open items → [OPEN-ITEMS.md](OPEN-ITEMS.md)

Mutable status (exposed PATs, missing backup schedule, stale Caddy blocks,
unhealthy container, auto-defense state) — read when planning server work;
keep it current there.

---

