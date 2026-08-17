# Repo grooming — the written policy (read before ANY merge decision)

Moved verbatim from SKILL.md 2026-08-16 (token audit); this file is the
authority. The core SKILL.md summary does not license a merge on its own.

**Standing merge authorization (Alex, 2026-08-15) — the carve-out from the
global "merges only on my explicit word" rule, scoped EXACTLY to this:**

- Repo is owned by `lxRbckl` or `lxrbckl-labs`, not archived, and the PR
  author is dependabot.
- The bump is **patch or minor** (never major), parsed from the PR title.
- **No prerelease on either side** — any version with a `-beta`/`-rc`/etc.
  tag disqualifies auto-merge. Prerelease transitions (beta→stable,
  beta→rc) routinely smuggle breaking changes behind a small-looking
  version delta (learned 2026-08-15: better-auth 1.5-beta→1.6.2 removed a
  core plugin and changed its DB schema).
- Checks, if the repo has any, are **passing** — a failing or errored check
  disqualifies. No-CI repos may merge on the version rule alone.
- Anything else — major bumps, failing checks, conflicts, non-dependabot
  authors — is **never auto-merged**: it stays open and gets reported.

**PR resolution — the left-hand-dev mandate (Alex, 2026-08-15).** Harah
does not stop at triage: queued dependabot PRs (major bumps, merge
conflicts) are Harah's to RESOLVE. In a session acting as Harah: read the
repo's vault dev notes first, check out the PR branch, do the real work —
resolve conflicts, apply the migration (read the changelog/breaking
changes), fix callers — then run the repo's own verification (tests /
typecheck / lint / build, whatever exists). **When verification passes,
Harah merges on its own authority** — the carve-out extends to
resolved-and-verified dependabot PRs of any bump size, provided ALL of:
work happened on the PR branch and is pushed; the repo's verification
actually ran and passed (never merge unverified); the trail is signed
(resolution comment `Resolved & verified: <what>. — Harah` before
merging); and the post-merge deployment check below follows. A resolution
that can't reach passing verification gets pushed as far as it got, a
signed comment explains what's stuck, and it goes back in the queue for
Alex.

Nothing in this carve-out extends to non-dependabot PRs, any repo Alex
does not own, or merging without verification. When in doubt, queue it
for Alex.

**Harah-authored remediation PRs are in scope (Alex, 2026-08-16):** "get all
the alerts resolved — that's your issue now." Most Dependabot *alerts* have no
dependabot *PR* behind them (no version-update config, or no published fix in
a matching range), so closing them means branches Harah authors itself. Those
PRs carry the **same authorization and the same gates** as a resolved
dependabot PR — repo owned by `lxRbckl`/`lxrbckl-labs`; work done on the branch
and pushed; **the repo's own verification actually ran and passed**; signed
`Resolved & verified: <what>. — Harah` comment before merging; post-merge
deployment check after. Nothing else widens: still no human-authored PRs, no
repos Alex doesn't own, and **never a merge without passing verification**.
This is the scheduled resolver's authority (`../resolver/`) as much as a
hand-run session's.

**Cadence is not authority (2026-08-16).** The alert-watch routine
(`../alerts/`) changes how *often* grooming runs — up to every 6h when
critical alerts are open — by rewriting the launchd schedule via
`set-cadence.sh`. That is a scheduling change and nothing more. It does not
enlarge this carve-out by a single PR: the same author, bump-size,
prerelease, and check rules apply on an escalated pass exactly as they do on
the daily one. An agent that reads "we're in critical mode" as license to
merge something this policy would otherwise queue has misread it.

**Reporting:** merged (list), queued-for-Alex (list, with why), errors —
honestly. Each queued PR also gets one signed explanatory comment on
GitHub (`Queued for Alex: <reason>… — Harah`) — once per reason, deduped
across passes, never in dry runs — so the PR explains itself when Alex
opens it. Every pass writes machine-readable state to
`~/.harah/grooming-state.json`; the dashboard renders it (`/api/grooming`
→ the **Repo Grooming** panel).

**Signature (standing instruction, Alex 2026-08-15):** whenever Harah
writes something others will read out of context — a PR comment, an issue
comment, a PR body, a commit that isn't a plain merge — it signs with its
name so the reader knows which agent acted: end with `— Harah` (e.g.
`Queued for Alex: major bump. — Harah`). Applies to the grooming routine
and to any session acting as Harah. Don't sign chat replies to Alex —
only outward artifacts.

**How the check is actually run (Alex, 2026-08-17):** don't hand-roll it —
run **`../deploy-check/verify.py <owner/repo>`** after every merge. It walks
merge → CI run → image → container → a real HTTPS request, and encodes the two
traps that made earlier reports wrong:

- **A merge does not deploy. A `publish` commit does.** The shared workflow
  builds only when the head commit message starts with `publish`. An ordinary
  merge produces **no image**, so "merged and verified healthy" is true and
  totally misleading — healthy because nothing changed. Note a run can conclude
  `success` while its only job was *skipped*; read the job conclusions.
- **A run with `jobs.total_count = 0` never started a job** — GitHub could not
  resolve the workflow (the `lxrbckl-dev` org-rename signature on
  `reactive-resume`). That is not a build failure and must not be reported as one.

The script also compares the running image against `main`'s newest commit and
says how many days behind the live code is. **Report that number.** As of
2026-08-17: Project-Jordyn 9 days behind, reactive-resume 44 days behind — both
serving 200 on old images. Alerts closed on GitHub are not fixes in production
until the image rolls.

**Publishing is NOT covered by any carve-out.** Harah may merge under this
policy; it may not push a `publish` commit or otherwise trigger a deploy without
Alex's explicit word for that deploy. Report "merged, not deployed, N days
behind" and let him choose when to ship.

**Post-merge deployment check (standing instruction, Alex 2026-08-15):**
after grooming merges land in a repo AND a deployment inherits them (the
mini pulls/rebuilds, or its next scheduled deploy runs), **verify the
affected running application**: is the container/service up, healthy, and
serving (dashboard, `docker ps`, health endpoint, or a real request)?
Notable changes are acceptable *because* this check follows them. If a
groomed repo maps to something running on the mini and the deployment
hasn't inherited the merge yet, say so explicitly — "merged, not yet
deployed" is a state Alex needs to see, not silence. A failed post-merge
check gets reported immediately with the suspect bump named.
