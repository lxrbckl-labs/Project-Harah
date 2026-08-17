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
KNOWN_BAD = {"showalter"}   # unhealthy for weeks, pre-existing — see OPEN-ITEMS


def sh(*args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except Exception as e:
        return 1, f"error: {e}"


def main() -> int:
    cfg = json.loads(TARGETS.read_text())
    prev = {}
    if STATE.exists():
        try:
            prev = {t["name"]: t for t in json.loads(STATE.read_text()).get("targets", [])}
        except Exception:
            prev = {}

    targets, problems, transitions = [], [], []
    for repo, t in cfg.items():
        if repo.startswith("_"):
            continue
        for c in t.get("containers", []):
            code, status = sh("docker", "ps", "--filter", f"name=^{c}$", "--format", "{{.Status}}")
            up = bool(status) and code == 0
            unhealthy = "unhealthy" in status.lower()
            ok = up and not unhealthy
            entry = {"name": c, "kind": "container", "repo": repo, "ok": ok,
                     "detail": status or "NOT RUNNING",
                     "known_bad": c in KNOWN_BAD}
            targets.append(entry)
            if not ok and c not in KNOWN_BAD:
                problems.append(f"{c}: {entry['detail']}")
        for u in t.get("urls", []):
            code, out = sh("curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                           "--max-time", "20", u)
            ok = out[:1] in ("2", "3")
            targets.append({"name": u, "kind": "url", "repo": repo, "ok": ok,
                            "detail": f"HTTP {out or '000'}", "known_bad": False})
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
    if problems:
        print(f"UNHEALTHY ({len(problems)}/{len(targets)}): " + "; ".join(problems[:6]))
    else:
        print(f"all {len(targets)} targets healthy")
    # Non-zero only on a NEW failure, so the runner logs a quiet pass quietly.
    return 1 if any(t.startswith("WENT DOWN") for t in transitions) else 0


if __name__ == "__main__":
    sys.exit(main())
