#!/usr/bin/env python3
"""Layer 3 — prove: after a deploy, is the app still doing what it did before?

Every pass, for each target in deploy-check/targets.json that runs on this mini:

  1. Read the image the first container is running. If it is the same image
     we proved last time, do nothing (a deploy is the only trigger).
  2. If the image changed (or we have never seen this target), run the
     target's functional checks against the LIVE app and compare the results
     with the last known-good baseline.
  3. A check that passed in the baseline and fails now is a REGRESSION: the
     deploy lost functionality. Record it, print a `REGRESSION:` line (prove.sh
     texts Alex and hands the container to incident/respond.py), and keep the
     old baseline so the failure stays visible until it is actually fixed.
  4. No regression: the new results become the baseline (`PROVED:`), or, on
     first sight of a target, the first baseline (`BASELINE:`).

Checks are declared per target in targets.json under "checks":

  "checks": [
    {"name": "home", "url": "https://example.com/", "status": 200},
    {"name": "health", "url": "https://example.com/api/health", "contains": "\"ok\":true"},
    {"name": "login page", "url": "https://example.com/login", "status": 200, "contains": "<form"}
  ]

A target with "urls" but no "checks" gets one default check per URL (any
2xx/3xx). Each check also records response time; a check that got 10x slower
is reported as a WARNING, never a regression. The container's own state
(running, not restart-looping) is always checked too.

State -> ~/.harah/prove-state.json (rendered by the dashboard).
Read-only against the apps. Exit 0 unless a regression was found (1).

Flags: --force   run checks for every target even if the image is unchanged
       --repo X  only this owner/repo
       --dry-run run and compare, print, but write no state
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGETS = HERE.parent / "deploy-check" / "targets.json"
STATE = Path.home() / ".harah" / "prove-state.json"
HISTORY_KEEP = 20
TIMEOUT = 20
SLOW_FACTOR = 10.0


def sh(*args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, str(e)


def running_image(container: str) -> str | None:
    code, out = sh("docker", "inspect", "-f", "{{.Image}}", container)
    return out if code == 0 and out.startswith("sha256:") else None


def container_state(container: str) -> dict:
    code, out = sh("docker", "inspect", "-f", "{{.State.Status}} {{.State.Restarting}} {{.RestartCount}}", container)
    if code != 0:
        return {"name": container, "pass": False, "detail": "not found"}
    status, restarting, restarts = (out.split() + ["", "", ""])[:3]
    ok = status == "running" and restarting != "true"
    return {"name": container, "pass": ok, "detail": f"{status}, restarts={restarts}"}


def default_checks(target: dict) -> list[dict]:
    checks = target.get("checks")
    if checks:
        return checks
    return [{"name": f"GET {u}", "url": u} for u in target.get("urls", [])]


def run_check(check: dict) -> dict:
    """One HTTP probe. pass = status matches (default any 2xx/3xx) and body
    contains the expected substring, if one is declared."""
    url = check["url"]
    want_status = check.get("status")
    contains = check.get("contains")
    t0 = time.monotonic()
    status, body, err = 0, "", ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "harah-prove/1"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            status = r.status
            body = r.read(512 * 1024).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            body = e.read(64 * 1024).decode("utf-8", "replace")
        except Exception:
            body = ""
    except Exception as e:  # DNS, TLS, timeout, refused
        err = type(e).__name__
    ms = int((time.monotonic() - t0) * 1000)
    if want_status is None:
        status_ok = 200 <= status < 400
    else:
        status_ok = status == int(want_status)
    contains_ok = True if not contains else (contains in body)
    detail = f"HTTP {status or '000'}{(' ' + err) if err else ''} in {ms}ms"
    if contains and not contains_ok and status_ok:
        detail += f", body lacks {contains!r}"
    return {"name": check.get("name") or url, "url": url, "pass": status_ok and contains_ok,
            "status": status, "ms": ms, "detail": detail}


def compare(baseline: dict | None, current: dict) -> dict:
    """baseline/current: {check_name: {pass, ms, ...}}. Returns regressions
    (passed before, fails now), still_failing (failed before and now), new
    passes, and slow (passes but >= SLOW_FACTOR slower than baseline)."""
    out = {"regressions": [], "still_failing": [], "fixed": [], "slow": [], "failing_new": []}
    base = baseline or {}
    for name, cur in current.items():
        was = base.get(name)
        if cur["pass"]:
            if was is not None and not was.get("pass"):
                out["fixed"].append(name)
            bms, cms = (was or {}).get("ms"), cur.get("ms")
            if bms and cms and bms > 0 and cms >= SLOW_FACTOR * bms and cms > 1000:
                out["slow"].append(f"{name} ({bms}ms -> {cms}ms)")
        else:
            if was is None:
                out["failing_new"].append(name)      # no baseline: can't call it a regression
            elif was.get("pass"):
                out["regressions"].append(name)
            else:
                out["still_failing"].append(name)
    return out


def results_for(target: dict) -> dict:
    results: dict[str, dict] = {}
    for c in target.get("containers", []):
        r = container_state(c)
        results[f"container {c}"] = r
    for chk in default_checks(target):
        r = run_check(chk)
        results[r["name"]] = r
    return results


def load_state() -> dict:
    try:
        s = json.loads(STATE.read_text())
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)


def main(argv: list[str]) -> int:
    force = "--force" in argv
    dry = "--dry-run" in argv
    only = None
    if "--repo" in argv:
        only = argv[argv.index("--repo") + 1]

    cfg = json.loads(TARGETS.read_text())
    state = load_state()
    targets_state = state.setdefault("targets", {})
    now = time.time()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    any_regression = False
    lines: list[str] = []

    for repo, t in cfg.items():
        if repo.startswith("_") or not isinstance(t, dict) or not t.get("containers"):
            continue
        if only and repo != only:
            continue
        first = t["containers"][0]
        image = running_image(first)
        ts = targets_state.setdefault(repo, {})
        if image is None:
            lines.append(f"SKIP: {repo} ({first} not running; watchdog owns that)")
            continue
        if not force and ts.get("image") == image:
            continue  # same image we already proved — nothing to do

        reason = "first sight" if not ts.get("image") else ("forced" if ts.get("image") == image else "image changed")
        results = results_for(t)
        cmp = compare(ts.get("baseline"), results)
        failed = [n for n, r in results.items() if not r["pass"]]
        summary = {"at": stamp, "image": image[:19], "reason": reason,
                   "checks": len(results), "failed": failed, **cmp}

        if cmp["regressions"]:
            any_regression = True
            ts["last_result"] = "regression"
            # keep the old baseline: the failure must stay visible until fixed
            for n in cmp["regressions"]:
                lines.append(f"REGRESSION: {first} {repo} {n}: {results[n]['detail']}")
            lines.append(f"  deploy of {repo} ({image[:19]}) lost {len(cmp['regressions'])} check(s); "
                         f"baseline kept from {ts.get('baseline_at', '?')}")
        else:
            ts["last_result"] = "proved" if ts.get("image") else "baseline"
            ts["baseline"] = results
            ts["baseline_at"] = stamp
            tag = "PROVED" if reason != "first sight" else "BASELINE"
            extra = ""
            if failed:
                extra = f"; {len(failed)} check(s) failing with no passing baseline: {', '.join(failed)}"
            if cmp["fixed"]:
                extra += f"; fixed: {', '.join(cmp['fixed'])}"
            lines.append(f"{tag}: {repo} {image[:19]} ({reason}) {len(results) - len(failed)}/{len(results)} checks pass{extra}")
        for s in cmp["slow"]:
            lines.append(f"WARNING: {repo} slower after deploy: {s}")

        ts["image"] = image
        ts["last_proved_at"] = stamp
        ts["last_results"] = results
        hist = ts.setdefault("history", [])
        hist.append(summary)
        del hist[:-HISTORY_KEEP]

    state["last_run"] = now
    state["healthy"] = not any(v.get("last_result") == "regression" for v in targets_state.values())
    if not dry:
        save_state(state)
    for l in lines:
        print(l)
    if not lines:
        print("steady: no image changes")
    return 1 if any_regression else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
