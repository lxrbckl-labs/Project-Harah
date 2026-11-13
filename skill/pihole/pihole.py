#!/usr/bin/env python3
"""pihole.py — Harah's hands on the Pi-hole, the LAN DNS ad blocker on the mini.

The Pi-hole is the Docker stack at ~/docker-bare-run/pihole (container `pihole`,
DNS on the mini's :53, admin UI and API on :8753, LAN only). This tool is the
CRUD surface Harah and Alex share; the web UI is for looking, this is for doing.

Usage (reads need nothing beyond the running container; writes take --dry-run):
  pihole.py status                        blocking state, gravity size, 24h totals
  pihole.py lists [--json]                the adlists (blocklist sources)
  pihole.py lists add <url> [comment]     add a blocklist, then run `gravity`
  pihole.py lists rm <url>                remove a blocklist, then run `gravity`
  pihole.py gravity                       rebuild the blocklist from the adlists
  pihole.py domains [allow|deny] [--json] exact allow/deny entries Alex or Harah added
  pihole.py allow <domain> [comment]      allow a domain (undo a false positive)
  pihole.py deny <domain> [comment]       deny a domain (an ad that got through)
  pihole.py rm <allow|deny> <domain>      drop an allow/deny entry
  pihole.py top [--blocked] [N]           top permitted (or blocked) domains, last 24h
  pihole.py leaks [--since H] [--json] [N] permitted domains that look like ads or
                                          trackers (recall over precision: a human or
                                          the audit agent judges them)
  pihole.py blocking [on|off [MINUTES]]   read or set blocking; off defaults to 5 min

Auth: the password is PIHOLE_PASSWORD in ~/docker-bare-run/pihole/.env (mode 600).
Read from there, never printed or logged. Every run logs its session out again:
Pi-hole caps concurrent sessions. PIHOLE_API overrides the base URL for tests.
Python stdlib only, like gateway.py. Exit 0 on success, 1 on any failure.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = os.environ.get("PIHOLE_API", "http://127.0.0.1:8753/api").rstrip("/")
ENV_FILE = Path(os.environ.get("PIHOLE_ENV", Path.home() / "docker-bare-run" / "pihole" / ".env"))
TIMEOUT = 30
_sid: str | None = None

# Labels (between dots, hyphens or underscores) that mark a hostname as an ad,
# tracking or telemetry endpoint. Exact label matches are listed under EXACT;
# PREFIX catches the morphology (adserv, adservice, advert, trackers, analytics).
EXACT = {
    "ad", "ads", "adx", "adsrv", "adnxs", "adsrvr", "adform", "adtech", "doubleclick",
    "track", "tracker", "tracking", "trk", "telemetry", "metrics", "smetrics", "pixel",
    "pixels", "beacon", "beacons", "banner", "banners", "sponsor", "sponsored", "affiliate",
    "affiliates", "click", "clicks", "clk", "collector", "collect", "stats", "stat", "tags",
    "tag", "tagmanager", "events", "event", "log", "logs", "logging", "measure",
    "measurement", "app-measurement", "taboola", "outbrain", "criteo", "pubmatic", "rubicon",
    "openx", "moatads", "scorecardresearch", "appsflyer", "adjust", "amplitude", "mixpanel",
    "segment", "hotjar", "braze", "leanplum", "chartbeat", "quantserve", "krxd", "demdex",
    "omtrdc", "2o7", "everesttech", "bluekai", "exelator", "rlcdn", "agkn", "liadm",
    "casalemedia", "smartadserver", "yieldmo", "sharethrough", "teads", "mgid", "revcontent",
    "zemanta", "bidswitch", "3lift", "triplelift", "indexww", "amazon-adsystem",
    "googlesyndication", "googleadservices", "google-analytics", "googletagmanager",
    "googletagservices", "branch", "kochava", "singular", "tenjin", "unityads", "vungle",
    "applovin", "ironsrc", "inmobi", "chartboost", "mopub", "flurry", "crwdcntrl", "mathtag",
    "serving-sys", "sitescout", "turn", "tapad", "adroll", "perfectaudience", "pardot",
    "marketo", "eloqua", "hubspot", "optimizely", "sentry", "bugsnag", "newrelic", "datadoghq",
    "intercom", "zendesk", "drift", "fullstory", "mouseflow", "clarity", "nr-data",
}
PREFIX = ("adserv", "adservice", "advert", "adsystem", "adsdk", "analytic", "telemetr", "metric",
          "tracker", "tracking", "trackers", "pixel", "beacon", "sponsor", "affiliat", "doubleclick")
# Things the heuristics would flag but that are plumbing, not ads. Still listed by
# `leaks --all`; dropped by default so the audit reads cleanly.
PLUMBING = {"pi.hole", "localhost", "attlocal.net"}


def die(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def password() -> str:
    try:
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("PIHOLE_PASSWORD="):
                return line.split("=", 1)[1].strip().strip("'\"")
    except FileNotFoundError:
        pass
    die(f"no password: expected PIHOLE_PASSWORD in {ENV_FILE} (mode 600). Alex writes it; Harah never prints it.")
    return ""  # unreachable


def call(method: str, path: str, body: dict | None = None, auth: bool = True) -> dict:
    url = f"{API}/{path.lstrip('/')}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"User-Agent": "harah-pihole/1", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if auth:
        headers["sid"] = sid()
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
            detail = f"{err.get('key', '')} {err.get('message', '')} {err.get('hint') or ''}".strip()
        except Exception:
            detail = e.reason
        die(f"{method} {path}: HTTP {e.code} {detail}")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        die(f"{method} {path}: Pi-hole API unreachable at {API} ({e}). Is the `pihole` container up?")
    return {}


def sid() -> str:
    global _sid
    if _sid is None:
        res = call("POST", "auth", {"password": password()}, auth=False)
        _sid = (res.get("session") or {}).get("sid")
        if not _sid:
            die("auth failed: wrong password in the .env, or the API refused the session")
        atexit.register(logout)
    return _sid


def logout() -> None:
    global _sid
    if _sid:
        try:
            req = urllib.request.Request(f"{API}/auth", method="DELETE", headers={"sid": _sid})
            urllib.request.urlopen(req, timeout=10).read()
        except Exception:
            pass
        _sid = None


def dry(args: list[str]) -> bool:
    if "--dry-run" in args:
        args.remove("--dry-run")
        return True
    return False


def want_json(args: list[str]) -> bool:
    if "--json" in args:
        args.remove("--json")
        return True
    return False


# ── commands ────────────────────────────────────────────────────────────────

def cmd_status(args: list[str]) -> int:
    s = call("GET", "stats/summary")
    b = call("GET", "dns/blocking")
    q, g = s.get("queries", {}), s.get("gravity", {})
    lists = call("GET", "lists").get("lists", [])
    print(f"blocking   {b.get('blocking')}" + (f" (timer {int(b['timer'])}s)" if b.get("timer") else ""))
    print(f"gravity    {g.get('domains_being_blocked', 0):,} domains from {len(lists)} adlists"
          + (f", last update {time.strftime('%Y-%m-%d %H:%M', time.localtime(g['last_update']))}" if g.get("last_update") else ""))
    print(f"24h        {q.get('total', 0):,} queries, {q.get('blocked', 0):,} blocked ({q.get('percent_blocked', 0):.1f}%), "
          f"{q.get('unique_domains', 0):,} unique domains, {s.get('clients', {}).get('active', 0)} active clients")
    print("note       Docker Desktop NATs every LAN client to one address; per-client stats are not meaningful here.")
    return 0


def cmd_lists(args: list[str]) -> int:
    as_json = want_json(args)
    if args and args[0] == "add":
        if len(args) < 2:
            die("usage: lists add <url> [comment]")
        is_dry = dry(args)
        url, comment = args[1], " ".join(args[2:]) or "added by Harah"
        if is_dry:
            print(f"DRY RUN: would add blocklist {url} ({comment})")
            return 0
        res = call("POST", "lists?type=block", {"address": url, "comment": comment, "enabled": True})  # type is a query param
        proc = res.get("processing", {})
        if proc.get("errors"):
            die(f"not added: {proc['errors']}")
        print(f"✓ added {url}  — run `pihole.py gravity` to pull it in")
        return 0
    if args and args[0] == "rm":
        if len(args) < 2:
            die("usage: lists rm <url>")
        is_dry = dry(args)
        if is_dry:
            print(f"DRY RUN: would remove blocklist {args[1]}")
            return 0
        call("DELETE", f"lists/{urllib.parse.quote(args[1], safe='')}?type=block")
        print(f"✓ removed {args[1]}  — run `pihole.py gravity` to drop its domains")
        return 0
    lists = call("GET", "lists").get("lists", [])
    if as_json:
        print(json.dumps(lists, indent=1))
        return 0
    for l in lists:
        flag = "on " if l.get("enabled") else "off"
        n = l.get("number")
        print(f"{l['id']:>3} {flag} {l['address']}  [{n:,} domains]" if n is not None else f"{l['id']:>3} {flag} {l['address']}", end="")
        print(f"  — {l['comment']}" if l.get("comment") else "")
    return 0


def cmd_gravity(args: list[str]) -> int:
    if dry(args):
        print("DRY RUN: would rebuild gravity")
        return 0
    # The gravity endpoint streams its progress as text; read it raw.
    req = urllib.request.Request(f"{API}/action/gravity", method="POST", headers={"sid": sid()})
    with urllib.request.urlopen(req, timeout=600) as r:
        out = r.read().decode("utf-8", "replace")
    tail = [ln for ln in out.splitlines() if ln.strip()][-3:]
    print("\n".join(tail) if tail else "✓ gravity rebuilt")
    g = call("GET", "stats/summary").get("gravity", {})
    print(f"✓ gravity now blocks {g.get('domains_being_blocked', 0):,} domains")
    return 0


def _domains(kind_filter: str | None) -> list[dict]:
    path = f"domains/{kind_filter}" if kind_filter else "domains"
    return call("GET", path).get("domains", [])


def cmd_domains(args: list[str]) -> int:
    as_json = want_json(args)
    kind = args[0] if args and args[0] in ("allow", "deny") else None
    doms = _domains(kind)
    if as_json:
        print(json.dumps(doms, indent=1))
        return 0
    if not doms:
        print("(no exact allow/deny entries)")
    for d in doms:
        flag = "on " if d.get("enabled") else "off"
        print(f"{d['type']:>5} {d['kind']:>5} {flag} {d['domain']}" + (f"  — {d['comment']}" if d.get("comment") else ""))
    return 0


def _add_domain(typ: str, args: list[str]) -> int:
    if not args:
        die(f"usage: {typ} <domain> [comment]")
    is_dry = dry(args)
    domain = args[0].lower().strip(".")
    if not re.fullmatch(r"[a-z0-9.-]+", domain):
        die(f"not a plain hostname: {domain} (exact matches only; regex is a UI job)")
    comment = " ".join(args[1:]) or f"{typ} by Harah {time.strftime('%Y-%m-%d')}"
    if is_dry:
        print(f"DRY RUN: would {typ} {domain} ({comment})")
        return 0
    res = call("POST", f"domains/{typ}/exact", {"domain": domain, "comment": comment, "enabled": True})
    proc = res.get("processing", {})
    if proc.get("errors"):
        die(f"not added: {proc['errors']}")
    print(f"✓ {typ} {domain}")
    return 0


def cmd_rm(args: list[str]) -> int:
    if len(args) < 2 or args[0] not in ("allow", "deny"):
        die("usage: rm <allow|deny> <domain>")
    is_dry = dry(args)
    if is_dry:
        print(f"DRY RUN: would remove {args[0]} entry {args[1]}")
        return 0
    call("DELETE", f"domains/{args[0]}/exact/{urllib.parse.quote(args[1].lower(), safe='')}")
    print(f"✓ removed {args[0]} {args[1]}")
    return 0


def _top(blocked: bool, count: int, since_h: float | None) -> list[dict]:
    if since_h is None:
        res = call("GET", f"stats/top_domains?blocked={'true' if blocked else 'false'}&count={count}")
    else:
        now = int(time.time())
        res = call("GET", f"stats/database/top_domains?from={now - int(since_h * 3600)}&until={now}"
                          f"&blocked={'true' if blocked else 'false'}&count={count}")
    return res.get("domains", [])


def cmd_top(args: list[str]) -> int:
    blocked = "--blocked" in args
    args = [a for a in args if a != "--blocked"]
    n = int(args[0]) if args else 25
    for d in _top(blocked, n, None):
        print(f"{d['count']:>7}  {d['domain']}")
    return 0


def looks_like_ad(domain: str) -> list[str]:
    labels = [p for p in re.split(r"[.\-_]", domain.lower()) if p]
    hits = []
    for lab in labels:
        if lab in EXACT or lab.startswith(PREFIX):
            hits.append(lab)
    return hits


def leaks(since_h: float, limit: int, include_all: bool) -> list[dict]:
    allowed = {d["domain"] for d in _domains("allow")}
    denied = {d["domain"] for d in _domains("deny")}
    out = []
    for d in _top(False, 500, since_h):
        dom = d["domain"]
        if dom in allowed or dom in denied:
            continue
        if not include_all and any(dom == p or dom.endswith("." + p) for p in PLUMBING):
            continue
        hits = looks_like_ad(dom)
        if hits:
            out.append({"domain": dom, "queries": d["count"], "signals": hits})
    out.sort(key=lambda x: (-len(x["signals"]), -x["queries"]))
    return out[:limit]


def cmd_leaks(args: list[str]) -> int:
    as_json = want_json(args)
    include_all = "--all" in args
    args = [a for a in args if a != "--all"]
    since_h = 24.0
    if "--since" in args:
        i = args.index("--since")
        since_h = float(args[i + 1])
        del args[i:i + 2]
    n = int(args[0]) if args else 40
    found = leaks(since_h, n, include_all)
    if as_json:
        print(json.dumps({"since_hours": since_h, "candidates": found}, indent=1))
        return 0
    if not found:
        print(f"no permitted domain in the last {since_h:g}h looks like an ad or tracker")
        return 0
    print(f"permitted in the last {since_h:g}h and shaped like ads/trackers (judge before denying):")
    for c in found:
        print(f"{c['queries']:>7}  {c['domain']}  ({', '.join(c['signals'])})")
    return 0


def cmd_blocking(args: list[str]) -> int:
    if not args:
        b = call("GET", "dns/blocking")
        print(f"blocking {b.get('blocking')}" + (f", back on in {int(b['timer'])}s" if b.get("timer") else ""))
        return 0
    is_dry = dry(args)
    state = args[0]
    if state not in ("on", "off"):
        die("usage: blocking [on|off [MINUTES]]")
    minutes = float(args[1]) if len(args) > 1 else (5.0 if state == "off" else None)
    body: dict = {"blocking": state == "on"}
    if state == "off" and minutes:
        body["timer"] = minutes * 60
    if is_dry:
        print(f"DRY RUN: would set blocking {state}" + (f" for {minutes:g} min" if state == "off" else ""))
        return 0
    b = call("POST", "dns/blocking", body)
    print(f"✓ blocking {b.get('blocking')}" + (f", back on in {int(b['timer'])}s" if b.get("timer") else ""))
    return 0


COMMANDS = {
    "status": cmd_status, "lists": cmd_lists, "gravity": cmd_gravity, "domains": cmd_domains,
    "allow": lambda a: _add_domain("allow", a), "deny": lambda a: _add_domain("deny", a),
    "rm": cmd_rm, "top": cmd_top, "leaks": cmd_leaks, "blocking": cmd_blocking,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    cmd, args = argv[0], list(argv[1:])
    if cmd not in COMMANDS:
        die(f"unknown command {cmd!r}; try --help")
    return COMMANDS[cmd](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
