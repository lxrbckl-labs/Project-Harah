#!/usr/bin/env python3
"""Is everything Harah touches still serving? Runs every 10 minutes.

The gap this closes: Harah could merge, verify once, and walk away. Nothing
watched the apps afterwards. If a deploy — or anything else — broke a site at
03:00, the first anyone knew was Alex noticing. A custodian that can change
things must also notice when they break.

Deliberately NOT limited to "did Harah cause it". It checks every deployed
target in deploy-check/targets.json regardless of cause, because the honest
question is "is the estate healthy", not "am I to blame".

State -> ~/.harah/watchdog-state.json (rendered by the dashboard).
Transitions are what matter: it records when a target goes ok->down and
down->ok, so a long-broken thing doesn't shout every 10 minutes forever.

READ-ONLY. It never restarts, redeploys, or rolls back anything — it reports.
Recovery is a decision, and an unattended process guessing at one during an
outage makes things worse.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

TARGETS = Path(__file__).resolve().parent.parent / "deploy-check" / "targets.json"
STATE = Path.home() / ".harah" / "watchdog-state.json"
# Chronic failures that are understood and accepted, each with the REASON it is
# excluded from alerting. A suppression with no stated reason is how `showalter`
# sat unexplained for months (docs/dev-notes.md, 2026-08-25) — the dashboard
# renders these strings, so an entry here has to justify itself in the UI.
#
# The suppression covers the KNOWN failure only. See classify_container: a
# suppressed container that has stopped running entirely is a different failure
# wearing the same name, and it still reports.
KNOWN_BAD = {
    "showalter": "healthcheck dials http://localhost:5827/api/health, which "
                 "resolves to ::1 while the Next server binds IPv4-only, so it "
                 "can never pass. The app serves 200 on 127.0.0.1 and on "
                 "https://sawyer.showalter.business. Fix filed: Project-Showalter#91.",
}


def classify_container(name: str, status: str, code: int) -> dict:
    """One container's health, and whether its failure is the accepted one.

    Split out from main() so the suppression rule is testable without Docker —
    watchdog-selftest.py imports this exact function rather than a copy of it.
    """
    up = bool(status) and code == 0
    unhealthy = "unhealthy" in status.lower()
    ok = up and not unhealthy
    reason = KNOWN_BAD.get(name)
    # The suppression is narrow on purpose. It covers the accepted failure —
    # running but unhealthy — and nothing else. A known-bad container that has
    # stopped entirely has failed in a NEW way, and one that has recovered has
    # nothing left to suppress; keeping the flag on either would mean the target
    # we stopped watching is also the one that can never tell us it changed.
    suppressed = bool(reason) and up and not ok
    return {"name": name, "kind": "container", "ok": ok,
            "detail": status or "NOT RUNNING",
            "known_bad": suppressed,
            "known_bad_reason": reason if suppressed else None}


def summarize(targets: list, problems: list, prev_problems: list,
              transitions: list) -> str:
    """The one line watch.sh greps to decide whether this pass is worth logging.

    `UNHEALTHY` / `WENT DOWN` / `RECOVERED` are the words that put a pass in the
    log, so an unchanged problem must not print any of them — otherwise a single
    long-lived failure writes an identical line every ten minutes and buries the
    events the log exists for. That is not hypothetical: adding
    ds.lxrbckl.com (HTTP 502, awaiting a decision, not a repair) turned every
    pass into a logged one.

    The problem stays in `problems` and the estate stays `healthy: false` — this
    governs the LOG, not the truth. A changed problem set is news; the same set
    twice is not.
    """
    if not problems:
        return f"all {len(targets)} targets healthy"
    line = f"UNHEALTHY ({len(problems)}/{len(targets)}): " + "; ".join(problems[:6])
    if transitions or set(problems) != set(prev_problems):
        return line
    # Unchanged. Say it without the words that trigger a log write.
    return (f"steady: {len(targets) - len(problems)}/{len(targets)} serving, "
            f"{len(problems)} known problem(s) unchanged since the last pass "
            f"[{'; '.join(problems[:6])}]")


def sh(*args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except Exception as e:
        return 1, f"error: {e}"


def main() -> int:
    cfg = json.loads(TARGETS.read_text())
    prev, prev_problems = {}, []
    if STATE.exists():
        try:
            was = json.loads(STATE.read_text())
            prev = {t["name"]: t for t in was.get("targets", [])}
            prev_problems = was.get("problems", [])
        except Exception:
            prev, prev_problems = {}, []

    targets, problems, transitions = [], [], []
    for repo, t in cfg.items():
        if repo.startswith("_"):
            continue
        for c in t.get("containers", []):
            code, status = sh("docker", "ps", "--filter", f"name=^{c}$", "--format", "{{.Status}}")
            entry = classify_container(c, status, code)
            entry["repo"] = repo
            targets.append(entry)
            if not entry["ok"] and not entry["known_bad"]:
                problems.append(f"{c}: {entry['detail']}")
        for u in t.get("urls", []):
            code, out = sh("curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                           "--max-time", "20", u)
            ok = out[:1] in ("2", "3")
            targets.append({"name": u, "kind": "url", "repo": repo, "ok": ok,
                            "detail": f"HTTP {out or '000'}", "known_bad": False,
                            "known_bad_reason": None})
            if not ok:
                problems.append(f"{u}: HTTP {out or '000'}")

    # Only transitions are newsworthy; a target that has been down for hours
    # should not re-announce itself every pass.
    for t in targets:
        was = prev.get(t["name"], {}).get("ok")
        if was is None or t["known_bad"]:
            continue
        if was and not t["ok"]:
            transitions.append(f"WENT DOWN: {t['name']} — {t['detail']}")
        elif not was and t["ok"]:
            transitions.append(f"RECOVERED: {t['name']} — {t['detail']}")

    state = {
        "last_run": time.time(),
        "healthy": len(problems) == 0,
        "targets": targets,
        "problems": problems,
        "transitions": transitions,
        "checked": len(targets),
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)

    for line in transitions:
        print(line)
    print(summarize(targets, problems, prev_problems, transitions))
    # Non-zero only on a NEW failure, so the runner logs a quiet pass quietly.
    return 1 if any(t.startswith("WENT DOWN") for t in transitions) else 0


if __name__ == "__main__":
    sys.exit(main())
