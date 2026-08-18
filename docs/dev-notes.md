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

### CI and deployment across the `lxrbckl-labs` repos (learned 2026-08-16)

- **A merge does not deploy. A `publish` commit deploys.** The shared reusable
  workflow builds only when the head commit message starts with `publish` (see
  SKILL.md standing rule 6 for the exact `if:`). Ordinary merges report
  `skipped` and produce no image. Doctrine previously asserted the opposite;
  it was wrong, and it cost real work — sessions queued safe changes because
  they believed a merge would replace a live container in ~5 minutes.
- **`skipped` ≠ `failure` ≠ "workflow file issue".** Three distinct outcomes
  that all leave the image unchanged, and they mean different things:
  `skipped` = the publish gate said no (healthy); `failure` with a real job
  = the build broke; **`failure` with `jobs: []` and the run `name` showing
  the workflow *path*** rather than its `name:` = GitHub could not resolve the
  workflow at all. Read `jobs.total_count` before drawing a conclusion.
- **`reactive-resume`'s CI is genuinely broken**, and this is the third
  symptom class above. Its workflow calls
  `uses: lxrbckl-dev/.github/...`, and the org `lxrbckl-dev` was renamed to
  `lxrbckl-labs`. **The REST API silently follows the rename redirect —
  `gh api repos/lxrbckl-dev/.github` happily returns `lxrbckl-labs/.github` —
  but GitHub Actions does not.** So the ref looks valid under every check you
  would naturally run, while every real run dies before starting a job.
  `Project-FlyingGitman` and `Project-Jordyn` were fixed on 2026-08-08;
  `reactive-resume` was missed. One-line fix, still open.
- **Always `git fetch` a target repo before branching from local `main`.** On
  2026-08-16 a resolver session branched `Project-FlyingGitman` off a stale
  local `main` (`747bd29`), eight days and four commits behind. It re-did
  dependabot work Alex had already merged, and — because that old commit also
  predated the org-ref fix — its CI run failed with the "workflow file issue"
  signature, which then got mis-attributed to a repo-wide outage. The PR was
  closed and redone against the real `main` for a sixth of the diff. The stale
  base poisoned both the work *and* the diagnosis.

### Verification signals per repo (as of 2026-08-16)

| repo | usable verification | notes |
|---|---|---|
| `reactive-resume` | `pnpm typecheck` (green on `main`) | `pnpm build` is **broken on `main`** — unbounded `h3` override floated to `2.0.1-rc.20`, which dropped the `resolveDotSegments` export `h3-rules` imports. `biome check` has a pre-existing nit. Judge by delta. |
| `Project-FlyingGitman` | `npm ci` + `npm run build` (`tsc`) + `npm audit` | `npm test` is an unimplemented stub that exits 1 on `main`. Not a signal. |
| `Project-Jordyn` | `pnpm install --frozen-lockfile` + `pnpm run build` + `pnpm run lint` — **all green on `main`** | Use **pnpm 10** (10.30.2 verified). See the correction below; the earlier "pnpm 10 rewrites the lockfile" warning was wrong. |
| `Project-ASBC`, `Project-RCoD` | **constructed** — `poetry check --lock` + `poetry lock` delta + `poetry install` + a functional exercise of the changed dependency | No CI, no tests, no container. See the correction below — the earlier "nothing can be merged here" reading was retired 2026-08-18. Poetry now lives at `~/.harah/tools/poetry-venv` (2.4.1 on python3.12). |

**Correction (2026-08-18): "the repo has no verification" is not the same as
"nothing here can ever be merged."** Two sessions in a row read POLICY's *never
merge unverified* gate as requiring a verification signal that already exists in
the repo, and concluded ASBC/RCoD were permanently frozen. That reading freezes a
repo forever for the sin of having no CI — while the *dependabot* no-CI clause
happily merged `cryptography 46 → 50` (a major) there with no signal at all.

The gate is about evidence, not about who authored the test runner. Where a repo
has none, **build one and say exactly what it covers**: for the ASBC torch bump
that was `poetry check --lock` (exit 0, output identical to `main`), a `poetry
lock` delta confined to the intended packages, `poetry install --no-root`
(exit 0), and torch exercised for real — conv2d forward, autograd, MPS,
torchvision transforms, `resnet18`. Where a path *can't* be exercised, measure it
on both sides and report the delta rather than waving it through: ASBC's only
torch call site (`torch.hub.load('ultralytics/yolov5', …)`) fails identically on
2.8.0 and 2.13.0 because `ultralytics` is undeclared — pre-existing, delta zero.

This is a judgment call flagged for Alex on the merge, not a silent widening. If
he wants the stricter reading, PR #18 reverts in one command. **What does not
change: the verification has to actually run, and its output has to be reported.**

### `deploy-check/verify.py` mis-reports on repos with no CI (2026-08-18)

Running it after the ASBC merge printed `== FAIL ==`, citing a CI run with
conclusion `failure`. **That run was a Dependabot updater job**
(`pip in /. for torch - Update`), not a build — `Project-ASBC` has no
`.github` directory at all. On Python repos with no workflows, the only Actions
runs are GitHub's own *Dependabot Updates* and *Dependency Graph* jobs, and the
script reads the newest one as if it were the repo's CI.

Two things follow. **A red Dependabot Updates run usually means "no resolvable
version", not "CI is broken"** — read `latest-resolvable-version` vs
`lowest-non-vulnerable-version` before calling it an outage; it is how a version
wall looks from the updater's side, and it is a useful signal that an alert has
no reachable fix. And **`verify.py`'s FAIL is not evidence about the merge** on
such a repo. Fix worth making: skip runs whose event is `dynamic`, or check for a
workflow file before reporting CI at all. Not done — recorded here so the next
session doesn't misdiagnose it the way the `reactive-resume` org-rename signature
was misdiagnosed as a repo-wide outage.

### When the fix is capped by a first-party package (2026-08-18)

`pytest` alerts in ASBC and RCoD were unclosable in those repos: Alex's own
`lxrbckl` package declared `pytest >=7.4.2,<8.0.0` as a **runtime** dependency,
so every consumer inherited the cap in its runtime lock, and Poetry has no
override mechanism. The fix lives in the *package's* repo, not the consumer's —
`lxRbckl/lxRbckl` PR #1, opened and **left unmerged**, because pushing to that
repo's `PyPI` branch runs `poetry publish` against Alex's token, gated only on
the commit message being exactly `"Update"`. Publishing is his call per release.

General rule: when an alert's advisory has a published fix but the resolver can't
reach it, **trace the cap before declaring it blocked.** A first-party dependency
is a fixable cap; an upstream package with no release (`extract-zip`, latest
2.0.1 vs advisory `<= 2.0.1`) is not.

**Correction (2026-08-16, measured — supersedes the earlier Jordyn row).** The
previous note said Jordyn was pinned to pnpm 9.15.9 by PR #13 and that local
pnpm 10.x "rewrites the lockfile format and guarantees a conflict." Both halves
are wrong now:

- **pnpm 10.30.2 installs Jordyn from the committed lockfile with
  `--frozen-lockfile` and leaves `pnpm-lock.yaml` byte-identical.** No format
  rewrite. The lockfile is already `lockfileVersion: '9.0'`, which pnpm 10
  reads and writes natively.
- **pnpm 9.15.9 can no longer install the repo at all.** `main` gained a
  `pnpm-workspace.yaml` (`fca7b44`) declaring `allowBuilds:` with no
  `packages:` key; pnpm 9 reads the file's presence as a workspace declaration
  and dies with `ERROR packages field missing or empty` before installing.
  So PR #13, which pins the Dockerfile to `pnpm@9.15.9`, **would break the
  Docker build** as written — flagged in a signed comment on #13. Appending
  `packages: []` fixes it and is a no-op for pnpm 10 (both verified).

The general lesson is standing rule 4 again: this table is a snapshot, and a
repo's `main` moves underneath it. Re-measure before trusting a row.

**Lockfile work collides with human PRs — check first, and own it if you
collide.** Merging Jordyn #17 (transitive `pnpm.overrides`) flipped Alex's #16
from MERGEABLE to CONFLICTING. That was a foreseeable cost of touching
`pnpm-lock.yaml` while a dependency PR was in flight. It was survivable —
`package.json` still merged cleanly, only the lockfile conflicted, and a
local test-merge confirmed #16 + #17 build green together — but **run
`gh pr list` for lockfile overlap before merging dependency work, and if you
do cause a conflict, say so on the affected PR with the resolution recipe
rather than leaving it to be discovered.**

## Conventions

Ship a change = build if the frontend changed → `git add -A && git commit &&
git push`, **automatically, without being asked**. Outward-facing writes (PR and
issue comments, non-merge commits) are signed `— Harah`.
