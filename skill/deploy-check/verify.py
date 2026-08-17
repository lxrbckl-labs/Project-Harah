#!/usr/bin/env python3
"""Did the merge actually reach the running app, and is that app still up?

Usage: verify.py <owner/repo> [--since-merge <ISO8601>]

Walks the whole chain, because a green merge tells you almost nothing here:

  merge -> CI run -> DockerHub image -> watchtower rolls it -> container -> HTTP

Two traps this exists to stop sessions falling into:

1. **A merge does not deploy — a `publish` commit does.** The shared workflow
   builds only when the head commit message starts with `publish` (or is a merge
   commit containing it). An ordinary merge reports `skipped` and produces NO
   image, so the live container keeps running the old code. Reporting "merged
   and verified healthy" after such a merge is true and completely misleading:
   healthy because nothing changed.

2. **`skipped` != `failure` != "GitHub couldn't find the workflow".** All three
   leave the image untouched and mean different things. A run whose
   `jobs.total_count` is 0 never started a job at all — on `reactive-resume`
   that is the `lxrbckl-dev` org-rename signature, not a broken build.

Exit codes: 0 verified-good (incl. correctly-not-deployed), 1 something is
actually wrong, 2 usage/unknown repo.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TARGETS = Path(__file__).resolve().parent / "targets.json"


def sh(*args: str, timeout: int = 45) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except Exception as e:
        return 1, f"error: {e}"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__); return 2
    repo = sys.argv[1]
    cfg = json.loads(TARGETS.read_text())
    if repo not in cfg:
        print(f"unknown repo '{repo}'. Known: {[k for k in cfg if not k.startswith('_')]}")
        return 2
    t = cfg[repo]
    ok = True
    print(f"== deployment check: {repo} ==")
    if t.get("notes"):
        print(f"   note: {t['notes']}")

    # 1. Did the last push to main actually build?
    code, out = sh("gh", "run", "list", "-R", repo, "--branch", "main", "--limit", "1",
                   "--json", "conclusion,displayTitle,createdAt,databaseId",
                   "--jq", r'.[0] | "\(.conclusion // "running")\t\(.createdAt)\t\(.databaseId)\t\(.displayTitle)"')
    if code == 0 and out:
        concl, created, run_id, title = (out.split("\t") + ["", "", "", ""])[:4]
        jcode, jobs = sh("gh", "api", f"/repos/{repo}/actions/runs/{run_id}/jobs",
                         "--jq", ".total_count")
        njobs = jobs.strip() if jcode == 0 else "?"
        _, jconcl = sh("gh", "api", f"/repos/{repo}/actions/runs/{run_id}/jobs",
                       "--jq", "[.jobs[].conclusion] | join(\",\")")
        built = "success" in (jconcl or "")
        print(f"\n1. CI       {concl}  ({created[:16]})  jobs={njobs}")
        print(f"            {title[:70]}")
        print(f"            jobs concluded: {jconcl or 'none'}")
        if concl == "skipped" or (concl == "success" and not built):
            print("            -> publish gate said no. NO new image was built.")
            print("               Expected for a plain merge: `publish` prefix is what ships.")
        elif concl == "failure" and njobs == "0":
            print("            -> ran ZERO jobs: GitHub could not resolve the workflow.")
            print("               Not a build failure. Check the `uses:` org reference.")
            ok = False
        elif concl == "failure":
            print("            -> the build genuinely broke.")
            ok = False
    else:
        print("\n1. CI       could not read run list")

    # 2/3. Is the container up, and how old is the image it is running?
    if not t["containers"]:
        print("\n2. Runtime  not deployed on this mini — nothing to verify")
    for c in t["containers"]:
        code, status = sh("docker", "ps", "--filter", f"name=^{c}$", "--format", "{{.Status}}")
        if code != 0 or not status:
            print(f"\n2. {c}: NOT RUNNING"); ok = False; continue
        _, created = sh("docker", "inspect", "-f", "{{.Created}}", c)
        _, img = sh("docker", "inspect", "-f", "{{.Config.Image}}", c)
        age = ""
        try:
            d = datetime.fromisoformat(created.replace("Z", "+00:00"))
            age = f", image built {(datetime.now(timezone.utc) - d).days}d ago"
        except Exception:
            pass
        flag = " <-- UNHEALTHY" if "unhealthy" in status.lower() else ""
        print(f"\n2. {c}: {status}{flag}\n   {img}{age}")
        if "unhealthy" in status.lower():
            ok = False

    # 3b. The decisive question: is the running code older than main?
    _, head_date = sh("gh", "api", f"/repos/{repo}/commits/main", "--jq", ".commit.committer.date")
    if head_date and t["containers"]:
        try:
            hd = datetime.fromisoformat(head_date.replace("Z", "+00:00"))
            _, cr = sh("docker", "inspect", "-f", "{{.Created}}", t["containers"][0])
            cd = datetime.fromisoformat(cr.replace("Z", "+00:00"))
            behind = (hd - cd).days
            print(f"\n2b. main's newest commit {head_date[:16]} vs running image {cr[:16]}")
            if behind > 0:
                print(f"    -> RUNNING CODE IS {behind}d BEHIND main. Merges have NOT shipped.")
            else:
                print("    -> running image is at or ahead of main's newest commit.")
        except Exception:
            pass

    # 4. The only end-to-end proof: a real request through Caddy.
    for u in t["urls"]:
        code, out = sh("curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                       "--max-time", "20", u)
        good = out.startswith("2") or out.startswith("3")
        print(f"\n3. {u} -> HTTP {out or '000'}{'' if good else '  <-- NOT SERVING'}")
        if not good:
            ok = False

    print(f"\n== {'PASS' if ok else 'FAIL'} ==")
    if ok:
        print("Note: 'PASS' with a skipped CI run means the app is healthy on the")
        print("OLD image. The merge is on main but has not shipped. Say so plainly.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
