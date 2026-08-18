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
| 1 | `reactive-resume` `extract-zip` | **no published fix exists** — advisory covers `<= 2.0.1` and npm `latest` *is* 2.0.1. Nothing to override to; not a version wall, a dead end. |
| 2 | `pytest` in `Project-ASBC` + `Project-RCoD` | first-party cap (see above) — needs `lxRbckl/lxRbckl` PR #1 merged **and published**, and publish is Alex's call per release. Merging #1 alone closes nothing, since consumers resolve from PyPI. |

**"Behind a human PR" is a real blocked state, not a cop-out** — but only after
you have checked the signature, because the same finding with the authorship
wrong is either a stalled fix or a crossed hard stop. The honest status here is
`EXHAUSTED`, and a session that closes zero alerts while saying so plainly is
worth more than one that banks 42 by overriding a pending question.

**Re-derived 2026-08-18 (resolver loop, session 1) — all five rows still hold**,
totals byte-identical (2 critical / 32 high / 26 medium / 6 low = 66). What was
re-measured from live data rather than carried over:

- `extract-zip` is a **dead end, confirmed at the registry**: npm `latest` is
  2.0.1, the advisory covers `<= 2.0.1`, and the package was last published
  **2023-03-04**. There is no version to override to and no reason to re-check
  it every run.
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

**`Project-ACLG` is ARCHIVED — its 2 open dependabot PRs are permanently out of
scope (2026-08-18).** A sweep for open dependabot PRs across the org turns it up
(#15 setuptools 82→83, #5 pytest 7.4.4→9.0.3, both `MERGEABLE`), which reads as
actionable until you check the repo state. POLICY's first condition is "not
archived", and GitHub refuses writes to an archived repo anyway; its alerts
endpoint returns **403 "Dependabot alerts are not available for archived
repositories"**, so it contributes nothing to the alert count either. Don't
re-investigate it — and note the 403 is *not* a permissions problem, despite
`gh` helpfully suggesting an `admin:repo_hook` scope refresh underneath it.

## Conventions

Ship a change = build if the frontend changed → `git add -A && git commit &&
git push`, **automatically, without being asked**. Outward-facing writes (PR and
issue comments, non-merge commits) are signed `— Harah`.
