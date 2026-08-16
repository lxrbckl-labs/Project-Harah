#!/usr/bin/env python3
"""Collect open Dependabot alerts across Alex's owners and decide grooming cadence.

READ-ONLY against GitHub. This routine never merges, comments, or writes to any
repo — it only reads alerts and writes local state. The only thing it *changes*
is how often the grooming routine runs (via grooming/set-cadence.sh); it never
widens what grooming is allowed to merge. That gate stays exactly where
grooming/POLICY.md put it.

Why it exists: groom.sh sees only open dependabot *pull requests*. Alerts fire
whenever a vulnerable dependency is detected, whether or not a PR exists (no
version-update config, no fix available yet, or the PR was closed). On
2026-08-16 that gap was 3 PRs visible vs 100 alerts open.

State -> ~/.harah/alerts-state.json (rendered by the dashboard's Alerts panel).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

OWNERS_ORG = ["lxrbckl-labs"]
OWNERS_USER = ["lxRbckl"]

SEVERITIES = ["critical", "high", "medium", "low"]

# Cadence tiers: worst open severity -> how often grooming should run.
# Escalating means fixes land sooner, NOT that more things become mergeable.
TIER_BASELINE = ("baseline", None, "no critical or high alerts open")
TIER_HIGH = ("high", 43200, "high-severity alerts open")
TIER_CRITICAL = ("critical", 21600, "critical alerts open")

STATE = Path.home() / ".harah" / "alerts-state.json"


def gh(*args: str, timeout: int = 120) -> tuple[int, str, str]:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def parse_alert(repo: str, a: dict) -> dict:
    adv = a.get("security_advisory") or {}
    dep = a.get("dependency") or {}
    pkg = (dep.get("package") or {}).get("name") or "?"
    return {
        "repo": repo,
        "number": a.get("number"),
        "severity": (adv.get("severity") or "unknown").lower(),
        "package": pkg,
        "summary": (adv.get("summary") or "").strip(),
        "url": a.get("html_url") or f"https://github.com/{repo}/security/dependabot",
        "created_at": a.get("created_at") or "",
    }


def stream_alerts(path: str) -> tuple[list[dict], str | None]:
    """Return (alerts, error). error is a short reason string when unreadable."""
    code, out, err = gh("api", "--paginate", f"{path}?state=open&per_page=100",
                        "--jq", ".[]")
    if code != 0:
        low = (err or "").lower()
        if "disabled" in low:
            return [], "disabled"
        if "not found" in low or "404" in low:
            return [], "not-found"
        return [], (err or "unknown error").strip().splitlines()[0][:120]
    alerts = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            alerts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return alerts, None


def main() -> int:
    collected: list[dict] = []
    disabled: list[str] = []
    errors: list[str] = []

    # Org-wide endpoint: one call covers every repo in the org.
    for org in OWNERS_ORG:
        raw, err = stream_alerts(f"/orgs/{org}/dependabot/alerts")
        if err == "disabled":
            disabled.append(org)
            continue
        if err:
            errors.append(f"{org}: {err}")
            continue
        for a in raw:
            repo = ((a.get("repository") or {}).get("full_name")) or org
            collected.append(parse_alert(repo, a))

    # Personal account has no aggregate endpoint — iterate its repos.
    for user in OWNERS_USER:
        code, out, err = gh("repo", "list", user, "--no-archived", "--limit", "200",
                            "--json", "nameWithOwner", "--jq", ".[].nameWithOwner")
        if code != 0:
            errors.append(f"{user}: repo list failed")
            continue
        for repo in [r.strip() for r in out.splitlines() if r.strip()]:
            raw, err2 = stream_alerts(f"/repos/{repo}/dependabot/alerts")
            if err2 == "disabled":
                disabled.append(repo)
                continue
            if err2 == "not-found":
                continue
            if err2:
                errors.append(f"{repo}: {err2}")
                continue
            for a in raw:
                collected.append(parse_alert(repo, a))

    # Diff against the previous pass to find genuinely NEW alerts.
    prev: dict = {}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text())
        except Exception:
            prev = {}
    seen_before = set(prev.get("seen") or [])
    keys = {f"{a['repo']}#{a['number']}" for a in collected}
    new_alerts = [a for a in collected if f"{a['repo']}#{a['number']}" not in seen_before]
    # First run has no baseline — everything would look "new", which is noise.
    first_run = not seen_before
    if first_run:
        new_alerts = []

    sev_rank = {s: i for i, s in enumerate(SEVERITIES)}
    new_alerts.sort(key=lambda a: (sev_rank.get(a["severity"], 9), a["repo"]))

    totals = {s: sum(1 for a in collected if a["severity"] == s) for s in SEVERITIES}
    totals["open"] = len(collected)

    by_repo: dict[str, dict] = {}
    for a in collected:
        r = by_repo.setdefault(a["repo"], {"repo": a["repo"], "open": 0,
                                           **{s: 0 for s in SEVERITIES}})
        r["open"] += 1
        if a["severity"] in r:
            r[a["severity"]] += 1
    repos = sorted(by_repo.values(),
                   key=lambda r: (-r["critical"], -r["high"], -r["open"]))

    # Cadence decision.
    if totals["critical"] > 0:
        tier, interval, why = TIER_CRITICAL
        why = f"{totals['critical']} critical alert(s) open"
    elif totals["high"] > 0:
        tier, interval, why = TIER_HIGH
        why = f"{totals['high']} high-severity alert(s) open"
    else:
        tier, interval, why = TIER_BASELINE

    state = {
        "last_run": time.time(),
        "totals": totals,
        "new_since_last": new_alerts[:25],
        "new_count": len(new_alerts),
        "by_repo": repos[:12],
        "alerts_disabled": sorted(set(disabled)),
        "errors": errors,
        "first_run": first_run,
        "cadence": {"tier": tier, "interval_seconds": interval, "reason": why},
        "seen": sorted(keys),
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, STATE)

    print(f"open={totals['open']} critical={totals['critical']} high={totals['high']} "
          f"medium={totals['medium']} low={totals['low']} new={len(new_alerts)}"
          + (" (first run — baseline recorded, nothing flagged new)" if first_run else ""))
    for a in new_alerts[:15]:
        print(f"  NEW {a['severity'].upper():8} {a['repo']}#{a['number']}  {a['package']}  {a['summary'][:70]}")
    if disabled:
        print(f"  alerts DISABLED on: {', '.join(sorted(set(disabled)))}")
    for e in errors:
        print(f"  ERROR {e}")

    # Hand the cadence decision to grooming (idempotent; no-op if unchanged).
    setter = Path(__file__).resolve().parent.parent / "grooming" / "set-cadence.sh"
    if setter.exists():
        mode = "baseline" if interval is None else str(interval)
        r = subprocess.run(["bash", str(setter), mode, why],
                           capture_output=True, text=True)
        out = (r.stdout or "").strip()
        if out:
            print(out)
        if r.returncode != 0:
            print(f"  ERROR set-cadence failed: {(r.stderr or '').strip()[:160]}")
    else:
        print(f"  ERROR set-cadence.sh not found at {setter}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
