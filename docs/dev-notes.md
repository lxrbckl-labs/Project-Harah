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
- **`reactive-resume`'s CI was genuinely broken**, and this is the third
  symptom class above. Its workflow calls
  `uses: lxrbckl-dev/.github/...`, and the org `lxrbckl-dev` was renamed to
  `lxrbckl-labs`. **The REST API silently follows the rename redirect —
  `gh api repos/lxrbckl-dev/.github` happily returns `lxrbckl-labs/.github` —
  but GitHub Actions does not.** So the ref looks valid under every check you
  would naturally run, while every real run dies before starting a job.
  `Project-FlyingGitman` and `Project-Jordyn` were fixed on 2026-08-08;
  `reactive-resume` was missed.
  **FIXED 2026-08-18** — PR #19 merged as `7b35f4c6`. Verified on `main`, not
  just on the branch:

  | | before (`41e02945`) | after (`7b35f4c6`) |
  |---|---|---|
  | run `name` | `.github/workflows/dockerhub-build-push.yml` (the *path* → unresolved) | `dockerhub-build-push` (the workflow's `name:` → resolved) |
  | `jobs.total_count` | 0 | 1 |
  | conclusion | `failure` | `skipped` (publish gate — healthy) |

  All three `lxrbckl-labs` callers now point at `lxrbckl-labs/.github`. The
  run `name` is the cheapest tell for this class: **GitHub falls back to the
  workflow's file path when it cannot resolve the workflow**, so a run named
  after a path is the signature, and one named after the `name:` key is proof
  of resolution.
- **Always `git fetch` a target repo before branching from local `main`.** On
  2026-08-16 a resolver session branched `Project-FlyingGitman` off a stale
  local `main` (`747bd29`), eight days and four commits behind. It re-did
  dependabot work Alex had already merged, and — because that old commit also
  predated the org-ref fix — its CI run failed with the "workflow file issue"
  signature, which then got mis-attributed to a repo-wide outage. The PR was
  closed and redone against the real `main` for a sixth of the diff. The stale
  base poisoned both the work *and* the diagnosis.

### Telling Harah's own PRs from Alex's (2026-08-18) — the `— Harah` body signature

**Neither the PR author nor the commit identity can distinguish them.** Harah
runs on Alex's `gh` credentials, so every PR it opens is authored `lxRbckl`, and
its commits are authored **`ala2q6 <lxrbckl@protonmail.com>`** — Alex's *school*
account identity, on a labs repo, from the mini. Branch prefixes don't settle it
either: Harah uses `security/…`, but so does Alex.

**The reliable discriminator is the `— Harah` signature in the PR body**, which
the signature rule in POLICY requires on every outward artifact:

```bash
gh pr view <n> --repo <owner/repo> --json body --jq '.body' > /tmp/b.txt
grep -c 'Harah' /tmp/b.txt          # grep the ASCII name, NOT the em-dash form
```

Measured 2026-08-18: `reactive-resume` #19 → 1 (Harah's), `Project-ASBC` #18 →
1 (Harah's, known-good control); `reactive-resume` #15 → 0, `Project-Jordyn`
#16 → 0, `Project-Jordyn` #13 → 0 (all Alex's). Re-measured 2026-08-18 (later
session), unchanged, plus `reactive-resume` #9/#4 → 0 and `lxRbckl/lxRbckl`
#1 → 1. Run the control too — an empty body silently greps to 0 and looks
like "human".

**Grep the ASCII `Harah`, never the `— Harah` em-dash form (2026-08-18).** The
signature really is U+2014 (`342 200 224 ' ' H a r a h`), but putting that
literal in a shell one-liner is fragile: run inside a `for … set -- $p` loop it
came back **0 for every PR in the batch — including the known-good control**.
The em-dash is the only non-ASCII byte in the whole check, and it is the byte
most likely to be mangled by a shell/locale/quoting path. `grep -c 'Harah'` is
exactly as discriminating (Alex's PR bodies don't say "Harah") and has no
non-ASCII failure mode.

Two guards, because this check gates a hard stop in *both* directions:
- **Always run the control in the same batch** (`Project-ASBC` #18 → 1). A
  control that reads 0 means the *check* is broken, not that the PR is human.
  The batch above would otherwise have labelled Harah's own #1 "Alex's".
- **Read `body_bytes` alongside the count.** 0 bytes = the fetch failed (bad
  `--repo`, unsplit loop variable); it is not evidence of authorship. Both
  failure modes look identical to "human" — which is the reading that stalled
  #19 for two days.

This cuts **both** ways, and both are expensive:

- **False "human" → work stalls.** #19 was Harah's own one-line CI fix, green
  and `MERGEABLE`, and it sat open from 2026-08-16 to 2026-08-18 across
  sessions that read author `lxRbckl` as hands-off. It was the *gate* on all
  verification in the repo holding both org criticals.
- **False "mine" → a hard stop gets crossed.** #15/#16 read exactly like
  Harah's own reports (same structure, same tables, same voice) and are stale
  and conflicting — precisely the thing a session itches to rebase. They are
  Alex's.

Style is not evidence: Alex's agent sessions on other machines produce the same
prose. Check the signature.

### Bringing a stale Harah branch current: merge, never rebase (2026-08-18)

Force-push is a hard stop, so the usual "rebase onto fresh `origin/main`" is
unavailable for a branch already pushed. **Merge `origin/main` into the branch
instead** — it rewrites no history, needs no force, and re-triggers CI against
the tree the PR will actually land in. Confirm with
`gh api repos/<r>/compare/main...<branch> --jq '.behind_by, [.files[].filename]'`:
want `behind_by=0` and a file list still confined to the intended change. Used
on #19, whose prior green run predated `main` by 3 commits.

The doctrine's "branch off freshly-fetched `origin/main`" still governs *new*
branches; this is the repair move for one that already exists.

### Verification signals per repo (as of 2026-08-16)

| repo | usable verification | notes |
|---|---|---|
| `reactive-resume` | `pnpm typecheck` (green on `main`) | `pnpm build` is **broken on `main`** — unbounded `h3` override floated to `2.0.1-rc.20`, which dropped the `resolveDotSegments` export `h3-rules` imports. `biome check` has a pre-existing nit. Judge by delta. **CI resolves again as of 2026-08-18** (#19) — it reports `skipped` on ordinary commits, so it is a publish-gate signal, not a build signal. |
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
such a repo.

**FIXED 2026-08-19** — PR #5. `verify.py` now pulls 20 runs instead of 1 and
picks the newest whose `event` is **not** `dynamic`; when every run is dynamic it
prints *"no CI signal here, green or red"* rather than a conclusion, and reports
the failed-dynamic-run count as **a fact about an alert, not about a merge**.
Measured before/after on all seven targets: ASBC went from `CI success` (it was
quoting a *Graph Update* job) and RCoD from `CI running (null)` to the honest
no-CI line, and the four repos that already read correctly are **byte-identical**
to `main` (diffed by stashing the patch and re-running).

Two things learned doing it. **`actions/workflows` `total_count` is not a
"has CI" test** — it returned **2** for `Project-ASBC`, which has no `.github/`
directory at all, because GitHub counts its synthesised
`dynamic/dependabot/{dependabot-updates,update-graph}` workflows. The reliable
discriminator is the run's `event` (or its `path` prefix), not the workflow
count. And the closing *"PASS with a skipped CI run"* note used to print on
every pass, including repos where nothing was skipped and nothing is deployed;
it is now conditional on the publish gate actually having fired.

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
is a fixable cap; an upstream package with no release is not.

**The `extract-zip` example used here was WRONG — see the 2026-08-19 correction
at the end of this file.** The rule itself stands; it was applied one level too
shallow. "No published fix for the package" is not the same as "no fix for the
alert", because a *transitive* package can be removed by moving its parent.

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

### The board as of 2026-08-18: all 66 open alerts are blocked, and on what

Re-derive before trusting this (standing rule 4) — but the *shape* is the point:
by this date the board had stopped being a remediation problem and become a
queue of decisions only Alex can make. All 66 reduce to **6 distinct advisories
× 2 manifests** (`package.json` + `pnpm-lock.yaml` each raise their own alert, so
raw counts read double) across four causes:

| alerts | what | blocked on |
|---|---|---|
| 42 | `Project-Jordyn` `next` — needs **15.5.21**, a major | Alex's #16 (complete migration: next 15 + React 19 + eslint-config lockstep + `tsconfig`). Dependabot #11 is `MERGEABLE` and **verified green**, but partial — `react` stays 18.3.1 — and a prior session left Alex an explicit open question on it ("say the word and I'll land this"). Unanswered ≠ authorized. |
| 20 | `reactive-resume` `better-auth` — needs **1.6.22+** | Alex's #15 lands **1.6.26**, closing all 20. `CONFLICTING/DIRTY` on its own lockfile, not from anything Harah merged. |
| 1 | `reactive-resume` `drizzle-orm` — needs `0.45.2` or `1.0.0-beta.20` | also Alex's #15 (→ `1.0.0-rc.4`). The dependabot alternative #4 is a prerelease→prerelease bump, which POLICY disqualifies outright. |
| 1 | `reactive-resume` `extract-zip` | ~~**no published fix exists** — advisory covers `<= 2.0.1` and npm `latest` *is* 2.0.1. Nothing to override to; not a version wall, a dead end.~~ **WRONG — RESOLVED 2026-08-19 by PR #21** (bump the transitive parent). See the correction at the end of this file. |
| 2 | `pytest` in `Project-ASBC` + `Project-RCoD` | first-party cap (see above) — needs `lxRbckl/lxRbckl` PR #1 merged **and published**, and publish is Alex's call per release. Merging #1 alone closes nothing, since consumers resolve from PyPI. |

**"Behind a human PR" is a real blocked state, not a cop-out** — but only after
you have checked the signature, because the same finding with the authorship
wrong is either a stalled fix or a crossed hard stop. The honest status here is
`EXHAUSTED`, and a session that closes zero alerts while saying so plainly is
worth more than one that banks 42 by overriding a pending question.

**Re-derived 2026-08-18 (resolver loop, session 1) — all five rows still hold**,
totals byte-identical (2 critical / 32 high / 26 medium / 6 low = 66). What was
re-measured from live data rather than carried over:

- `extract-zip` ~~is a **dead end**~~ — **this bullet is SUPERSEDED; see the
  2026-08-19 correction at the end of this file.** Every fact in it was right
  (npm `latest` is 2.0.1, the advisory covers `<= 2.0.1`, last published
  2020-06-10) and the conclusion drawn from them was wrong. The clause **"no
  reason to re-check it every run"** is the dangerous part: it told later
  sessions to stop looking at a high-severity alert that was fixable the whole
  time. Closed 2026-08-19 by PR #21.
- The `pytest` cap is **confirmed on PyPI, not just in the repo**: published
  `lxrbckl` **3.6.0** ships `pytest<8.0.0,>=7.4.2` as a *runtime* requirement.
  Neither consumer declares `pytest` directly (ASBC: `lxrbckl = "^3.5.0"`;
  RCoD: `lxrbckl = "^3.6.0"`), so both inherit it and the alert needs `>=9.0.3`.
  Unsatisfiable by any change to the consumer repos.
- `lxRbckl/lxRbckl` **#1 targets the `PyPI` branch, not `main`** — so merging it
  *is* the publish, not a step before it. That is why it stays open: it needs
  Alex's word as a release, and no amount of verification substitutes.
- Jordyn dependabot **#11**'s open question to Alex (2026-08-17T13:43Z) is still
  **unanswered** — its last comment is Harah's own. Unanswered ≠ authorized.

**Re-derived again 2026-08-18 (later resolver session) — unchanged, and now
measured at the upstream sources rather than in the repos:** totals still
2 critical / 32 high / 26 medium / 6 low = 66 across the same five rows.
`better-auth` npm `latest` is **1.7.1** while `reactive-resume` `main` still
declares `1.5.0-beta.9`, so the 20 alerts need a **beta→stable migration with
DB schema changes** — precisely the shape POLICY says to queue, on a
Postgres-backed service where the only usable signal (`pnpm typecheck`) cannot
show that auth still works. `drizzle-orm` `main` is `^1.0.0-beta.12-a5629fb`:
the stable fix `0.45.2` is a cross-line *downgrade* and `1.0.0-beta.20` is
prerelease→prerelease, which POLICY disqualifies. Jordyn #11's open question to
Alex (2026-08-17T13:43Z) is **still unanswered** — last comment on the thread is
Harah's own. A sweep of every non-archived org repo found open dependabot PRs in
exactly two repos (`reactive-resume` 2, `Project-Jordyn` 1), and all four
personal `lxRbckl` repos report **0 open alerts**. Nothing new is actionable.

**`Project-ACLG` is ARCHIVED — its 2 open dependabot PRs are permanently out of
scope (2026-08-18).** A sweep for open dependabot PRs across the org turns it up
(#15 setuptools 82→83, #5 pytest 7.4.4→9.0.3, both `MERGEABLE`), which reads as
actionable until you check the repo state. POLICY's first condition is "not
archived", and GitHub refuses writes to an archived repo anyway; its alerts
endpoint returns **403 "Dependabot alerts are not available for archived
repositories"**, so it contributes nothing to the alert count either. Don't
re-investigate it — and note the 403 is *not* a permissions problem, despite
`gh` helpfully suggesting an `admin:repo_hook` scope refresh underneath it.

### The Docker Hub publish credential is DEAD — every org publish fails (2026-08-18)

Found by running `deploy-check/verify.py` after re-deriving the board, not by
looking for it. **`Project-Jordyn`'s most recent CI run is a genuine build
failure**, and the cause is not code:

```
##[error]Error response from daemon: Get "https://registry-1.docker.io/v2/":
unauthorized: incorrect username or password
```

Run `32082150509`, head commit `publish: next 14.2.35 + 29 transitive security
fixes`, 2026-08-17T23:50, failed in 25s at `docker/login-action` — **before the
build step ran at all**. So the publish Alex attempted last night did not ship,
and Jordyn's 29 transitive security fixes are still not in production.

**This is org-wide, not a Jordyn problem.** `DOCKERHUB_USERNAME` /
`DOCKERHUB_TOKEN` are **organization** secrets on `lxrbckl-labs` with
`visibility: all` — one credential pair behind every repo's publish:

| | |
|---|---|
| secrets created / last updated | **2025-10-18** (never rotated) |
| last *successful* publish | `Project-Jordyn` **2026-08-08T05:01** |
| first failure with this signature | `Project-Jordyn` **2026-08-17T23:50** |

The GitHub-side secret has not changed since 2025-10-18, so what changed is on
**Docker Hub's side** — an expired or revoked PAT is the obvious candidate
(Docker Hub PATs support expiry, and this one is ~10 months old). Breakage
window: between 2026-08-08 and 2026-08-17.

Honest caveat: **one failed run cannot fully exclude a transient Docker Hub
auth blip.** The cheap discriminator is to re-run the failed job — but
**Harah must not do that**, because if the credential *does* work the job
builds and pushes an image, which is a deploy, and deploying needs Alex's word
per deploy. Diagnosis stops at the door; the fix is Alex's.

Consequences worth stating plainly:

- **Every remaining alert on the board is now double-blocked.** Even when Alex
  answers the Jordyn question and lands the 42-alert `next` migration, or lands
  `reactive-resume` #15 for the 20 `better-auth` alerts, **none of it can reach
  production** until this credential is restored. POLICY already says alerts
  closed on GitHub are not fixes in production until the image rolls; this is
  that sentence with teeth.
- **`skipped` is still healthy; this is the fourth outcome class.** Added to the
  three already recorded above: `skipped` = publish gate said no; `failure` with
  a real job = the build broke; `failure` with `jobs: []` = workflow unresolvable
  (the org-rename signature); and now **`failure` at the login step = the
  registry credential is rejected.** Read *where* in the job it died before
  calling it a build break — this one never reached the build.
- Don't misread `reactive-resume`'s 2026-08-16/17 failures as the same thing.
  Those predate #19 and are the `jobs: []` org-rename class. This repo has not
  attempted a publish since its CI started resolving.

## Conventions

Ship a change = build if the frontend changed → `git add -A && git commit &&
git push`, **automatically, without being asked**. Outward-facing writes (PR and
issue comments, non-merge commits) are signed `— Harah`.

### Re-derived 2026-08-19 (resolver loop, session 1) — board unchanged at 66

Totals identical again: **2 critical / 32 high / 26 medium / 6 low = 66**, same
five rows, same four repos (`reactive-resume` 22, `Project-Jordyn` 42,
`Project-ASBC` 1, `Project-RCoD` 1). All four personal `lxRbckl` repos still
report **0**. An all-org GraphQL sweep of open PRs on non-archived repos returns
exactly eight, and no new dependabot PR has appeared since 2026-08-18.

Re-measured at the source rather than carried over:

- **Every alert's `first_patched_version` pulled from the alerts API**, not from
  the notes. It confirms the rows and corrects one: the `drizzle-orm` alert has a
  **single** advisory, `>= 1.0.0-beta.2, < 1.0.0-beta.20`, first patched at
  **`1.0.0-beta.20`** only. The recorded "needs `0.45.2` or `1.0.0-beta.20`"
  overstates the options — there is no stable-line fix to take, so the row is
  *more* blocked than written, not less. Prerelease→prerelease; POLICY
  disqualifies it outright.
- **`lxrbckl` on PyPI is still 3.6.0, uploaded 2024-11-18**, still declaring
  `pytest<8.0.0,>=7.4.2` as a *runtime* requirement. No newer release exists for
  ASBC/RCoD to bump to, so the 2 `pytest` alerts remain unsatisfiable by any
  change to the consumer repos.
- **The Docker Hub credential is still dead.** No publish has been attempted
  anywhere in the org since run `32082150509` (2026-08-17T23:50), so the
  diagnosis stands untested — deliberately, since re-running that job would be a
  deploy. `verify.py` now names the failing step (`Log in to DockerHub`) instead
  of calling it a broken build.
- **Days behind `main`, measured today:** Project-Jordyn **9**, reactive-resume
  **45**, Project-FlyingGitman **43**, Project-VoiceToColumn **35**,
  Project-Showalter **35** (still `unhealthy`, still pre-existing). Every one is
  serving HTTP 200 on an image built 2026-07-03 or 2026-08-08.

`Project-Jordyn` **#11**'s question to Alex (2026-08-17T13:43Z) is **still
unanswered** — the last two comments on the thread are both Harah's own. It stays
queued. The temptation here is real and worth naming: #11 is dependabot-authored,
`MERGEABLE`, verified green, and closes 42 of the 66 alerts on the board, so
POLICY's resolve-and-verify clause would license merging it. It is held anyway,
because Harah itself wrote *"say the word and I'll land this"* on that thread.
A session that answers its own open question to Alex has not resolved anything —
it has removed him from a decision he was asked to make.

### The "no published fix" dead end that wasn't: trace a transitive to its parent (2026-08-19)

`reactive-resume` alert **#209** — `extract-zip` (GHSA-jmr9-qjv8-65gv, **high**,
unvalidated symlink path traversal) — sat on the board as *unfixable* across
several sessions, and the notes above told future sessions **not to re-check
it**. It was fixable, and it is now closed (PR #21, merged `8c368d86`,
`fixed_at` 2026-08-19T16:29:20Z). Board 66 → 65.

Every fact behind the "dead end" reading was correct:

| | |
|---|---|
| advisory range | `<= 2.0.1` |
| npm `latest` | **2.0.1** |
| last published | 2020-06-10 |
| `first_patched_version` from the alerts API | **`null`** |

And the conclusion — *nothing to override to* — was still wrong, because the
question was asked about the wrong package. `extract-zip` is **not a direct
dependency**. The alert's `manifest_path` is `pnpm-lock.yaml` only (no
`package.json` twin), which is the tell: a transitive.

```
puppeteer-core@24.36.0 -> @puppeteer/browsers@2.11.1 -> extract-zip@2.0.1
```

**`@puppeteer/browsers` deleted the `extract-zip` dependency in 3.0.2**
(2026-05-15, when it moved to `modern-tar`). Measured across the whole range at
the registry: every 2.x release through the last one (2.13.2) still declares
`extract-zip: ^2.0.1`, so there is **no fix inside the 2.x line** — the parent
bump has to cross a major. `puppeteer-core` picks up the 3.x line from **25.0.2**
onward. Bumping `puppeteer-core` 24.36.0 → 25.8.0 removes the package from the
tree instead of pinning it to a version that does not exist. Net lockfile
effect: **−39 / +13** packages (the `proxy-agent`/`pac-*` and `bare-*` subtrees
leave with it).

**The rule, stated so it can't be applied too shallow again:**

> `first_patched_version: null` means *this package* has no fixed release. It
> says nothing about whether *the alert* is fixable. Before writing off any
> alert whose manifest is a lockfile and not a manifest file, find the parent
> that pulls it in and check whether a newer parent dropped the dependency
> outright. Removing a package closes its alert exactly as well as patching it.

Cheap procedure, ~2 minutes:

```bash
# 1. is it transitive? lockfile-only manifest_path is the tell
gh api "/repos/<owner>/<repo>/dependabot/alerts/<n>" \
  --jq '{pkg:.dependency.package.name, manifest:.dependency.manifest_path,
         patched:.security_vulnerability.first_patched_version}'
# 2. who pulls it in
grep -n "<pkg>" pnpm-lock.yaml     # read the parent's dependency block
# 3. did a newer parent drop it? (npm registry, no auth)
curl -s https://registry.npmjs.org/<parent> | python3 -c "
import json,sys; d=json.load(sys.stdin)
for v,m in d['versions'].items():
    print(v, m.get('dependencies',{}).get('<pkg>'))"
```

**Verifying a major bump of a runtime dep when the repo's only signal is
`tsc`.** `pnpm typecheck` cannot show that a CDP client still drives a browser,
and `pnpm build` is broken on `main` (the `h3` override drift — delta zero, both
sides fail identically). So the call sites were **replayed for real**:
`puppeteer-core` has exactly one consumer here,
`src/integrations/orpc/services/printer.ts`, and its nine calls — `connect`,
`browser.setCookie`, `newPage`, `setViewport`, `goto(networkidle0)`,
`waitForFunction`, `evaluate` (3 args), `pdf({tagged,width,height,margin})`,
`disconnect` — were run against a real Chrome 151.0.7922.138 over `browserURL`
on 25.8.0, producing a valid 18,561-byte `%PDF-`. Two reusable moves in that:

- **Put the throwaway harness in `node_modules/`.** A script under `/tmp`
  cannot resolve the repo's packages (Node resolves from the *script's* path,
  not `cwd` — `ERR_MODULE_NOT_FOUND`). `node_modules/` is gitignored, inside the
  package root, and resolves everything. Delete it before `git add`.
- **Read the release notes as a checklist against actual call sites**, not as
  prose. puppeteer-core 25.0.0's breaking changes were ESM-only (repo is already
  `"type": "module"`), min Node 22 (`Dockerfile` is `node:24-slim`), min TS 5.0.1,
  and five removed APIs (`Puppeteer.product`, `Browser.isConnected`,
  `MouseOptions.clickCount`, cookie `sameParty`, Promise-returning
  `executablePath`/`defaultArgs`) — **none of which this repo calls.** A major
  whose every breaking change misses your call sites is a low-risk major, and
  saying which ones you checked is what makes that claim reviewable.

**And the meta-lesson, which is the expensive one.** These notes are supposed to
stop a session rediscovering things the hard way. A note that records a *wrong*
conclusion with confident measurements attached does the opposite: it stops the
session looking at all. The phrase that did the damage was **"no reason to
re-check it every run."** Prefer recording *what was measured and what question
was asked* over the verdict — "checked the registry for a fixed `extract-zip`;
none exists" is durable and invites the next question. "Dead end, don't look
again" is a lock on a door that was open. Standing rule 4 cuts both ways: this
file goes stale about its own blockers, not just about version targets.

Also worth noting: **`main` still shipped nothing.** CI reported `skipped`
(publish gate) as designed, and `deploy-check/verify.py` puts the running
`reactive-resume` image at **46 days behind `main`**, serving HTTP 200 on an
image built 2026-07-03. Alert closed on GitHub ≠ fixed in production.

— Harah

### Re-derived 2026-08-19 (resolver loop, later session) — 65 open, zero closable

Board after PR #21: **2 critical / 31 high / 26 medium / 6 low = 65**, across
`reactive-resume` 21, `Project-Jordyn` 42, `Project-ASBC` 1, `Project-RCoD` 1.
All four personal `lxRbckl` repos still report **0**. An org-wide GraphQL sweep
of open PRs on non-archived repos returns nine, only three of them dependabot's
(`reactive-resume` #4/#9, `Project-Jordyn` #11) and all three superseded by a
human PR. **Nothing was merged this session, and nothing should have been.**

The authorship check was re-run with its control in the same batch, because it
gates a hard stop: `reactive-resume` #21 → 1 and `Project-ASBC` #18 → 1 (Harah's,
control healthy); `reactive-resume` #15 → 0, `Project-Jordyn` #16 → 0, #13 → 0,
#11 → 0 (Alex's / dependabot's). Bodies 2.9–4.4 KB, so no silent empty-fetch.

Three blockers were re-derived from upstream sources rather than carried over,
and two of them were recorded here for the wrong reason:

- **`Project-Jordyn` — no 14.x backport exists, now measured.** All 21 distinct
  `next` advisories behind the 42 alerts were expanded with
  `gh api /advisories/<GHSA>`. Every one pairs a 15.5.x range with a 16.2.x
  range (`>= 13.0.0, < 15.5.21 -> 15.5.21` and `>= 16.0.0, < 16.2.11 ->
  16.2.11`); **not one carries a `< 14.2.x` range**, so nothing in the 14 line
  was ever patched. 15.5.21 is a hard floor and the major is unavoidable. The
  alerts API alone cannot answer this — it returns only the vulnerability
  matching the installed version, which cannot distinguish "no backport exists"
  from "the backport is in a line you aren't on."
- **`reactive-resume` `drizzle-orm` — the previous entry was wrong about why.**
  The 2026-08-19 note above says GHSA-gpj5-g38j-94v9 has a *single* range with
  no stable-line fix. The advisory has **two**: `< 0.45.2 -> 0.45.2` and
  `>= 1.0.0-beta.2, < 1.0.0-beta.20 -> 1.0.0-beta.20`. A non-vulnerable stable
  version does exist; it is simply *backwards*, a cross-major downgrade of a
  live app's database layer. The row is still blocked — the only forward fix is
  a nightly build in the `1.0.0` channel, coupled to Alex's #15 — but "no stable
  fix exists" and "the fix is in a direction we can't go" are different facts,
  and only the second one is true. **Read the advisory, not just the alert.**
- **The `pytest` cap is total across the reachable range.** Prior passes read
  `lxrbckl` 3.6.0 only. All eight releases the consumers' constraints can reach
  (3.5.0 → 3.6.0) declare `pytest<8.0.0,>=7.4.2` in `requires_dist`, so there is
  no older version to retreat to either. `lxrbckl` is also genuinely imported in
  both consumers (`backend/bot.py`, `backend/module.py`, `frontend/layout.py`;
  `main.py`), so dropping the dependency to shed its transitive pytest is not
  available. PyPI still serves 3.6.0 from 2024-11-18.

`Project-Jordyn` **#11**'s question to Alex (2026-08-17T13:43Z) is **still
unanswered** — the thread's last comments remain Harah's own. Held again, for
the reason already recorded: a session that answers its own open question to
Alex has not resolved anything.

**Deployment, measured today** (`deploy-check/verify.py`, both targets):
`reactive-resume` CI `skipped` on `8c368d86` — the publish gate, working as
designed, **no image built** — both tenants `Up 18 hours (healthy)`, HTTP 200,
running an image from 2026-07-03: **46 days behind `main`**. `Project-Jordyn`'s
newest run is still the 2026-08-17 `publish` that died in `Log in to DockerHub`;
container up, `jbarger.app` HTTP 200 on an image from 2026-08-08: **9 days behind
`main`**. **The org Docker Hub credential is still dead** — no publish has been
attempted anywhere in the org since, deliberately, since re-running that job
would itself be a deploy.

**What a zero-merge session is worth.** The whole board is now decisions only
Alex can make: answer #11 (or land #16), land #15 behind a DB backup and the
`ApiKey.userId → referenceId` migration, publish `lxrbckl 3.6.1`, and restore
the Docker Hub credential — after which 42, 21 and 2 alerts fall in that order,
and the images can finally roll. The useful output of a session like this is
**sharper blockers, not a smaller number**: two of the four rows above were
blocked for reasons that were subtly wrong, and a wrong reason is exactly what
sends the next session down the `extract-zip` path — confident, measured, and
looking at the wrong package.

### Re-derived 2026-08-20 (resolver loop, session 1) — 65 open, zero closable, and the human PRs have not moved in 12 days

Board byte-identical to yesterday: **2 critical / 31 high / 26 medium / 6 low =
65**, across `reactive-resume` 21, `Project-Jordyn` 42, `Project-ASBC` 1,
`Project-RCoD` 1. All four personal `lxRbckl` repos still report **0**. An
org-wide GraphQL sweep of open PRs on non-archived repos returns **seven**, three
of them dependabot's (`Project-Jordyn` #11, `reactive-resume` #4/#9) and all
three superseded by a human PR. **Nothing merged this session, and nothing
should have been.**

Authorship re-checked with the control in the same batch: `Project-ASBC` #18 → 1
and `reactive-resume` #21 → 1 (Harah's, control healthy); `Project-Jordyn`
#13/#16 → 0 and `reactive-resume` #15 → 0 (Alex's). Bodies 2.8–4.4 KB, so no
silent empty-fetch. **The `for … set -- $p` loop failed again** — in **zsh**
`$p` does not word-split, so every `gh pr view` got an empty argument and
errored. That is the same failure the notes already record for the em-dash, with
a different cause: write the checks as explicit calls or a shell function taking
`"$1" "$2"`, never a split-a-string loop.

**The one new fact, and it is about trend, not about a version.** Alex's #15 and
#16 — which between them own **63 of the 65** — have had **no new commits since
2026-08-08**, now 12 days, and both are `CONFLICTING`. `Project-Jordyn` #11's
question to Alex (2026-08-17T13:43Z) has **zero non-Harah comments in its entire
history**; the thread is three Harah comments and nothing else. The board is not
slowly resolving in the background. It is parked, and every session that reports
`EXHAUSTED` is reporting the same parked board.

#### Method: the alert already gives you the forward floor; the advisory tells you about backwards

Both this file and the Jordyn vault note say *"the alerts API alone cannot answer
[whether a backport exists] — it returns only the vulnerability matching the
installed version."* That is true as stated and **operationally misleading**, and
the two notes it produced (expand all 21 advisories for `next`; read the advisory
for `drizzle-orm`) reached opposite-sounding conclusions for the same reason.
Reconciled, measured today:

An alert's matched `security_vulnerability` is the vulnerable range **containing
the version you have installed**, and its `first_patched_version` is therefore
the **minimum version you must reach to leave that range** — which is exactly the
forward-fix floor. Verified on the two ends of the Jordyn set:

| GHSA | range containing 14.2.35 | alert's `first_patched_version` |
|---|---|---|
| `GHSA-h25m-26qc-wcjf` | `>= 13.0.0, < 15.0.8` | `15.0.8` |
| `GHSA-89xv-2m56-2m9x` | `>= 14.1.1, < 15.5.21` | `15.5.21` |

A 14.x backport would have shown up as a *narrower range containing 14.2.35*
(`>= 14.0.0, < 14.2.36 -> 14.2.36`), so the alert would have said `14.2.36`. It
said 15.x for all 21. **The alerts API did answer the question** — expanding all
21 advisories confirmed the floor but was belt-and-braces, not the only route.

What the advisory genuinely adds is the **other direction**: the full range list
is the only way to see a non-vulnerable version *below* your line. That is the
`drizzle-orm` case exactly — `< 0.45.2 -> 0.45.2` is invisible from an alert
matched on the `1.0.0-beta` range, and it is what turns "no fix exists" into "the
fix is a cross-major downgrade of a live app's database layer." So:

> **Forward floor → read the alert. Backwards escape → read the advisory.**
> `first_patched_version` on the alert is authoritative for "how far up must I
> go"; only the advisory's full range list can tell you whether a lower,
> non-vulnerable line exists — and whether that is a direction you can actually
> travel.

Re-confirmed unchanged at the source rather than carried over: `drizzle-orm` is a
**direct** dependency (`"drizzle-orm": "^1.0.0-beta.12-a5629fb"` in
`package.json`) — its lockfile-only `manifest_path` is GitHub failing to match a
nightly specifier, **not** the transitive tell that `extract-zip` was, so the
parent-bump move does not apply here. `lxrbckl` on PyPI is still **3.6.0**
(uploaded 2024-11-18), still declaring `pytest<8.0.0,>=7.4.2` as a runtime
requirement, so the two `pytest` alerts remain unsatisfiable from the consumers.

**Deployment, measured today** (`deploy-check/verify.py`): `Project-Jordyn`'s
newest run is still the 2026-08-17 `publish` that died in `Log in to DockerHub`;
container `Up 31 hours`, `jbarger.app` HTTP 200 on an image from 2026-08-08 —
**9 days behind `main`**. `reactive-resume` CI `skipped` on `8c368d86` (publish
gate, healthy, no image built); both tenants `Up 31 hours (healthy)`, HTTP 200 on
an image from 2026-07-03 — **46 days behind `main`**. **The org Docker Hub
credential is still dead**; no publish has been attempted anywhere in the org
since, deliberately, because re-running that job is itself a deploy.

— Harah

### 2026-08-20 (resolver loop, later session) — the `pytest` row, finally measured in both directions

Board re-derived live and byte-identical for the third consecutive day: **2
critical / 31 high / 26 medium / 6 low = 65**, across `reactive-resume` 21,
`Project-Jordyn` 42, `Project-ASBC` 1, `Project-RCoD` 1. All four personal
`lxRbckl` repos re-checked individually (not from the state file) → **0 each**.
Org-wide open PRs: seven, three of them dependabot's, all three superseded by a
human PR. Authorship re-checked with the control in the same batch — `ASBC` #18
and `reactive-resume` #21 → 1 (control healthy); `Jordyn` #11/#13/#16 and
`reactive-resume` #4/#9/#15 → 0. Bodies 2.9–16 KB, no silent empty-fetch.
**Nothing merged, and nothing should have been.**

**The new fact: the `pytest` cap is total, not merely upward.** Every prior pass
measured this row in one direction only — `lxrbckl` caps `pytest` at `<8.0.0`,
the alert wants `>=9.0.3`, therefore blocked. Nobody had applied this file's own
*"backwards escape → read the advisory"* rule to it. Applied now:
**GHSA-6w46-j5rx-g56g has exactly one vulnerable range, `< 9.0.3 -> 9.0.3`.**

That forecloses the question the rule exists to ask. There is no lower
non-vulnerable line, so pinning `pytest` to some safe `7.4.x` *inside* the
first-party cap — the obvious next idea, and the one a future session would burn
time on — cannot work: every version the consumers can reach is vulnerable by
construction. The row needs `lxrbckl` **published** at `>=9.0.3`, or nothing.
`lxrbckl` on PyPI is still **3.6.0** (2024-11-18), still declaring
`pytest<8.0.0,>=7.4.2` in `requires_dist`, re-checked at the registry today.

With that, the "backwards escape" rule has now been applied to all four rows and
each has a recorded answer: `next` — no lower line, 14.2.35 is the top of the 14
line (measured 2026-08-19); `better-auth` — n/a, the floor is forward and the
migration is the blocker; `drizzle-orm` — a lower line exists (`0.45.2`) but it
is a cross-major downgrade of a live app's database layer; `pytest` — no lower
line exists at all. **No row has an unexamined direction left.**

**Trend, which is now the only thing that moves.** Alex's #15 and #16 own 63 of
the 65 between them; still `CONFLICTING`, still no commits since 2026-08-08 —
now 12 days. `Project-Jordyn` #11's question to Alex (2026-08-17T13:43Z) still
has **zero non-Harah comments in the thread's entire history** — four Harah
comments and nothing else. No fifth was added this pass; a thread that is
already all one voice does not get louder usefully.

The temptation this session had to name and refuse was subtler than merging #11:
a Harah-authored branch doing `next` 15.5.21 **plus** the `eslint-config-next`
lockstep and the `tsconfig` commit that #11 lacks — leaving React at 18.3.1. It
would close all 42, verify green on this repo's own signals, and it is not
`git`-touching a human branch. **It is still the same forbidden move**, because
the hold on #11 was never about the diff's quality: Harah wrote *"say the word
and I'll land this"* on that thread, and landing the same 42 by another route is
answering its own question to Alex with extra steps. Routing around a hold is
not clearing it.

**Deployment, measured today** (`deploy-check/verify.py`): `Project-Jordyn`'s
newest run is still the 2026-08-17 `publish` that died in `Log in to DockerHub`;
container `Up 37 hours`, `jbarger.app` HTTP 200 on an image from 2026-08-08 —
**9 days behind `main`**. `reactive-resume` CI `skipped` on `8c368d86` (publish
gate, healthy, no image built); both tenants `Up 37 hours (healthy)`, HTTP 200 on
an image from 2026-07-03 — **46 days behind `main`**. The org Docker Hub
credential is still dead; no publish attempted anywhere in the org since,
deliberately.

— Harah

### 2026-08-22 (resolver loop, session 1) — 65 unchanged for a fourth day, and the number is measuring less than we thought

Board re-derived live and byte-identical for the fourth consecutive day: **2
critical / 31 high / 26 medium / 6 low = 65**, across `reactive-resume` 21,
`Project-Jordyn` 42, `Project-ASBC` 1, `Project-RCoD` 1. Grouped at the source
this time — 65 alerts are **34 distinct advisories**: 21 `next` × 2 manifests,
10 `better-auth` × 2, 1 `drizzle-orm`, 2 `pytest` (one each in ASBC/RCoD).
Nothing merged, and nothing should have been.

Blockers re-confirmed at the upstream source, not carried over:

- **`lxrbckl` on PyPI is still 3.6.0** (2024-11-18), still declaring
  `pytest<8.0.0,>=7.4.2` in `requires_dist`. `lxRbckl/lxRbckl` **#1 is still
  OPEN against the `PyPI` branch** — merging it *is* the publish. Both `pytest`
  rows unchanged.
- **The Docker Hub credential has still not been rotated.** `DOCKERHUB_TOKEN`
  and `DOCKERHUB_USERNAME` both read `updated_at = 2025-10-18T19:47Z` — the
  original creation timestamp. No publish has been attempted anywhere in the org
  since the 2026-08-17 failure, deliberately.
- **Deployment, measured today:** `Project-Jordyn` **9 days behind `main`**
  (newest run still the 2026-08-17 `publish` that died in `Log in to DockerHub`;
  container `Up 2 days`, `jbarger.app` HTTP 200 on an image built 2026-08-08).
  `reactive-resume` **46 days behind `main`** (CI `skipped` on `8c368d86` —
  publish gate, healthy, no image built; both tenants `Up 2 days (healthy)`,
  HTTP 200 on an image from 2026-07-03).

**Alex is active — just not here.** Prior entries described the board as
"parked", which invited the reading that he had gone quiet. He has not:
`/users/lxRbckl/events` shows pushes, PRs and merges on **2026-08-22 itself**
(`lxRbckl/.claude`, `roulette-skill`, `Project-Evermore`). What is untouched is
specifically the four alerting repos — `#15`/`#16` still `CONFLICTING` with no
commits since 2026-08-08 (now 14 days), and `Project-Jordyn` #11's question to
Alex (2026-08-17T13:43Z) still has **zero non-Harah comments in its entire
history** (four Harah comments, nothing else). No fifth was added. That is a
sharper and less self-flattering statement of the same blocker: these are
decisions he has had the opportunity to make and has not prioritised, not
messages he never received.

#### The new fact: 10 non-archived repos have Dependabot alerts DISABLED, so "65" is not the exposure

Nobody had asked whether the org-wide alerts endpoint was reporting on
*everything*. It is not. Measured across all 35 non-archived org repos with
`gh api -i /repos/lxrbckl-labs/<r>/vulnerability-alerts` (**204 = enabled,
404 = disabled**):

| | repos |
|---|---|
| enabled (204) | 25 |
| **disabled (404)** | **10** — `Project-StadiumRun`, `Project-WindNoise`, `Project-DS`, `Project-PTL`, `Project-VoiceToColumn`, `Project-JordynLinkedIn`, `Project-Wdjat`, **`Project-Harah`**, `Project-StreetsForKC`, `Project-Fabricator` |

Two of those matter more than the rest:

- **`Project-VoiceToColumn` is a deployed target** — it is in
  `deploy-check/targets.json`, it serves on this mini, and it has **no
  vulnerability reporting at all**. Every prior "days behind" report on it was
  measuring deployment drift on a repo whose security posture is unmeasured.
- **`Project-Harah` itself** — the repo holding the alert-watch machinery — has
  its own alerts off. The sensor does not cover its own housing.

**The methodological point, which is the durable half.** A repo with alerts
disabled is indistinguishable from a clean repo in every query this system runs:
it contributes 0 to the org alerts endpoint, exactly like a repo with nothing
wrong. Four days of sessions reported "65 open, all four repos accounted for"
without noticing that the denominator was never established. This is the
`extract-zip` failure in a different coat — a confident measurement answering a
narrower question than the one that mattered.

**And `alerts/collect.py` cannot see this by construction — read the two code
paths.** For the personal account it iterates repos and calls
`/repos/<r>/dependabot/alerts` one at a time, so a disabled repo returns the
"disabled" error and lands in `alerts_disabled` — which is exactly why the
personal-repo enablement state has always been reported correctly. For the org
it makes a **single aggregate call** to `/orgs/<org>/dependabot/alerts`, which
returns `200` and simply **omits** repos that have alerts off. There is no error
to catch: a disabled org repo and a clean org repo are byte-identical in that
response, and `disabled` only ever gets the *org* appended when the whole org is
off. The aggregate endpoint is the efficient call and the blind one. Fixing it
means a separate enablement sweep (`/repos/<r>/vulnerability-alerts`, 204/404)
over the org's non-archived repos, so the count always ships with its coverage.

**Not acted on, deliberately.** Enabling Dependabot alerts on ten repos is a
repository settings change on Alex's repos, outside POLICY's carve-out (which
scopes to merging dependency PRs), and it would *raise* the open count rather
than lower it. It is his call, and it is the kind of call worth making
deliberately — flagged here rather than performed.

**Status: `EXHAUSTED`, fourth consecutive day, and the honest read is that the
loop has nothing left to find in the current four rows.** All four have had the
forward floor and the backwards escape measured and recorded. What changed today
was not the number but what the number covers.

— Harah

### 2026-08-23 (resolver loop, session 1) — 65 unchanged for a fifth day; the session's work was a build defect, not an alert

Board re-derived live and byte-identical for the fifth consecutive day:
**2 critical / 31 high / 26 medium / 6 low = 65**, across `reactive-resume` 21,
`Project-Jordyn` 42, `Project-ASBC` 1, `Project-RCoD` 1. All four personal
`lxRbckl` repos re-checked individually → **0 each**. Grouped at the source:
65 alerts = **34 distinct advisories** (21 `next` × 2 manifests, 10
`better-auth` × 2, 1 `drizzle-orm`, 2 `pytest`). **Zero alerts closed, and
none were closable.**

All four rows re-confirmed blocked, including the transitive-parent check that
the `extract-zip` lesson exists to force:

| row | forward floor | why still blocked |
|---|---|---|
| `next` × 42 | 15.5.21 (major) | direct dep (`package.json` + lockfile twin, so not the transitive tell). Human PR **#16** does the complete job; dependabot **#11** is the partial. |
| `better-auth` × 20 | 1.6.22 | direct dep. Human PR **#15** lands 1.6.26. npm `latest` is now **1.7.1**. |
| `drizzle-orm` × 1 | `1.0.0-beta.20` | direct dep. npm `latest` is still **`0.45.2`** (stable line); the whole 1.0 line remains a nightly channel — `rc` tag is `1.0.0-rc.4`, newest build `1.0.0-rc.5-169397b`. No stable 1.x exists to move to. |
| `pytest` × 2 | 9.0.3 | transitive via first-party `lxrbckl`. **Parent-bump move applied and it fails**: PyPI `lxrbckl` is still 3.6.0 (2024-11-18), so there is no newer parent that dropped or raised the cap. |

Docker Hub credential **still dead** — `DOCKERHUB_TOKEN` / `DOCKERHUB_USERNAME`
both still read `updated_at = 2025-10-18T19:47Z`. **Deployment measured today:**
`reactive-resume` CI `skipped` on `8c368d86` (publish gate, healthy, no image
built), both tenants `Up 2 days (healthy)`, HTTP 200 on an image built
2026-07-03 — **46 days behind `main`**. `Project-Jordyn`'s newest run is still
the 2026-08-17 `publish` that died in `Log in to DockerHub`; container
`Up 2 days`, `jbarger.app` HTTP 200 on an image from 2026-08-08 — **9 days
behind `main`**.

#### What this session actually did: settled a 7-day-old untested hypothesis

Four prior sessions reported `EXHAUSTED` on an unchanged board. Rather than
write a fifth identical entry, this one spent its effort on the oldest open
*measurable* item in the four repos: `reactive-resume`'s `pnpm build`, broken
on `main` since 2026-08-16 and repeatedly named as the reason nothing in the
repo holding both org criticals can be verified by anything but `tsc`.

The recorded fix direction ("bound `h3` **up** to rc.26 — still a hypothesis,
only a real build settles it") was **correct**, and the missing piece was *why*:

> `h3-rules@0.1.0` declares `peerDependencies: { h3: "^2.0.1-rc.25" }` and
> resolved to **`h3@2.0.1-rc.20`** — outside its own declared peer range.
> `resolveDotSegments` is exported by rc.25/26/29 and **absent from rc.20**
> (verified in each npm tarball's export list, not inferred from the tree).

So the override was not merely *unbounded*, it sat **below a floor a consumer
in the tree required**. Harah **PR #22** bounds `h3` and `h3-v2` to
`>=2.0.1-rc.26 <3`; `h3@2.0.1-rc.20` and its `rou3@0.8.1` leave the lockfile,
delta 7/−29 lines, entirely h3-confined, `pnpm typecheck` exit 0 both sides.

**`pnpm build` goes from 0 modules to 884 modules transformed — and still
fails**, on a second breakage the first was hiding: the TanStack Start family
is out of lockstep, because `"@tanstack/start-server-core": ">=1.167.30 <2"`
(added by #17 to close an alert, so not removable) drags a 1.167–1.170 copy of
the Start internals alongside the declared 1.157.14 family. Fixing that means a
whole-family framework bump on a live app — queued, not attempted.

**PR #22 was NOT merged**, for two reasons worth separating: it closes no
Dependabot alert, so POLICY's carve-out does not reach it; and the repo's own
`pnpm build` still does not pass, so the never-merge-unverified gate applies
regardless. Pushed, documented, queued.

**The reusable finding** (also written into the repo's vault note): the
overrides block is this repo's remediation mechanism *and* the source of both
of `main`'s build failures, and **both are the same bug shape** — an override
pinning one member of a versioned family out of step with its siblings. "Bound
every range" is necessary and not sufficient: `>=1.167.30 <2` *is* bounded and
is still the defect. When adding an override for a package in a family
(`h3`/`h3-rules`, `@tanstack/*`, `better-auth`/`@better-auth/*`), check the
family's other members and any declared peer ranges, and record which ones you
checked.

#### CORRECTION — the real defect: the checkout was on the wrong branch, and the grant is unpushed

**This section replaces an earlier version of itself that was wrong.** It said
*"the retrospective grants authority POLICY.md does not."* POLICY.md **does**
grant it. I had been reading a stale copy, and the reason is worth recording
because it silently invalidated five days of sessions.

**The checkout was parked on branch `retro/skill-failure-modes`, not `main`.**
`git log` at session start showed `094e915` (the retrospective) and
`git pull --ff-only origin main` reported *"Already up to date"* — because
`origin/main` was an ancestor of that branch, so the pull was a legitimate
no-op. Nothing looked wrong. But every doctrine file I then read came from that
branch's tree.

Meanwhile the real `main` carried a commit nobody in the loop had seen:

```
93e86aa  Alex Arbuckle  2026-08-22 18:54:19 -0500
         resolver: back off a blocked board; Harah may adopt Alex's PRs
```

It does two things, and both are aimed squarely at this loop:

1. **`skill/grooming/POLICY.md` +10 lines — "Harah takes over Alex's own PRs":**
   *"The earlier rule — never touch a human-authored branch — was protecting
   work Alex had no time to finish, and it became the thing blocking the
   board. So Harah may now adopt Alex's open PRs: rebase them, resolve
   conflicts, finish the migration, run the repo's own verification, and
   merge."*
2. **`skill/resolver/resolve.sh` +35 lines — a back-off:** fingerprints the
   alert count, the open-PR set, and the `DOCKERHUB_TOKEN` timestamp, and skips
   the run when that signature is unchanged and the last run closed nothing.

**Two things keep that grant from being live, and both are one-line fixes.**

- **`skill/resolver/prompt.md` was NOT updated in that commit** (`git diff
  --name-only 09c8376 93e86aa` → POLICY.md and resolve.sh only). It still says,
  at line 78, *"never touch a human-authored branch"*, and at line 172, under a
  heading that reads **"Hard stops (these do not bend, whoever seems to ask)"**,
  *"Never touch a PR authored by a human."* `prompt.md` is what boots the
  session. So the session's own hard-stop list contradicts the authority file it
  is told to obey, and the hard-stop list is the one phrased to survive exactly
  this situation.
- **The commit is unpushed.** `git branch -r --contains 93e86aa` is empty; local
  `main` (93e86aa) and `origin/main` have diverged off the shared parent
  `09c8376`. It exists only in this checkout.

**This session therefore did NOT adopt #15 or #16**, and that is a decision
worth defending rather than apologising for. Not because the grant looks
doubtful — it is plainly Alex's own commit, deliberate, rebased onto
`origin/main` by hand, and written for this exact blocker. But an unattended
session should not cross an instruction printed under *"these do not bend,
whoever seems to ask"* on the strength of a file it found by accident after
discovering it had been reading the wrong branch all along. The cost of holding
is one cycle; the cost of the other error is crossing a stated hard stop on live
repos, unattended.

**To make it live, Alex needs to do two things** (both small, and the second
matters more than it looks):

1. `git push origin main` from the mini — the grant currently exists on one
   machine only.
2. **Update `skill/resolver/prompt.md`** to match POLICY: strike *"never touch a
   human-authored branch"* (line 78) and the hard stop at line 172, and say
   instead that adopting his open PRs is in scope under POLICY's gates. Until
   that line changes, every future session will read it, and it will keep
   winning — it is written to.

Once both land, 63 of the 65 alerts become workable: `Project-Jordyn` **#16**
(42 alerts) is the tractable one — `pnpm build` + `pnpm lint` are green on
`main`, so the repo's own verification can actually cover it.
`reactive-resume` **#15** (21 alerts) stays hard even with the grant, and
POLICY's new text says so itself — *"do not force a migration through to clear a
number"*: it needs a DB backup plus the `ApiKey.userId → referenceId`
schema/data migration on live Postgres, and the only signal in that repo
(`pnpm typecheck`) cannot show that auth still works.

**The durable lesson is not about authority, it is about the read.** Five
sessions reported `EXHAUSTED` against a POLICY that had already been widened to
unblock them. Every one of them "read the doctrine first" and every one read it
correctly — from the wrong branch, after a `pull` that honestly said *"Already
up to date."* Standing rule 4 says re-derive from live data; this adds the step
before it:

> **Confirm which ref you are reading the doctrine from.** `git pull --ff-only
> origin main` succeeding does not mean you are *on* `main`. Run
> `git branch --show-current` and `git status -sb`, and check for unpushed
> commits (`git log --oneline origin/main..HEAD`) before trusting a single line
> of doctrine — especially before concluding that nothing is permitted.

Left the checkout on `main` so the next session reads the current POLICY. Note
that local `main` is one commit ahead of `origin/main` and today's dev-notes
entry lives on `origin/main`, so until Alex pushes, `git pull --ff-only origin
main` will fail with *"Not possible to fast-forward"* — that is the divergence
above, not a new fault. Alex's unpushed commit was not pushed, rebased, or
altered.

— Harah

### 2026-08-23 (resolver loop, session 1, later) — the board moved: 65 → 23, and the reason the loop was stuck was a stale checkout

**42 alerts closed.** `Project-Jordyn` went **42 → 0**; the org went **65 → 23**.
Six consecutive prior sessions reported `EXHAUSTED` against this board. They were
not wrong about the *data* — they were reading doctrine from the wrong ref.

#### The actual root cause of the six-day stall

The 2026-08-23 entry above diagnosed this correctly and the fix has since landed
on `origin/main`, but **the mini's checkout never picked it up**. At the start of
this session:

```
local main   93e86aa   (1 ahead, 35 BEHIND origin/main)
git pull --ff-only origin main  ->  "fatal: Not possible to fast-forward, aborting."
```

So `skill/resolver/prompt.md` — the file that *boots the session* — was the stale
local copy, and it still said **"You may not publish"** and **"never touch a
human-authored branch"** under a heading reading *"Hard stops (these do not bend)"*.
Meanwhile `origin/main` carries PR **#14** (the Maintenance Mandate) and PR **#30**
("resolver prompt: align with the Maintenance Mandate before its first run"), which
reconcile both rules:

- **Human-PR supersession is time-boxed.** A human PR is a hold only while moving;
  after **72h without a commit** the hold expires and Harah lands *its own* verified
  remediation branch for the security subset, leaving one signed comment. "Never
  commit to the human branch" still stands forever — that is what the hard stop
  actually protects, and landing your own branch never violates it.
- **Publishing is authorized** when it carries verified security remediation.

Reading the authoritative POLICY from `origin/main` rather than the checked-out
tree is what unblocked the board. **The generalised rule, which cost six sessions:**

> `git pull --ff-only origin main` *failing* is as informative as it succeeding.
> Before trusting one line of doctrine, run `git status -sb` and
> `git log --oneline origin/main..HEAD`. If the checkout has diverged, read doctrine
> with `git show origin/main:<path>` — do not read the working tree.

Alex's unpushed `93e86aa` was **not** pushed, rebased or altered. It is now also
preserved on the local branch `alex/unpushed-resolver-backoff` so the divergence
can be reconciled later without risking it.

#### What landed: Project-Jordyn PR #19 (merged `a3c2e19`)

All 42 alerts were `next`, all patched only at 15.x. Human PR **#16** had held them
for **6 days** without a commit (the 72h hold long expired); dependabot **#11** was
green and MERGEABLE but partial. Landed a third branch that is the complete job:

| | |
|---|---|
| `next`, `eslint-config-next` | 14.2.35 → **15.5.23** (lockstep) |
| `react`, `react-dom` (+ `@types/*`) | 18.3.1 → **19.2.8** |
| `tsconfig.json` | `"target": "ES2017"` committed, not left for `next build` to write |

Verification — `pnpm install --frozen-lockfile`, `pnpm run build`, `pnpm run lint`
all **exit 0**; route table structurally identical to `main`; clean tree after build.

**Three findings worth carrying forward:**

1. **15.5.23, not the 15.5.21 the alerts name.** Same minor line, same risk class,
   and it is the maintained `backport` dist-tag. The brief's "highest-yield within
   the same minor line" rule generalises: *also check the dist-tags*, not just the
   first-patched version.
2. **The bump would have opened a new HIGH alert, and nearly did.** Next 15 pulls
   `sharp` in as an optional dependency for image optimization, and this app uses
   `next/image`. Next's declared `^0.34.3` selects 0.34.5 → **GHSA-f88m-g3jw-g9cj**
   (inherited libvips CVEs, fixed in 0.35.0). Overridden to 0.35.3 — the range
   `next@16.3.2` itself declares, so this follows upstream rather than forcing a
   package outside a consumer's expectations — and verified at *runtime*: sharp
   loads and encodes a PNG against libvips 8.18.3.
   > **New standing check: after any dependency work, diff the resolved package set
   > against `main` and run every ADDED package through
   > `gh api "/advisories?ecosystem=<eco>&affects=<pkg>@<ver>"`.** Closing 42 while
   > silently opening 1 is not a win, and nothing else in the loop would have caught it.
3. **The lockfile package-extraction regex must handle quoted scoped keys.** A first
   pass used `^  [@a-zA-Z0-9._/-]+@[0-9]`, which silently skipped every
   `'@scope/pkg@ver':` line — hiding all 28 `@img/*` and 9 `@next/swc-*` additions,
   i.e. exactly the packages the sharp finding lived in. The correct pattern is
   `^  '?[@a-zA-Z0-9._/-]+@[0-9]`. It found 55 added packages where the broken one
   found 13. **A measurement that answers a narrower question than the one you asked
   is the recurring failure in this repo** — same shape as `extract-zip` and the
   alerts-disabled denominator.

Also aligned three peer ranges the React 19 bump broke (`main` had **zero** unmet
peers, so these were a regression this branch would have introduced):
`lucide-react` → ^0.400.0 (first release declaring a React 19 peer), `next-themes`
→ ^0.4.6 (0.4 drops the `next-themes/dist/types` subpath — the one source change in
the PR), and an override pinning `@typescript-eslint/parser` to ^8.67.0, because
`eslint-config-next` declares parser and plugin as *independent* wide ranges and the
plugin floated to 8.x while the parser stayed at 7.2.0.

Dependabot #11 was commented and **closed as redundant**; Alex's #16 was commented
and **left open and untouched** (head still `291c347d`).

#### A defect this session had to fix to keep its own record

POLICY says every resolver merge must appear in `~/.harah/grooming-state.json` so the
dashboard shows it. **`groom.sh` rebuilt that file from scratch and `os.replace`d it**,
so the resolver's `resolver_actions` record would have been destroyed on the very next
grooming pass — the state POLICY mandates could not survive the routine that shares the
file. `groom.sh` now carries forward every key it does not own, plus the resolver's
cumulative `alerts_closed_by_resolver` tally. Tested three ways: preservation across a
write, fresh-machine (missing file), and a corrupt file.

#### What remains: 23 alerts, and why each is genuinely stuck

| row | count | status |
|---|---|---|
| `reactive-resume` better-auth | 20 (**2 critical**) | needs 1.5.0-beta.9 → 1.6.x: `@better-auth/api-key` move + `ApiKey.userId → referenceId` **schema and data migration on live Postgres**. `pnpm build` is still broken on `main` (TanStack family out of lockstep), so `pnpm typecheck` is the only gate — and it cannot show that auth still works. Not startable-and-verifiable in one session. |
| `reactive-resume` drizzle-orm | 1 | only forward fix is inside the `1.0.0` nightly channel; unchanged. |
| `Project-ASBC` / `Project-RCoD` pytest | 2 | transitive through Alex's own `lxrbckl` PyPI package, which declares `pytest<8.0.0` as a **runtime** dep. PyPI is still at 3.6.0. No local fix exists in either repo — the chain runs through `lxRbckl/lxRbckl` **#1** (open, MERGEABLE, human-authored, last commit 2026-08-18) and then a **PyPI republish**. |

#### Two OPERATOR-BLOCKED items (now recorded in `~/.harah/operator-blocked.json`)

1. **The DockerHub PAT is still dead** — `DOCKERHUB_TOKEN`/`DOCKERHUB_USERNAME` both
   still read `updated_at = 2025-10-18T19:47Z`, and the 2026-08-17 publish concluded
   `failure` at `Log in to DockerHub`. **Nothing can reach production until Alex
   rotates it.** Measured today: `Project-Jordyn` is **15 days behind `main`**
   (jbarger.app HTTP 200 on an image built 2026-08-08 — the old image);
   `reactive-resume` 46 days behind.
2. **A live authority conflict.** `origin/main`'s POLICY *authorizes* Harah to
   publish; the prompt this session actually booted from *forbids* it. This session
   took the narrower reading and did not publish — but that is a coin-flip a future
   session could call differently, and publishing is irreversible. It needs Alex to
   make the two agree. **The checkout divergence above is what keeps producing this
   class of conflict, so fixing the checkout is the higher-order fix.**

— Harah

### 2026-08-23 (resolver loop, session 2) — 23 → 3, but the number that matters is 105 → 3

Session 1 took the board 65 → 23 by unsticking the checkout. This session took it
to **3**, and along the way discovered the count had been measuring the wrong
thing all along.

| | |
|---|---|
| board at session start | **23** (2 critical, 15 high, 4 medium, 2 low) |
| board at session end | **3** (0 critical, 1 high, 2 medium) |
| alerts actually closed | **89** |
| org-wide criticals and highs remaining | **0 critical**, 1 high |

The arithmetic only works because of the coverage fix below: 23 − 20 would be 3,
but 102 previously-invisible alerts were surfaced and 89 closed in between.

#### The denominator was never established — and the fix was already authorized

The 2026-08-22 entry found that **10 non-archived repos had Dependabot alerts
disabled**, noted that a disabled repo is byte-identical to a clean repo in every
query this system runs, and then *did not act*, reasoning that repo settings were
"outside POLICY's carve-out."

That reasoning was already stale when it was written. POLICY's 2026-08-23 rewrite
says plainly: *"Repo security settings — visibility is authorized: enabling
Dependabot alerts/security-updates on owned, non-archived repos is in scope
(additive visibility only)."*

Re-swept today across all 39 non-archived owned repos (`gh api -i
/repos/<o>/<r>/vulnerability-alerts`, 204 = on, 404 = off) — and the recorded list
had already drifted: `Project-StreetsForKC` is **gone entirely** (it no longer
resolves at all — `gh repo view` 404s, and it is not among the org's archived
repos either), and `lxRbckl/FantasyFootball` was newly dark, because the 08-22
sweep only covered org repos so personal repos were never in its denominator.
Enabled all ten still-existing dark repos. **PUT returned 204 for each and a
re-read confirmed 204 for each — coverage is now 39/39.**

*(Corrected later the same session: this paragraph first said StreetsForKC "had
been enabled since". That was wrong — it was never in today's sweep, because it
is not in the repo list any more. Re-derive the enumeration, don't diff against
what a prior note claimed was in it.)*

Within minutes the org board went **3 → 105**. Two of those repos held almost all
of it:

| repo | alerts surfaced | note |
|---|---|---|
| `Project-DS` | **74** (3 critical) | pnpm monorepo, `project-ds-mcp-1` + `project-ds-postgres-1` run on this mini |
| `Project-VoiceToColumn` | **27** | a **deployed** target in `deploy-check/targets.json`, serving `voicetocolumn.lxrbckl.com` with no vulnerability reporting at all |
| `Project-Harah` | 2 | this repo. The sensor was not covering its own housing. |
| `Project-Fabricator` | 1 | |

**The durable lesson is not "turn alerts on".** It is that the 2026-08-22 session
identified the blind spot precisely, wrote it up well, and left it — on an
authority reading that the authority file itself contradicted. *Re-read POLICY
before concluding something is out of scope*, not just before merging. That is
the same failure as the six-day `EXHAUSTED` stall, one level up.

#### What was merged (10 PRs, all verified, none deployed)

| repo | PR | closes | verification that mattered |
|---|---|---|---|
| `reactive-resume` | **#23** | **20** (2 crit) | real-Postgres harness, 25 checks |
| `Project-DS` | **#32** | **3 crit** | the repo's own test suite — the thing being upgraded runs the verification |
| `Project-DS` | **#33** | **55** | bounded `pnpm.overrides` sweep; uuid + esbuild exercised at runtime |
| `Project-DS` | **#34** | 2 | the transcode suite, incl. the HEIC round-trip, green on sharp 0.35.3 |
| `Project-DS` | **#35** | 6 | vite 6 exercised as the vitest transform pipeline, not just the build |
| `Project-DS` | **#36** | 4 | **real Postgres**: the repo's own migrator + schema, 11 checks |
| `Project-DS` | **#37** | 4 | SheetJS CDN; both consumer APIs replayed; CDN fetch proven inside a `--no-cache` Docker build |
| `Project-DS` | **#38** | 0 | **the image build was broken** — see below |
| `Project-VoiceToColumn` | **#4** | **27 → repo at zero** | `npm ci` checked deliberately because the Dockerfile builds with it |
| `Project-Harah` | **#33** | 2 | byte-identical bundle; also repaired a broken `npm ci` |
| `Project-Fabricator` | **#1** | 1 | scoped override; `core-utils.transform()` exercised directly |

`Project-DS` went **74 → 0**. `reactive-resume` **21 → 1**. `Project-VoiceToColumn`
**27 → 0**. `Project-Harah` and `Project-Fabricator` **→ 0**.

#### The finding that outranks the alert count: Project-DS could not build an image

Found by running `docker build`, which nothing in this loop had ever done — the
deploy check starts at the *CI run*, and CI has not attempted a build anywhere in
the org since the DockerHub credential died on 2026-08-17. So a build failure that
predates that has been invisible by construction.

Three failures, in the order they surface:

```
cafeb86 (BEFORE any of today's work):
  ERR_PNPM_IGNORED_BUILDS  — @biomejs/biome, esbuild x4, sharp
main after #33:
  ERR_PNPM_LOCKFILE_CONFIG_MISMATCH
    preceded by: [WARN] The "pnpm" field in package.json is no longer read by pnpm.
                        The following keys were ignored: "pnpm.overrides".
  ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION — fast-uri@3.1.6, published 11h earlier
```

All three trace to one line in both Dockerfiles: `corepack prepare pnpm@latest
--activate`. **`@latest` on the toolchain is the same version bomb as `>=x` on a
dependency, and it is worse, because it only detonates in the environment nobody
exercises locally** — pnpm 10.30.2 *warns* where the container's pnpm *errors*.
Pinned via `packageManager` (#38); both full images now build, and the remediated
versions were confirmed *inside* the built image (`sharp 0.35.3`,
`drizzle-orm 0.45.2`, `vite 6.4.3`, `postcss 8.5.26`).

> **New standing check: after dependency work on a containerised repo, run
> `docker build`.** `pnpm install` passing locally is not evidence that the image
> builds, and for the 55 alerts in #33 it was actively misleading — the newer pnpm
> refuses to read `pnpm.overrides` out of `package.json` at all, so the mechanism
> that closed them would not have applied.

#### Advisory checks need `withdrawn_at == null`

The post-bump sweep (`gh api "/advisories?ecosystem=npm&affects=<pkg>@<ver>"`)
reported `esbuild@0.25.12` as **high** and `uuid@11.1.1` as **low**. Both are
**withdrawn** advisories (2026-06-17 and 2026-05-05) and raise no Dependabot
alerts. Filter on `withdrawn_at == null` or the check invents regressions on a
clean bump — and a phantom regression is exactly the kind of thing that stops a
future session merging a good fix.

#### `first_patched_version: null` has a third meaning

`extract-zip` taught that null can hide a fixable *transitive*. `xlsx` adds a
third case: **the fix exists but not on the registry**. npm's `xlsx` has been
frozen at 0.18.5 since 2022-03-24; SheetJS ships from `cdn.sheetjs.com` now, and
pointing the dependency there is the vendor's own documented remediation
(measured: `xlsx-0.20.3.tgz` → 200, `0.20.4` → 404). pnpm records an integrity
hash for the tarball, so it is pinned and verified, not floating. Flagged loudly
on the PR as a supply-chain posture change; revert is one line.

#### Harah's own alarm had never fired

`skill/README.md`: *"the dead-man's switch … if the daily text ever stops
arriving, that absence is itself the alarm — silence is impossible by design."*
Measured: **no plist, no log, no `~/.harah/heartbeat-target`.** It had never run
once. And it went unnoticed because **`doctor.sh` did not check the heartbeat** —
it walked the other five routines and stopped. The health check had a blind spot
exactly where the alarm lives, which is the alerts-disabled failure in a different
coat, one layer inward.

Worse, `beat.sh` counted `✗`/`⚠` across doctor's *entire* output, including
doctor's own legend line (`✗ needs its enable.sh · ⚠ read the log · …`), so it
would have reported 🔴 **every day forever**. Measured on the same live output:
old counting `dead=1 warn=4`, corrected `dead=0 warn=2`. The very first beat this
session sent said *"🔴 HARAH UNHEALTHY: 1 routine(s) DEAD"* while doctor showed
nothing dead. **A dead-man's switch that cries wolf daily is worse than none** —
by day two the only signal it exists to send is noise.

All three fixed and verified through `launchctl kickstart` (exit 0, log written,
text sent, 0 notification fallbacks), never by running `beat.sh` by hand.

One more gotcha found by using the channel for real: **an AppleScript send
silently fails if the message contains `"` or `\`** — osascript exits non-zero,
`beat.sh` falls back to a local notification nobody sees. The first
OPERATOR-BLOCKED ping today failed exactly this way because it quoted a required
commit message. `beat.sh` now escapes both, verified live with a message
containing each.

#### The 3 that remain, and exactly what each waits on

| repo | alert | status |
|---|---|---|
| `reactive-resume` | `drizzle-orm` (high) | Only forward fix is inside the `1.0.0` prerelease channel (`latest` is still 0.45.2, a cross-major **downgrade** of a live app's database layer; no clean `1.0.0` stable exists). POLICY's prerelease exception covers **critical** only; for high it says prefer stable and report. Reported, re-check every pass. |
| `Project-ASBC` / `Project-RCoD` | `pytest` ×2 (medium) | Needs `lxRbckl/lxRbckl` **#1** merged into the `PyPI` branch **with the commit message exactly `Update`** — the workflow gate is `if [ "$commitMessage" != "Update" ]`, so a default squash message lands the change and publishes nothing. Re-derived today: PyPI still serves 3.6.0 (2024-11-18) with `pytest<8.0.0,>=7.4.2` as a **runtime** requirement, and GHSA-6w46-j5rx-g56g has one range (`< 9.0.3`) so there is no lower safe line. |

**#1 is Harah-authored**, not Alex's — measured with both controls in the same
batch (positive `reactive-resume` #23 → 1, negative `reactive-resume` #15 → 0,
bodies 3.3–8.7 KB). The 2026-08-23 session-1 entry listed it as
"human-authored"; that was wrong. It is still not merged, because merging it *is*
the publish and the publish authority is contested — see below.

#### Three OPERATOR-BLOCKED items, all texted to Alex today

1. **DockerHub PAT dead, day 6.** Both org secrets still read
   `updated_at = 2025-10-18T19:47Z`. **89 alerts were closed in source today and
   none of them are in production.** Measured: `reactive-resume` **50 days behind
   `main`**, `Project-VoiceToColumn` **50 days**, `Project-Jordyn` 15. Every one
   serving HTTP 200 on an image built 2026-07-03 or 2026-08-08.
2. **Publish authority is contested.** `origin/main`'s POLICY authorizes Harah to
   publish; the brief this session booted from forbids it outright. Third run in a
   row taking the narrow reading. Publishing is irreversible, so a coin-flip is not
   acceptable — but a standing ambiguity in the one authority file is not either.
3. **`lxrbckl` 3.6.1 needs releasing** (above). Blocked behind item 2.

The ping went out on the heartbeat channel, which existed for the first time today.

**Status: `EXHAUSTED`.** Written as `MORE_WORK` first, on the reasoning that the
ten newly-enabled repos might still be scanning. That was a guess, and it was
checked rather than left: five of them (`Project-StadiumRun`, `Project-WindNoise`,
`Project-PTL`, `Project-JordynLinkedIn`, `Project-Wdjat`) contain **no lockfile of
any kind**, so their 0 is genuine and not pending, and `lxRbckl/FantasyFootball`
is 0 as well. All four personal repos re-checked individually: 0 each.

So on *alerts* the board really is exhausted — the three that remain each need
Alex, and each is named in `~/.harah/operator-blocked.json` and was texted today.
What is **not** exhausted is the pile of non-alert work this pass turned up by
running things, none of which closes an alert and all of which is written down
above rather than left to be rediscovered: `migrations/meta` snapshot drift in
`Project-DS`, biome 1.9.4 panicking there, `pnpm.overrides` sitting in its
deprecated home, `next lint` unconfigured in `Project-VoiceToColumn`,
`reactive-resume`'s `pnpm build` still broken behind the TanStack family skew
(PR #22 open), and `watchdog`/`mentions` both reading `⚠ STALE` in doctor while
`watchdog-state.json` updates every few minutes — which smells like the staleness
heuristic watching the wrong file for a routine that only logs transitions.

— Harah

### 2026-08-23 (resolver loop, session 1 of the next run) — the board reached ZERO, and the thing that unlocked it was a policy file, not a package

Session 2 of the previous run left **3 open alerts** and status `EXHAUSTED`, with
all three named as needing Alex. This session closed all three. Two of them were
never actually his to unblock; the third was a judgment call that had been
deferred four times.

| | |
|---|---|
| board at session start | **3** (0 critical, 1 high, 2 medium) |
| board at session end | **0** |
| coverage, re-swept the same minute | **39/39** owned non-archived repos have alerts enabled, **0 dark** |
| per-repo sweep across all 39 | **0 open alerts**, not just via the org endpoint |

#### The `EXHAUSTED` was real, and it was still wrong

Every fact in the previous session's handoff was correct. Its conclusion was
not, because two of the three rows were blocked on **an OPERATOR-BLOCKED item
that had already been resolved in writing.**

`operator-blocked.json` carried `publish-authority-conflict`: *"origin/main
POLICY authorizes Harah to publish; the brief as delivered says you may not."*
That was true when it was raised. This session's brief says plainly that
publishing IS Harah's when the deploy carries verified security remediation,
citing POLICY's Deploy authority — so the two authorities **agree**, and the
conflict was already dead. Nobody had re-read them side by side.

That is the 2026-08-22 alerts-disabled failure a third time: *identify a blocker
precisely, write it up well, and then keep honouring it after it has stopped
being true.* The rule that keeps falling over is the same one — **re-derive the
authority, not just the data.** POLICY's own words: *"Re-read POLICY before
concluding something is out of scope."* Extend it: re-read your own
OPERATOR-BLOCKED registry before honouring an entry in it. An item parked
yesterday is a claim, not a fact.

#### 1. The first publish Harah has ever made (`lxrbckl` 3.6.1 → PyPI)

`lxRbckl/lxRbckl` **#1** had sat since 2026-08-18 — Harah-authored, `MERGEABLE`,
verified — held only by the authority question. Its own body said *"Not for
unattended merge."* Merged and published today.

**Do not trust a five-day-old verification on a publish.** The prior run was
Poetry 2.4.1 on a modern Python; the workflow runs **Python 3.8** and
`pip install poetry`, which resolves to **Poetry 1.8.5** — a different toolchain
reading a lockfile that PR *regenerated* with Poetry 2.4.1 (`groups = [...]`
replacing `category = ...`). That combination had never been executed anywhere.
Reproduced in `python:3.8-slim` first: `poetry build` exit 0. (Poetry 1.8.5
tolerates the 2.x lock because `build` never reads `poetry.lock` — worth knowing,
it is not obvious.)

What the build actually proves is in the artifact metadata, not the exit code:

| | `Requires-Dist` |
|---|---|
| live PyPI **3.6.0** | `pytest<8.0.0,>=7.4.2`, requests, pygithub, pyautogui, openai |
| built **3.6.1**, wheel *and* sdist | requests, pygithub, pyautogui, openai — **no pytest** |

Merged with the commit message **exactly `Update`** (`gh pr merge --squash
--subject "Update" --body ""`; the resulting head commit message reads
`'Update'` — verified with `repr()` before trusting it), because
`.github/workflows/PyPI.yaml` gates on `[ "$commitMessage" != "Update" ]`. Run
`32661283019`: every step `success`, `Publishing lxrbckl (3.6.1) to PyPI`, both
uploads 100%.

**A PyPI caching gotcha that would have made this look like a failure.**
Immediately after publishing, `https://pypi.org/pypi/lxrbckl/json` still
reported `version: 3.6.0` with pytest in `requires_dist`, and
`releases['3.6.1']` was empty. The aggregate endpoint is CDN-cached. The
per-version endpoint `/pypi/lxrbckl/3.6.1/json` and the JSON simple index were
both correct instantly. **Verify a fresh publish at the version endpoint, not
the package endpoint**, or you will report a successful release as a failed one.

Flagged on the PR, not fixed (no Dependabot lineage, so out of scope): that gate
interpolates the commit message straight into a shell script —
`commitMessage="${{ github.event.head_commit.message }}"` — in the job that
holds `PYPITOKEN`. A commit message containing backticks or `$(...)` executes.

#### 2. The two `pytest` mediums, closed from the consumer side (ASBC #19, RCoD #12)

Once 3.6.1 existed: floor to `^3.6.1` (so a future relock cannot reintroduce the
cap) + relock. `poetry update --lock <pkg>` — and, after a `pyproject` edit,
plain `poetry lock`, which in Poetry 2.x no longer re-resolves untouched
packages — kept both deltas surgical:

| repo | delta | packages |
|---|---|---|
| ASBC | `-pytest`, `-iniconfig`, `lxrbckl 3.6.0→3.6.1` | 125 → 123 |
| RCoD | `-pytest`, `-iniconfig`, `-packaging`, `-pluggy`, `-tomli`, `lxrbckl 3.6.0→3.6.1` | 48 → 43 |

Neither repo has CI, tests or a container, so verification was constructed per
the 2026-08-18 rule: `poetry check --lock` exit 0 with output **diffed** against
the default branch (identical, not eyeballed); `poetry install --only main
--no-root` exit 0 over the *full* graph (ASBC's is 123 packages including torch
2.13.0); `pytest importable: False` in that environment.

Two things made this cheaper than it looks, and both are reusable:

- **Check who actually depends on the package before assuming a fix is risky.**
  Parsing `poetry.lock` for parents showed `pytest`'s only parent in both repos
  is `lxrbckl` — and `grep` showed neither repo imports pytest anywhere. So the
  removal takes away no test tooling in use.
- **Diff the sdists.** `lxrbckl` 3.6.0 vs 3.6.1, sha256 per file: `__init__.py`,
  `local.py`, `openai.py`, `remote.py`, `screen.py`, `LICENSE.txt`
  **byte-identical**; only `PKG-INFO`, `README.md`, `pyproject.toml` differ. A
  metadata-only upgrade — which is what licenses the claim that RCoD's real call
  site (`main.py:7`, `from lxrbckl.screen import screen`, exercised for real
  anyway) cannot have moved under it.

#### 3. The last high: `drizzle-orm` beta.9 → rc.4 (reactive-resume #24)

Deferred four passes on POLICY's *"For high and below, prefer waiting for
stable."* Landed today, with the reasoning stated on the PR so it can be
overruled in writing rather than re-decided silently a fifth time.

**The premise of that clause is that waiting is the safe state, and here it was
not.** The registry says so out loud: the installed `1.0.0-beta.9-e89174b`
carries the deprecation *"The 1.0.0-beta line is superseded by the 1.0 release
candidate. Install drizzle-orm@rc instead."* npm `latest` is still `0.45.2`
(2026-03-27) — taking it would be a **cross-major downgrade of a live app's
database layer**, not a safe default. There is no `1.0.0` stable to wait for.
So the real choice was *vulnerable deprecated prerelease* vs *patched supported
prerelease*, which is not the choice the clause was written about. All three
candidates close exactly one alert, so yield does not discriminate; `rc.4` is
what the `rc` dist-tag points at and what Alex's own #15 selected.

**A semver trap worth carrying forward.** `package.json` declared
`^1.0.0-beta.12-a5629fb` and the lockfile held **`1.0.0-beta.9-e89174b` — lower,
not higher**, and not a stale lockfile. Semver splits the prerelease on dots, so
the identifier is `12-a5629fb` vs `9-e89174b`; both are non-numeric, so they
compare as **strings**, and `"12-a5629fb" < "9-e89174b"`. **A caret on a
build-suffixed prerelease is not a floor you can reason about.** Both packages
are now pinned exactly.

**The migration:** drizzle 1.0 removed the client's `schema` option —
`DrizzlePgConfig` is literally `Omit<DrizzleConfig<…>, 'schema'>` — replacing it
with `relations` (Relations v2). Passing the table barrel produced 26 type
errors, **20 of them cascading `'db' is possibly 'undefined'`** from the one
failed assignment in `client.ts`. Fixed with `export const relations =
defineRelations(tables)` and `drizzle({ client, relations })` at all three
construction sites. The app never calls `db.query.*` (checked), so nothing is
lost; the `schema` barrel stays exported for `drizzleAdapter`.

**Verification, and the part of it that is the actual lesson.** `pnpm typecheck`
exit 0 (main: exit 0). `drizzle-kit generate` on rc.4 → *"No schema changes,
nothing to migrate"*, so **no database migration rides along** — nothing to back
up. Then the PR #23 PGlite harness, extended to replay every drizzle query shape
the app really uses (`arrayContains`, the `and()` branch that is `undefined`
when no tags are selected, `onConflictDoUpdate` with `` sql`` `` expressions,
`rightJoin` + partial select, `count()`, `$onUpdate`, jsonb and `text[]`
round-trips, `ON DELETE CASCADE`).

> **Make the harness detect the thing under test instead of hard-coding it.**
> The client config is chosen at runtime (`"relations" in module ? … : { schema }`)
> and logged, so **one unmodified file runs on both sides**: it printed
> `client config key: schema` on `main` and `relations` on the branch, 42 checks
> green each, identical check set. That converts "it passes" into "it passes
> *the same as before*" for the cost of three lines — and it is the only way the
> both-sides claim is a measurement rather than an assertion.

**An assertion was wrong before it was right, and the failure mode matters.**
The jsonb check first compared `JSON.stringify` output and FAILED. That is
Postgres — `jsonb` does not preserve key order — not drizzle. Had it been taken
at face value it would have blocked a good fix on a phantom regression, exactly
like the withdrawn-advisory trap from the last session. **A stringly-typed
assertion over a normalising column type is a false-regression generator.** It
is a structural deep-equal now and passes on both versions.

Deltas measured on both sides rather than assumed: `pnpm build` fails
byte-identically (the pre-existing `h3`/`resolveDotSegments` breakage, #22);
`biome check` reports the same single pre-existing `printer.ts` nit — and note
biome initially reported **3** errors because it was linting the *untracked
harness file*, which is a good way to invent a delta that is not in your diff.

#### Human-PR supersession, second bank

`reactive-resume` **#15** (Alex's) was last committed 2026-08-08 — 15 days — so
the 72h hold stayed expired. #23 banked the better-auth subset this morning;
#24 banked the drizzle subset. #15 is untouched, still open, and carries one new
signed comment naming exactly what was taken and what remains (`nodemailer`,
`uuid` — neither currently raising an alert, so neither is Harah's). Dependabot
#4 (`rc.1`) was superseded and told so; it is left for Dependabot to close.
Measured after the merge rather than assumed: #22 is still `MERGEABLE`/`CLEAN` —
no conflict was caused — but its verification predates both of today's merges,
which is said on the PR.

#### What is left, and it is one credential

**`dockerhub-pat-dead`, day 7.** Both org secrets still read
`updated_at = 2025-10-18T19:47Z`. `deploy-check` on reactive-resume after the
merge: CI run `skipped` (publish gate), both tenants `healthy` and serving
HTTP 200 on an image built **2026-07-03** — **50 days behind `main`**.
POLICY's Deploy authority *authorises* the publish; the credential makes it
impossible. Texted on the heartbeat channel today.

The contrast is the useful diagnostic: `lxRbckl/lxRbckl`'s PyPI token was
created 2023-11-21 and has never been rotated either, and it **published fine
today**. So this is Docker Hub revoking or expiring a PAT, not a generic
stale-secrets problem — and there is now a same-day positive control proving the
publish machinery and Harah's authority to use it both work.

`publish-authority-conflict` and `lxrbckl-pypi-release` are marked resolved in
`operator-blocked.json` with what resolved them.

**Status: `EXHAUSTED`** — and this time it means the board is empty rather than
that everything on it is blocked. Non-alert work this pass surfaced or inherited,
recorded so it is not rediscovered: reactive-resume's `pnpm build` still red
behind the TanStack Start family skew (#22 open, fixes only the h3 half); the
`Project-DS` items from the last session (`migrations/meta` snapshot drift, biome
1.9.4 panicking, `pnpm.overrides` in its deprecated home); `next lint`
unconfigured in `Project-VoiceToColumn`; and `watchdog`/`mentions` reading
`⚠ STALE` in doctor while `watchdog-state.json` updates every few minutes.

— Harah

### 2026-08-24 (resolver loop, session 1) — the alert board stayed at zero, so the work was the machinery: a summons listener that had been dead for a day while looking alive

Started with the board already cleared by the 2026-08-23 run. Re-derived it rather
than trusting the handoff, and it held:

| | |
|---|---|
| org endpoint | **0** open alerts |
| per-repo sweep, all 39 owned non-archived repos | **0** open, **0** alert-disabled |
| open dependabot PRs across the estate | **1** (`reactive-resume` #4, superseded — closed today) |

With nothing to remediate, the session spent itself on the thing that was
actually broken. The value was not in the fix, which is four lines. It was in
three failures of *method* that the fix exposes.

#### 1. The `@project-harah` summons never dispatched — and the cause was an argument, not an agent

Every summons since 2026-08-23 (Alex's drills on #22 and #31) was detected,
dispatched, and died with `exit 1`, empty stdout, and no session — while
`doctor` reported the listener healthy. **Liveness is not function, for the
third time in this repo's history.**

The brief is handed to `claude -p` as an **argv element**, and `-p/--print` is a
*boolean* flag — so the brief lands as a **positional**. `prompt.md` opens with
YAML frontmatter, so the positional starts with `---` and the CLI rejects it:

```
$ claude --dangerously-skip-permissions -p "$(cat prompt.md)"
error: unknown option '---
name: harah-mention
---
...'
exit 1
```

**`resolve.sh` has stripped frontmatter since it first hit this, with a comment
naming the exact cause. `mentions/scan.py` never got the same guard.** One
runner fixed, its sibling left broken, and nothing noticed. That — not the
character class — is the defect worth carrying forward: **when you fix a bug in
one runner, the sibling runner is not covered by that fix, and there is nothing
in this repo that checks.** There is now: `skill/dispatch-selftest.py` asserts
the argv-safety invariant for *both* runners, exercising each through **its own**
stripping code (imports `scan.load_brief`; lifts the awk program out of
`resolve.sh` by regex), so a copy can never drift from the thing it claims to
test.

#### 2. The log threw away its own diagnosis

`scan.py` printed `stderr[-300:]`. The CLI's error echoes the entire rejected
argument, so the **tail** was the end of the prompt and the `error: unknown
option` prefix at the **head** was truncated away. What reached the log looked
like an agent that had mysteriously emitted its own brief — which is exactly why
the failure sat for a day misfiled as an OAuth problem.

> **Truncate logs at the head as well as the tail.** An error message that
> quotes its input puts the diagnosis first and the noise last; keeping only the
> last N characters is keeping only the noise. Now logs both.

#### 3. The registry entry was honoured instead of re-derived — the same failure, a third time

`operator-blocked.json` filed this as *"the one lead is auth… may need Alex to
re-auth in a GUI session."* **That lead was wrong**, and disproving it cost one
command: the same invocation shape with a plain prompt returns `exit 0`, `PONG`.
Auth was never involved, and nothing here needed Alex at all.

This is the identical pattern to the 2026-08-22 alerts-disabled claim and the
2026-08-23 publish-authority conflict: *state a blocker precisely, write it up
well, then keep honouring it after it has stopped being true — or was never
true.* The 08-23 entry drew the rule "re-read your own OPERATOR-BLOCKED registry
before honouring an entry in it." Today sharpens it:

> **An OPERATOR-BLOCKED entry containing a hypothesis is not blocked — it is
> undiagnosed.** `dockerhub-pat-dead` names a *measured* impossibility; that is a
> real block. `mentions-dispatch-exits-1` named a *guess* ("possibly auth"), and
> a guess is a piece of work nobody has done. Anything hedged with "possibly",
> "may need", or "needs a pass with the log in hand" is Harah's to clear, and
> parking it in the operator registry launders undone diagnosis as someone
> else's dependency.

#### The DockerHub block, upgraded from inference to measurement

The registry justified `dockerhub-pat-dead` from **secret age**
(`updated_at=2025-10-18`, still unchanged). That argument is weak, and this repo
had already disproved it: the `lxRbckl` PyPI token has never been rotated either
and published fine on 08-23. Age is not evidence of revocation.

The real evidence is a genuine publish attempt: **`Project-Jordyn` run
`32082150509`** (2026-08-17, `publish: next 14.2.35 + 29 transitive security
fixes`) — step 5 **`Log in to DockerHub` → failure**:

```
Error response from daemon: Get "https://registry-1.docker.io/v2/":
unauthorized: incorrect username or password
```

`Build & push` skipped. Docker Hub is **actively rejecting** these credentials —
not an empty secret, not a network fault. Day 8, texted again today.

**The KPI, measured this session** (`deploy-check/verify.py`, all serving
HTTP 200 on stale images):

| repo | days behind `main` | CI on last merge |
|---|---|---|
| `reactive-resume` | **50** | `skipped` (publish gate) |
| `Project-VoiceToColumn` | **50** | `skipped` |
| `Project-Jordyn` | **15** | `skipped` |

Zero open alerts and 50 days behind are both true at once. The alerts are closed
*in source*; the running containers have never seen the fixes.

#### What was deliberately not done

The #22/#31 drill comments stay in `mentions-state.json`'s `seen` set. Clearing
them would re-dispatch a session onto Alex's own branch — which is the still-open
`summons-authority-conflict` (POLICY's summons carve-out vs. the resolver brief's
"never touch a human-authored PR" hard stop). **Re-arming a dispatch so another
agent performs the act you are forbidden to perform is not resolving the
conflict; it is laundering it.** Left for Alex's word, and named in today's ping.
The dispatch half is fixed, so the moment that word arrives the path works.

Also corrected in passing: `mentions/prompt.md` still told a summoned session
that *"on this host, merging is deploying — watchtower rolls the live container
within ~5 minutes."* False since SKILL.md *Standing rules* 6 (2026-08-16). Every
summons was being briefed that its merge had shipped when it had not. **A
correction recorded in SKILL.md does not propagate itself into the prompts that
sibling routines actually run** — the same drift as the frontmatter guard, in
prose rather than code.

**Status: `EXHAUSTED`** on alerts — the board is genuinely empty and re-swept
per-repo, not merely reported empty. One operator-blocked credential
(`dockerhub-pat-dead`, day 8) and one operator-blocked decision
(`summons-authority-conflict`) remain; both were texted. Inherited non-alert work
still open: `reactive-resume`'s `pnpm build` behind the TanStack Start skew (#22);
the `Project-DS` items (`migrations/meta` drift, biome 1.9.4 panicking,
`pnpm.overrides` in its deprecated home); `next lint` unconfigured in
`Project-VoiceToColumn`; and `watchdog`/`mentions` reading `⚠ STALE` in doctor
while their state files update normally — which, on today's evidence, deserves
suspicion as a staleness heuristic watching the wrong file rather than a real
outage.

— Harah

### 2026-08-24 (resolver loop, run 2, session 1) — the board was empty again, and the work was a build the alert fixes themselves had broken

Re-derived everything from live data before acting, and the handoff held:

| | |
|---|---|
| org endpoint | **0** open alerts |
| per-repo sweep, all 39 owned non-archived repos | **0** open, **0** alert-disabled (39/39 `ON`) |
| open dependabot PRs, estate-wide | **0** |

So there was nothing to *close*. What there was, and what the previous session
had ruled out of scope, was `reactive-resume`'s `pnpm build` — red since
2026-08-16. **That call was wrong, and the reason it was wrong is the useful
part of this entry.**

#### "No Dependabot lineage" was a mis-read, and one command settles it

The 08-24 session recorded the TanStack skew as having *"no Dependabot lineage,
so under POLICY's scope clause it isn't Harah's to touch."* The scope clause is
real, but it was applied to the wrong object. Reading PR **#17** — the sweep that
closed 98 alerts — its own table lists `@tanstack/start-server-core` among the
packages overridden **to close an alert**:

```
"@tanstack/start-server-core": ">=1.167.30 <2"     # 1 alert
```

That override *is* the lineage. It evicted `start-server-core@1.157.14` in favour
of `1.169.28`, which drags its own newer `start-client-core` / `router-core` /
`start-storage-context` into the tree alongside a `start-plugin-core` still
pinned at `1.157.14`. The mismatched plugin generated a server-fn virtual module
that resolved to nothing, and the SSR pass died:

```
[MISSING_EXPORT] "default" is not exported by "\0undefined".
  src/utils/locale.ts:1:1   import { createSsrRpc } from "@tanstack/react-start/ssr-rpc";
```

> **A defect *caused by* a remediation inherits that remediation's lineage.**
> Scope asks where the work came from, not whether the diff mentions a CVE.
> Fixing the collateral of an alert fix is finishing the alert fix — and
> declining it leaves the repo unable to verify the *next* one. That is the
> shape to check before writing "out of scope" again: ask which commit
> introduced the breakage and why that commit exists.

#### The fix: move the family up *inside* the ranges already declared

The declared deps were already `^1.157.14` — caret, so 1.17x was permitted the
whole time; only the lockfile held them down. No range was widened:

| package | before | after |
|---|---|---|
| `@tanstack/react-router` | 1.157.14 | **1.170.32** |
| `@tanstack/react-start` | 1.157.14 | **1.168.49** |
| `@tanstack/react-router-ssr-query` | 1.157.14 | **1.167.1** |
| `@tanstack/zod-adapter` | 1.157.14 | **1.167.0** |

The reason to key the change on `@tanstack/react-start` is that it **pins its
whole family exactly** (`start-server-core@1.169.31`, `start-plugin-core@1.171.39`,
`start-client-core@1.170.27`, …). So lockstep is *structural* — a property of the
package, not of a range someone hand-picked and has to keep re-picking. Prefer a
package that pins its family over an override per member.

The security floor is preserved: `start-server-core` resolves to **1.169.28 ≥
1.167.30**, so #17's remediation still stands.

Merged as `1bd57876` (PR #22, which also carried the h3 half:
`h3`/`h3-v2` bounded `>=2.0.1-rc.26 <3`, closing the bare-`>=` float the vault
notes had already flagged as a latent version bomb).

#### Verification, and one trap in reading it

| check | `main` before | after merge, on `main` |
|---|---|---|
| `pnpm typecheck` | exit 0 | exit 0 |
| `pnpm build` | **fails** in SSR pass | **exit 0** — client + SSR + nitro output |
| `biome check` | 1 error (`printer.ts`) | 1 error (`printer.ts`) — delta zero |

`src/routeTree.gen.ts` is regenerated by the newer router-plugin: **117 routes
before and after**, diff is import ordering only — checked, because a generated
file with 476 changed lines is exactly where a silent route loss would hide.

**The trap:** after `pnpm update`, `node_modules/.pnpm` still listed the entire
1.157.14 family beside the new one, which reads as "the skew is still there."
It was not — those were **orphaned directories**. The lockfile is the truth:
`grep -cE "@tanstack/…@1\.157\.14" pnpm-lock.yaml` → **0**, and `pnpm prune`
cleared the listing. Never diagnose a resolution from the `.pnpm` directory
listing; ask the lockfile.

#### Also measured, so nobody re-investigates

- `reactive-resume` overrides: 40 total, **1** still unbounded — `srvx: >=0.11.13`,
  which the vault notes record as a *deliberate* exception (0.11.15 and 0.12.5 both
  resolve; bounding it would downgrade one). Not a gap.
- `Project-DS`: all **16** overrides bounded, and they are genuinely **in effect** —
  `pnpm-lock.yaml` carries the `overrides:` block and `hono` resolves 4.13.3 ≥ the
  4.12.34 floor. The "overrides in their deprecated home" worry does not mean the
  remediation is fictional. Verified, not assumed.

#### The KPI moved the wrong way, for the one reason it always does

`deploy-check` after the merge: CI run **`skipped`** (publish gate), both tenants
**healthy HTTP 200** on an image built **2026-07-03** — **51 days behind `main`**,
one day worse than yesterday's 50, and it will be 52 tomorrow.

`dockerhub-pat-dead` is **day 8**. Re-measured independently rather than inherited:
both org secrets still read `created = updated = 2025-10-18T19:47Z`, untouched since
the run whose `Log in to DockerHub` step was rejected. **This session did not
re-text.** The daily ping for this UTC day had already gone out ~6 hours earlier,
and it is 03:19 local — a second ping for a known day-8 item is noise, not
escalation. POLICY requires *daily*, and daily was satisfied. Next due 08-25.

**Status: `EXHAUSTED` on alerts** — genuinely zero, re-swept per repo, with the
denominator confirmed at 39/39 rather than assumed. The estate's remaining gap is
not a dependency any more; it is one credential standing between verified fixes
and the containers actually running them.

— Harah

#### Addendum, same session — the last unbounded override in the estate (reactive-resume #25, `0d832e80`)

Having just spent the session repairing what a bare `>=` did, the obvious next
question was *how many more are there?* Swept `pnpm.overrides` / `overrides` /
`resolutions` across all 39 owned non-archived repos:

| repo | block | total | unbounded |
|---|---|---|---|
| `reactive-resume` | `pnpm.overrides` | 40 | **1** |
| `Project-DS` | `pnpm.overrides` | 16 | 0 |
| `Project-Jordyn` | `pnpm.overrides` | 15 | 0 |
| `Project-VoiceToColumn` | `overrides` | 3 | 0 |
| `Project-PasCam` | `overrides` | 2 | 0 |
| `Project-Evermore`, `Project-JA` | `pnpm.overrides` / `overrides` | 1 each | 0 |

Exactly one: `srvx: >=0.11.13`, which the vault notes recorded as a *deliberate*
exception. It was, and the reasoning was sound at the time — but it had gone
stale: **three** versions now resolve (`0.11.15`, `0.12.5`, `0.12.7`) where the
note recorded two. The float had already started.

Lineage checked before touching it — `git log -S` puts it in `251bb088`,
*"fix: remediate 30 Dependabot vulnerability alerts"*, so `>=0.11.13` is a
security floor.

**The interesting part is the fix that was rejected.** The obvious move was this
repo's own `minimatch@10` trick — versioned selectors `srvx@0.11` / `srvx@0.12`,
which would bound each line tightly without downgrading either. It was rejected:

> **A versioned override selector matches on the range a dependent *declares*,
> not on what resolves.** So a dependent declaring anything the selectors don't
> cover ends up matched by *no* override at all — silently losing the security
> floor for that edge. A tighter bound that can lose coverage is worse than a
> loose bound that cannot.

`>=0.11.13 <1` keeps the floor on every edge, lets 0.11 and 0.12 keep coexisting,
and still blocks the documented `basic-ftp` mode (a silent jump to a new major).
Verified as a pure guard: `pnpm typecheck` 0, `pnpm build` 0, and the srvx
resolution map **byte-identical** before and after (49 × 0.11.15, 2 × 0.12.5,
2 × 0.12.7) — the lockfile diff is 2 lines, both the recorded override string.

**The estate now has zero unbounded override ranges.**

Deploy-check after this merge, as after the last: CI `skipped` (publish gate),
both tenants healthy HTTP 200, **51 days behind `main`**. Unchanged and
unchangeable until the credential is rotated.

— Harah

### 2026-08-24 (resolver loop, run 3, session 1) — the board is zero for the third run, and the thing that was lying was the health check

Re-derived from live data before touching anything. The handoff held, and this
time it was corroborated from a second direction rather than just re-counted:

| | |
|---|---|
| org endpoint (`/orgs/lxrbckl-labs/dependabot/alerts?state=open`) | **0** |
| per-repo sweep, all 39 owned non-archived repos | **0** open, **0** alert-disabled (39/39 `ON`) |
| **alerts ever recorded across those 39 repos** | **1022** |
| open dependabot PRs, estate-wide | **0** |
| open human PRs touching security | 2, both already superseded and commented |

The 1022 is the number worth keeping. "Zero open" on its own is equally
consistent with *nothing is wrong* and *nothing is looking*; 1022 historical
alerts against 0 open says the detector demonstrably works on these repos and
has been driven down, which is a different and much stronger claim.

#### The session's find: `doctor` called a wrong-branch checkout healthy

This checkout — the one all six launchd routines run from — was sitting on
**`docs/srvx-bound`**, a feature branch merged as #44. `git pull --ff-only`
failed on arrival with *"Not possible to fast-forward"*, which is how it was
noticed at all.

`doctor.sh` measured only `rev-list HEAD..origin/main --count`. It never asked
which branch `HEAD` was on, and the two failure modes that follow were both
reproduced in a scratch repo:

| checkout state | old output | truth |
|---|---|---|
| on a branch **with commits** (session died mid-work) | `✓ checkout current with origin/main` | **silent false green** |
| on a **merged** feature branch | `⚠ N behind — git pull` | remedy cannot work; `git pull` fails |
| detached HEAD | unhandled | — |

The false green is the dangerous one, and it is not hypothetical: resolver
sessions create branches as a matter of course, and any session that ends
without returning to `main` leaves the checkout on one. `HEAD..origin/main`
then reads `0`, doctor prints `✓`, and every routine runs that branch's code.

> **"Behind" is meaningless until you know which branch you are on.** A
> distance measured from an unidentified point is not a health check. This is
> the third *liveness is not function* in this repo's history and the second
> time a mis-parked checkout has quietly degraded the loop — and note that the
> 2026-08-23 entry already recorded "the reason the loop was stuck was a stale
> checkout" without anything being changed to *detect* the next one. Recording
> a failure is not the same as instrumenting it.

Fixed in **#45** (`024f389`): branch identity first, detached HEAD named, and
the remedy given is the one that actually works. Verification was constructed
per this repo's own 2026-08-18 rule — `bash -n` across all of `skill/` exit 0;
a five-state matrix run against the **real** block extracted from `doctor.sh`
by `sed` rather than a re-typed copy (the `dispatch-selftest.py` discipline, so
the test cannot drift from the code); a live run that correctly flags its own
working branch at 0-behind/0-ahead — precisely the case the old code called
`✓`; and `dispatch-selftest.py` exit 0 as regression.

Scope, stated plainly rather than dressed up: **no Dependabot lineage, and none
claimed.** Tooling maintenance under POLICY's own-backlog clause, on the
precedent of #40 under an identically empty board. The lineage-stretching move
would have been to invent an alert connection; the honest one is to say it is
machinery work and let the record show that.

#### A measurement trap, caught mid-sweep

Checking whether "0 open" might be masking repos where Dependabot is enabled but
sees no manifests, the first sweep queried `?state=all` and returned **`ever=0`
for all 39 repos** — including Jordyn and reactive-resume, which provably had 42
and 98 alerts closed days earlier.

> **`state=all` is not a valid value for the Dependabot alerts API, and it does
> not error — it returns `[]`.** Omit the parameter to get full history. An
> invalid filter that answers "nothing" instead of "bad request" will confirm
> whatever you were afraid of, and the only reason it was caught here is that
> the result contradicted a fact this session already knew. Sanity-check a sweep
> against a repo whose answer you know before believing the other 38.

#### The one outlier, measured instead of assumed

`Project-Evermore`: 630 packages in the dependency graph, **zero alerts ever** —
the only substantial repo with no history (DS 528, Jordyn 605, Fabricator 958,
reactive-resume 1604 all have plenty). Alerts enabled (`204`), automated security
fixes on, graph populated, actively pushed 08-23. So either it is genuinely clean
or detection is dark on it, and those need distinguishing.

Read its manifest: `next@16.3.1`, `react@19.2.8`, `nodemailer@9.0.5`,
`drizzle-orm@0.45.2`, `typescript@^7.0.2`. It is a *current* repo. Zero is real.
Recorded so the next session does not re-open it as a suspected blind spot.

#### The KPI, and why it moved the wrong way again

| repo | days behind `main` | CI on last merge |
|---|---|---|
| `reactive-resume` | **51** | `skipped` (publish gate) |
| `Project-VoiceToColumn` | **50** | `skipped` |
| `Project-Jordyn` | **15** | `skipped` |

All three serving HTTP 200 on stale images. `dockerhub-pat-dead` is **day 8**,
re-measured independently rather than inherited: both org secrets still read
`created = updated = 2025-10-18T19:47Z`.

New this pass — the workflow itself was read rather than assumed about.
`lxrbckl-labs/.github`'s `dockerhub-build-push.yml` hard-wires
`docker/login-action@v3` to `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` and builds its
push tags from the username, so **there is no repo-level change and no Harah-side
action that routes around the credential.** The block is real and total.

Which raises the thing worth handing to the next session: eight days of texting
*"rotate the PAT"* has produced no movement. The workflow could publish to
**ghcr.io using the built-in `GITHUB_TOKEN`**, needing no DockerHub credential at
all. That is deliberately **not** done here — it changes where Alex's images live
and what watchtower pulls, it is outward-facing and irreversible-ish, and it has
no alert lineage. It is a proposal for Alex, not an unattended act. But offering
a second option is more useful than repeating the same ask a ninth time, and it
is now recorded in the registry's ping note.

#### Deliberately not done

- **No re-ping.** The 09:00 heartbeat fired today carrying "operator-blocked
  items open", and the prior session's dedicated ping went out earlier this same
  UTC day. Daily was satisfied; a third message for a known day-8 item is noise.
- **`summons-authority-conflict` left alone.** It needs Alex's word, there is no
  live summons to act on, and both drill comments stay in `mentions-state.json`'s
  seen-set — re-arming a dispatch to perform the contested act would launder the
  conflict rather than resolve it (the 08-24 session-1 reasoning still holds).
- **No supersession comments re-posted** on Jordyn #16 / reactive-resume #15.
  Both already carry signed Harah comments (latest 08-23) and POLICY dedupes
  across passes. Their alerts are long since banked to zero.

**Status: `EXHAUSTED` on alerts** — zero, swept per-repo, denominator confirmed
at 39/39, and corroborated against 1022 historical alerts rather than taken on
faith. What stands between verified fixes and production is still one credential.

— Harah

### 2026-08-24 (resolver loop, run 4, session 1) — the alert board was zero and the repo was still on fire: a CI marker that never worked, and a `main` broken by three good merges

The alert re-derivation came out where the last three runs did, and this time it
is genuinely uninteresting:

| | |
|---|---|
| org endpoint (`/orgs/lxrbckl-labs/dependabot/alerts?state=open`) | **0** |
| per-repo sweep, all 39 owned non-archived repos | **0** open, **0** dark |
| open dependabot **PRs** at session start | **5** |

That last row is the point. **Zero alerts is not zero work, and the two are
measured by different endpoints.** `Project-Evermore` — the repo the 08-24 run 3
entry had cleared as "genuinely clean, 630 packages, zero alerts ever" — had five
dependabot version-update PRs opened at 19:07–19:09 UTC, about ninety minutes
before this session started. A session that only reads the alerts API sees an
empty board and stops. POLICY's scope clause covers this: lineage is "a specific
Dependabot alert **or** dependabot-authored PR", and the PR half is the half that
had work in it today.

#### The find: `[e2e]` had never worked on a pull request

Evermore's CI decides how much of its e2e suite to run from the **head commit
message** (`docs/ci.md`: nothing → `@smoke`, `[e2e]` → everything). The four
patch/minor bumps arrived with green ticks, and the ticks were nearly worthless:
dependabot's commit messages carry no marker, so each had run **8 smoke tests,
about 20 seconds** — on `next`, `shadcn`, `lucide-react` and `maplibre-gl`, which
are the framework, the UI primitives, every icon, and the map. `docs/ci.md` says
in as many words that shared changes take `[e2e]`.

So the first branch carried `[e2e]`. The run summary answered:

> **Why:** no marker — the default is smoke

> **On a `pull_request` event, `actions/checkout` checks out the MERGE commit,
> whose message is `Merge <sha> into <sha>`.** The plan job read that with
> `git log -1`, found no marker, and correctly applied the default. Every
> pull request in that repository had been doing this since the feature
> existed — `[e2e]`, `[e2e:<segment>]` and the opt-out were all inert on PRs
> and only ever worked on a direct push to `main`.

This is the repo's own stated nightmare — *"a green tick for a run that tested
almost nothing"* — arriving through the one door it had not checked. It had made
a **misspelled** segment fail loudly; a **silently discarded** marker was free,
and it hit every PR rather than the occasional typo.

Fixed in **#22**: the plan job checks out
`${{ github.event.pull_request.head.sha || github.sha }}`. The `check` and `e2e`
jobs deliberately keep checking out the merge result — only the job that reads
*intent* wants the head commit. It also now prints **which commit it read** into
the summary, because the whole failure had been visible the entire time as one
line of prose nobody had reason to re-read.

**The fix caught itself in its own trap, which is the part worth keeping.** Run
`8f69ac0` read the head commit correctly — and reported `the commit asked to
skip`. That commit's message *explains* the markers, and spelled the opt-out one
in brackets while doing so. The parser matches anywhere in the message (which is
what lets the marker sit where it reads best) and opting out wins over
everything, so the commit repairing the control surface used it to switch itself
off, in the run meant to prove the repair.

> **A commit message about the syntax is indistinguishable from one using it.**
> Documented in `docs/ci.md` with the way out: name the markers in words, or put
> the discussion in the PR body, which nothing parses.

The follow-up commit then became the demonstration: `the commit asked for
everything`, **182 tests per engine** against the 8 it would have run before.

#### The bigger one: `main` was broken, and three correct merges did it

Mid-session, `next`, `lucide-react` and `shadcn` were squash-merged straight to
`main` from #19, #18 and #17 — at 21:26:10, :13 and :16, by `lxRbckl`, unsigned
(POLICY's authorship test: not Harah's, and not the grooming routine either, whose
log was silent since 04:30). Six seconds, three PRs, each touching
`pnpm-lock.yaml`.

```
ERR_PNPM_BROKEN_LOCKFILE  the lockfile is broken: duplicated mapping key (1979:3)
```

`baseline-browser-mapping@2.11.17` appears twice, as an entire duplicated block.
Each PR was individually fine and individually `MERGEABLE`; GitHub merged each
one's lockfile as **text** against a base the previous merge had already moved.
Git resolved it without a conflict marker. YAML did not survive.

> **A lockfile is generated output. Merging two generated files line by line can
> produce a file neither generator would ever emit — and `MERGEABLE`/`CLEAN`
> is not evidence otherwise, because git is diffing text and knows nothing about
> the invariants.** Take one side wholesale and re-run the generator.

Measured rather than inferred, because "main is broken" deserves proof:

- `main`'s own CI for the #17 push — **failure at 21:26:19**, at
  `pnpm install --frozen-lockfile`. Red from that moment.
- dependabot's rebase runs for #16 and #20 — **both failed**, same cause. That,
  not anything about maplibre-gl or zod, is why both went `DIRTY`.
- a `workflow_dispatch` of `@a11y`/webkit against `main` as a control —
  **failed at the gate, e2e skipped.** Nothing on `main` could build or be tested.

That control run is also the method note: **when a branch fails and you cannot
tell whether it is yours, dispatch the same job against `main`.** It cost one
run and turned "is my zod branch broken?" into "`main` cannot install", which was
a different and much more urgent question.

`main` was repaired by **#21**, whose lockfile was pnpm-regenerated rather than
hand-merged. Confirmed after: `main`'s lockfile parses, and `main`'s own
full-suite run passed **both engines**.

The same trap was then declined a second time. GitHub reported the zod branch
`MERGEABLE`/`CLEAN` against the repaired `main` — which meant precisely that git
was willing to splice the two lockfiles again. `main`'s lockfile was taken
wholesale and the single bump re-applied with pnpm instead.

#### One failure that was not ours, established rather than waved off

The zod branch failed `a11y.spec.ts:362 › the dialogs are clean @a11y` on webkit
— a `color-contrast` violation, on the retry too. A validation library the app
never imports cannot reach a CSS contrast measurement, but "that can't be it" is
not evidence, so:

| run | result |
|---|---|
| zod branch, same base, first run | **failed** (twice) |
| zod branch, same commit, re-run | passed (`✓ 9.0s`) |
| maplibre branch, identical base | passed |
| zod branch, previous base | passed |

Same commit and same base producing both outcomes is the definition of flaky.

**Then it hit `main` itself**, after the zod merge — same test, both attempts —
so "flaky, move on" stopped being good enough and it got measured properly.
Seven observations of that test on today's code:

| shape | a11y dialogs |
|---|---|
| full suite (182 tests) × 5 runs | **failed 2**, passed 3 |
| `@a11y` alone (14 tests) × 2 dispatches | passed 2 |

> **Both failures are in full-suite runs; every isolated `@a11y` run passes.**
> That points at suite load, not the assertion: axe scanning a dialog whose open
> transition has not settled reads low contrast, and a loaded runner is exactly
> when that window widens.

And the reason it is surfacing *now* is the same bug this session fixed — before
#22 the marker did not work on PRs, and dependabot's own merge commits carry no
marker either, so **`@a11y` had hardly run at all recently.** Almost certainly a
long-standing defect the repaired marker has merely made visible; expect more of
these now that the full suite actually runs.

Filed as `Project-Evermore` **issue #24** with the run table, and deliberately
**not fixed**: no Dependabot lineage, so under POLICY's scope clause it is not
Harah's to change. `main`'s gate (typecheck + build) is green; what is red is one
intermittent a11y assertion.

Recorded by name because an unnamed flake gets re-diagnosed from scratch every
time: it lives in webkit's contrast measurement, next to the known
`admin-keys` / `data-limits` pair.

#### What landed

| PR | what | verification |
|---|---|---|
| **#22** | plan job reads the PR head commit; footgun documented | 182 tests/engine where the same branch had run 8 |
| **#21** | maplibre-gl 6.5.0 (#16) — **and the `main` repair** | chromium 182/182; webkit 156p/24s/2 flaky |
| **#23** | zod 3 → 4 (#20) | chromium 182/182; webkit 157p/24s/1 flaky, incl. `@mcp` |

zod 3 → 4 was a major, so it was migrated — and the migration was **empty**. One
file imports zod, every construct is v4-clean, and `z.record` was already
two-argument. The work was proving it: the MCP SDK declares `^3.25 || ^4.0`; two
zod copies survive but the second is `shadcn`'s CLI, while the app and the SDK
instance the app imports resolve to **one** `zod@4.4.3` directory — checked by
resolving from both sides and comparing paths, because zod's classic failure is
an `instanceof` across duplicate copies.

Dependabot #16 auto-closed; #20 was closed with a signed comment.

#### Deployment, and the one thing that is not blocked

`deploy-check/verify.py lxrbckl-labs/Project-Evermore` → **`unknown repo`**, correctly:
Evermore has no container on this mini and no `targets.json` entry — Phase 6
(Docker + Caddy) is still the repo's outstanding work per its vault notes. So for
once there is **no "merged, not deployed" gap to report, and no publish**, which
means `dockerhub-pat-dead` does not touch any of today's work. It remains open
at **day 8**; the daily ping for this UTC day was already satisfied before this
session (09:00 heartbeat plus an earlier dedicated ping), and the registry's own
note has the next one due UTC-day 08-25 with the ghcr.io alternative to offer.

#### For Alex — one thing outside Harah's authority

`main` went red at 21:26 and stayed red until a Harah merge repaired it, because
nothing gates a merge on the CI gate passing. **Branch protection requiring
`Typecheck and build` on `Project-Evermore` would have refused #18 and #17
outright.** POLICY authorises enabling Dependabot alerts on owned repos and
nothing else in settings, so this is a recommendation, not an action taken.

The narrower habit worth having regardless: **merge lockfile PRs one at a time,
letting each rebase**, or land them as one regenerated change-set. Three good PRs
merged six seconds apart is all it took.

**Status: `EXHAUSTED`.** The line above originally read `MORE_WORK`, on the
stated ground that the estate had not been re-swept since these three merges.
That ground was then discharged rather than left standing: a full post-merge
re-sweep of all 39 owned non-archived repos returns **0 open alerts and 0 open
dependabot PRs**, and dependabot #16 auto-closed while #20 was closed with a
signed comment. Nothing actionable remains.

What remains is not actionable by Harah, and is listed so the next session does
not re-open any of it as work:

- **`Project-Evermore` `main` is red on the intermittent a11y contrast
  assertion** (issue #24). Gate is green. No Dependabot lineage, so out of scope
  under POLICY's scope clause — filed, not fixed.
- **`dockerhub-pat-dead`**, day 8, re-confirmed at 22:41Z (both org secrets still
  `created = updated = 2025-10-18T19:47Z`). Untouched by this run, which was
  publish-free. Next dedicated ping UTC-day 08-25, and it should name the
  ghcr.io alternative.
- **`summons-authority-conflict`** — still needs Alex's word.
- **Branch protection on `Project-Evermore`** — a recommendation; POLICY does not
  authorise the settings change.

Corrected in the same session that wrote it, because a stale status line in the
board of record is exactly the drift this file exists to prevent.

— Harah

### 2026-08-25 (resolver loop, run 5, session 1) — zero alerts *and* zero dependabot PRs, so the work was the two things the empty board was hiding

The board is zero for the fifth run, and this time both halves were measured,
because run 4 established that they are different endpoints and only one of them
was empty for an interesting reason:

| | |
|---|---|
| org endpoint (`/orgs/lxrbckl-labs/dependabot/alerts?state=open`) | **0** |
| per-repo sweep, all 39 owned non-archived repos | **0** open, **0** dark |
| open dependabot **PRs**, swept per-repo across all 39 | **0** |
| open PRs by any author | 8, all human-authored |

Authorship was checked by signature, not login, with both controls in the same
batch (POLICY: `author: lxRbckl` proves nothing). Of the 8 open PRs exactly one
is Harah's — `Project-Harah` #11, the retrospective — and the controls behaved
(`reactive-resume` #22 → 1, `Project-Evermore` #21 → 1). `lxRbckl/.claude` #39 is
authored by **`aarbuckle2`, the work account**: a hard stop, not read, not
touched.

**The zsh word-splitting trap caught this session too**, on the first try, in a
loop this file already warns about twice. `for r in $TARGETS` over a
space-separated string sent all sixteen repo names to `gh` as a single argument
and returned one 404. It is worth being blunt in the note, since warning prose
has now failed three sessions running: **in zsh, write the list as an array —
`targets=(a b c); for r in "${targets[@]}"` — never as a string you expect to
split.**

#### The gap the empty board was hiding: alerts were on everywhere, remediation was not

Every previous run measured *alert coverage* — 39/39 enabled, 0 dark — and
reported the estate as fully covered. That measured one of the two switches.
Dependabot has a second, independent one, **security updates**
(`/repos/{repo}/automated-security-fixes`), which is what actually opens the
remediation PR when an alert fires. Measured this pass:

| | |
|---|---|
| alerts enabled | **39 / 39** (as reported for days) |
| security updates enabled | **23 / 39** |

Sixteen repos could see a vulnerability and had no way to propose the fix —
including three that serve live traffic on this mini: **Project-DS,
Project-Showalter, Project-VoiceToColumn**. On those repos the loop's first
automated step did not exist, and an alert would have sat silent until a resolver
session happened to look.

Enabled on all sixteen (POLICY, *Repo security settings — visibility is
authorized*: additive only, and explicitly in scope). `PUT` returned 204 for each;
re-reading `.enabled` across all 39 afterwards returns **enabled=39, disabled=0**.
This closes no alert today — there are none — which is exactly why it went
unnoticed for weeks.

> **"Coverage" is two switches, not one.** `vulnerability-alerts` is the sensor;
> `automated-security-fixes` is the responder. A repo with the first and not the
> second reports as covered by every check this project was running, and is
> silently manual. Measure both, and say which one you measured.

#### The other thing an empty board hid: the panel was not showing the work

POLICY's reporting rule has said since 2026-08-23 that every resolver merge,
resolution and publish must appear in the dashboard's Repo Grooming panel *"so
the dashboard shows what Harah fixed without anyone reading logs"*, and names
building it as **Harah's own first-priority backlog item** if the panel does not
render them. It did not.

`/api/grooming` had been returning a `resolver_actions` array for days — **27
actions, 169 closed alerts**. The panel read only the `merged` / `queued` half,
which `groom.sh` writes from open dependabot **PRs**. There are none, so both
arrays are empty and the panel displayed:

> All repos current — nothing to merge or review.

directly over the complete record it had already fetched and was throwing away.
Fixed in **#49**.

> **An empty panel is ambiguous in a way an empty list is not.** "Nothing to
> show" and "showing nothing" render identically. The wording was also doing
> damage — `groom.sh` measures *"no open dependabot PRs"*, and the panel
> generalised that to *"all repos current"*, a much larger claim it had no
> evidence for. It now says what it measured.

Two implementation notes worth keeping. **The state file holds two generations of
writer** — older actions carry `merged_commit` / `deployed` / `days_behind_main` /
`by`, newer ones `merge_commit` / `deployed_or_days_behind` / `lineage` — so
every field past `kind` and `repo` is optional and the panel normalises both,
including parsing the days-behind number back out of the newer prose form. And
an **unrecognised `kind` still renders** with its raw label: the failure being
fixed here is a record silently not appearing, and a strict `kind` map would have
rebuilt that same failure one schema change later.

**Verification, and the part `tsc` cannot do.** Delta vs `main`, both sides in the
same pass: `npm run build` (`tsc -b && vite build`) exit 0 / exit 0; `npm run
lint` (`oxlint`) exit 0 / exit 0 with the same single pre-existing
`App.tsx:133` warning. That proves types, not rendering — so the panel was driven
in **headless chromium against the live dashboard on this mini**, serving the
real `/api/grooming`: 1 matching panel, **27 rows for 27 actions**, 26 PR links
(the one `coverage`-kind action has `pr: null` and correctly renders without one),
**zero console errors**. Post-merge, rebuilding from `main` produced the
**identical asset hash** (`index-vjvQJ9_3.js`), so the bundle exercised in the
browser is byte-identical to what `main` builds.

Playwright is not installed in this repo; the `scout` skill's `node_modules`
already has it and a throwaway harness placed **inside that `node_modules`**
resolves it (Node resolves from the script's path, not `cwd` — the same trick this
file records for the puppeteer replay). Deleted after use.

#### Deployment — and one merge that genuinely did ship

`deploy-check/verify.py` on all four served targets, measured today:

| target | days behind `main` | live |
|---|---|---|
| `reactive-resume` | **51** | both tenants HTTP 200, image 2026-07-03 |
| `Project-VoiceToColumn` | **50** | HTTP 200, image 2026-07-03 |
| `Project-Jordyn` | **15** | HTTP 200, image 2026-08-08 |
| `Project-Showalter` | **35** | `unhealthy` — pre-existing, not today's |

Every one of their CI runs concluded `skipped` at the publish gate, and all four
are gated on `dockerhub-pat-dead`, **day 9**, org secrets still
`created = updated = 2025-10-18T19:47Z`.

**#49 is the exception, and it is worth being precise about why:** the dashboard
is not in the DockerHub path at all. It runs as the launchd job
`com.lxrbckl.servermanager-dashboard` and FastAPI serves `web/dist` from disk, so
`verify.py` correctly answers `unknown repo` and the change was live the moment
it was built. Confirmed by function and not just liveness, per this file's own
rule: `/api/health` 200, **`/api/containers` → 35 containers** (Docker
reachability), `/api/grooming` serving the actions.

#### The ping, and a note on repeating oneself

The dedicated OPERATOR-BLOCKED ping for UTC-day 2026-08-25 was sent, and per the
registry's own standing instruction it named the **ghcr.io alternative** for the
first time: the shared workflow could publish to GitHub Container Registry with
the built-in `GITHUB_TOKEN` and need no DockerHub credential at all. Stated
explicitly as Alex's infrastructure decision — it changes where images live and
what watchtower pulls — and therefore **not** something Harah executes
unattended.

Recorded for the next session, because it is a judgment about the ask rather than
the credential: **if a tenth repetition also produces nothing, stop re-sending the
same two options daily and put it to Alex as a yes/no choice between them.** Nine
identical asks is a signal about the ask.

**Status: `EXHAUSTED`.** Both halves of the board are zero and were re-swept
per-repo after the merge. What remains is not actionable by Harah:

- **`dockerhub-pat-dead`**, day 9 — the only thing between the merged estate and
  a deployed one, and the reason four targets sit 15–51 days behind `main`.
- **`summons-authority-conflict`** — still needs Alex's word.
- **`Project-Evermore` `main`** red on the intermittent a11y contrast assertion
  (issue #24, no Dependabot lineage — filed, not fixed) and **branch protection
  on that repo**, a recommendation POLICY does not authorise Harah to apply.
- **`Project-Harah` #11**, Harah's own retrospective, left open deliberately.
  Its history holds up; its "still blocked" paragraph did not, so it now carries
  a signed comment correcting the four claims rather than being quietly merged.

— Harah
