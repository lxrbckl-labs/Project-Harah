#!/usr/bin/env python3
"""
caddy-traffic.py — snapshot of network traffic through the homelab Caddy proxy.

Reads Caddy's JSON access log (/data/access.log inside the caddy container,
enabled via the (accesslog) snippet in ~/caddyfile), windows it to the last N
minutes, and prints a report: request volume, throughput, status-code mix,
per-site breakdown, top client IPs, and rate-limit (429) activity.

Examples
    ./caddy-traffic.py                 # last 5 minutes, one report
    ./caddy-traffic.py -n 15           # last 15 minutes
    ./caddy-traffic.py -n 10 --watch   # re-run every 10 minutes
    ./caddy-traffic.py -n 60 --json    # machine-readable (for future dashboards)

Data source: `docker exec <container> cat <logpath>`. No extra mounts needed;
the log lives in the existing caddy_data volume.
"""
import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime


def human_bytes(n):
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} PiB"


def read_log(container, logpath):
    """Return raw access-log text from inside the caddy container."""
    try:
        out = subprocess.run(
            ["docker", "exec", container, "cat", logpath],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        sys.exit("error: `docker` not found on PATH")
    except subprocess.TimeoutExpired:
        sys.exit("error: timed out reading the log from the container")
    if out.returncode != 0:
        err = out.stderr.strip()
        if "No such file" in err:
            sys.exit(f"error: {logpath} not found in '{container}' — is access "
                     f"logging enabled in the Caddyfile and has any traffic hit it yet?")
        if "No such container" in err or "is not running" in err:
            sys.exit(f"error: container '{container}' not found/running")
        sys.exit(f"error reading log: {err}")
    return out.stdout


def collect(text, cutoff):
    """Parse access-log lines newer than `cutoff` epoch into aggregate stats."""
    stats = {
        "total": 0, "bytes": 0, "dur_sum": 0.0,
        "class": defaultdict(int),          # '2xx' -> count
        "codes": defaultdict(int),          # 429 -> count
        "by_host": defaultdict(lambda: {"req": 0, "bytes": 0, "4xx": 0, "5xx": 0}),
        "by_ip": defaultdict(lambda: {"req": 0, "err": 0, "429": 0}),
        "rl_by_host": defaultdict(int),     # 429s per host
        "rl_by_ip": defaultdict(int),       # 429s per ip
        "oldest": None, "newest": None,
    }
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] != "{":
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        ts = e.get("ts")
        if not isinstance(ts, (int, float)) or ts < cutoff:
            continue
        req = e.get("request", {})
        if e.get("msg") != "handled request" and "status" not in e:
            continue
        status = int(e.get("status", 0) or 0)
        size = int(e.get("size", 0) or 0)
        dur = float(e.get("duration", 0.0) or 0.0)
        host = req.get("host", "?")
        ip = req.get("client_ip") or req.get("remote_ip") or "?"

        stats["total"] += 1
        stats["bytes"] += size
        stats["dur_sum"] += dur
        stats["oldest"] = ts if stats["oldest"] is None else min(stats["oldest"], ts)
        stats["newest"] = ts if stats["newest"] is None else max(stats["newest"], ts)

        cls = f"{status // 100}xx" if status else "0xx"
        stats["class"][cls] += 1
        stats["codes"][status] += 1

        h = stats["by_host"][host]
        h["req"] += 1
        h["bytes"] += size
        if 400 <= status < 500:
            h["4xx"] += 1
        elif status >= 500:
            h["5xx"] += 1

        p = stats["by_ip"][ip]
        p["req"] += 1
        if status >= 400:
            p["err"] += 1
        if status == 429:
            p["429"] += 1
            stats["rl_by_host"][host] += 1
            stats["rl_by_ip"][ip] += 1
    return stats


def render_text(stats, minutes, top):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    win_min = max(minutes, 1e-9)
    lines = []
    lines.append(f"── Caddy traffic · last {minutes} min · {now} " + "─" * 12)

    if stats["total"] == 0:
        lines.append("  no requests in window")
        return "\n".join(lines)

    rpm = stats["total"] / win_min
    bpm = stats["bytes"] / win_min
    avg_ms = (stats["dur_sum"] / stats["total"]) * 1000
    lines.append(
        f"  {stats['total']} requests  ({rpm:.1f}/min)   "
        f"{human_bytes(stats['bytes'])} out  ({human_bytes(bpm)}/min)   "
        f"avg {avg_ms:.1f} ms"
    )

    # status mix
    order = ["2xx", "3xx", "4xx", "5xx", "0xx"]
    mix = "  ".join(
        f"{c}:{stats['class'][c]}" for c in order if stats["class"].get(c)
    )
    lines.append(f"  status: {mix}")

    # rate-limit callout (429s)
    rl = stats["codes"].get(429, 0)
    if rl:
        lines.append("")
        lines.append(f"  ⚠ RATE-LIMITED (429): {rl} request(s) blocked")
        for host, n in sorted(stats["rl_by_host"].items(), key=lambda x: -x[1]):
            offenders = sorted(
                ((ip, stats["by_ip"][ip]["429"]) for ip in stats["by_ip"]
                 if stats["by_ip"][ip]["429"] and stats["rl_by_host"].get(host)),
                key=lambda x: -x[1],
            )
            ip_str = ", ".join(f"{ip}({n})" for ip, n in offenders[:top])
            lines.append(f"      {host}: {n}   from: {ip_str}")

    # per-host
    lines.append("")
    lines.append("  by site:")
    hosts = sorted(stats["by_host"].items(), key=lambda x: -x[1]["req"])
    lines.append(f"    {'host':<32} {'req':>6} {'bytes':>10} {'4xx':>5} {'5xx':>5}")
    for host, d in hosts:
        lines.append(
            f"    {host:<32} {d['req']:>6} {human_bytes(d['bytes']):>10} "
            f"{d['4xx']:>5} {d['5xx']:>5}"
        )

    # top IPs
    lines.append("")
    lines.append(f"  top client IPs (of {len(stats['by_ip'])}):")
    ips = sorted(stats["by_ip"].items(), key=lambda x: -x[1]["req"])[:top]
    lines.append(f"    {'ip':<24} {'req':>6} {'4xx+':>6} {'429':>5}")
    for ip, d in ips:
        lines.append(f"    {ip:<24} {d['req']:>6} {d['err']:>6} {d['429']:>5}")

    return "\n".join(lines)


def render_json(stats, minutes):
    win_min = max(minutes, 1e-9)
    return json.dumps({
        "generated_at": time.time(),
        "window_minutes": minutes,
        "requests": stats["total"],
        "requests_per_min": round(stats["total"] / win_min, 3),
        "bytes_out": stats["bytes"],
        "bytes_per_min": round(stats["bytes"] / win_min, 1),
        "avg_duration_ms": round((stats["dur_sum"] / stats["total"] * 1000), 3) if stats["total"] else 0,
        "status_class": dict(stats["class"]),
        "status_codes": {str(k): v for k, v in stats["codes"].items()},
        "rate_limited_429": stats["codes"].get(429, 0),
        "rate_limited_by_host": dict(stats["rl_by_host"]),
        "rate_limited_by_ip": dict(stats["rl_by_ip"]),
        "by_host": {h: d for h, d in stats["by_host"].items()},
        "by_ip": {ip: d for ip, d in stats["by_ip"].items()},
    }, indent=2)


def run_once(args):
    cutoff = time.time() - args.minutes * 60
    text = read_log(args.container, args.logpath)
    stats = collect(text, cutoff)
    if args.json:
        print(render_json(stats, args.minutes))
    else:
        print(render_text(stats, args.minutes, args.top))


def main():
    ap = argparse.ArgumentParser(description="Monitor traffic through the Caddy proxy.")
    ap.add_argument("-n", "--minutes", type=float, default=5,
                    help="window size in minutes (default 5)")
    ap.add_argument("-w", "--watch", action="store_true",
                    help="loop forever, re-running every --minutes")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    ap.add_argument("--top", type=int, default=5, help="rows for top IPs/offenders (default 5)")
    ap.add_argument("--container", default="caddy", help="caddy container name (default caddy)")
    ap.add_argument("--logpath", default="/data/access.log",
                    help="access log path inside the container")
    args = ap.parse_args()

    if not args.watch:
        run_once(args)
        return
    try:
        while True:
            run_once(args)
            sys.stdout.flush()
            time.sleep(args.minutes * 60)
    except KeyboardInterrupt:
        print("\nstopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
