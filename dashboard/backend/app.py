"""
ServerManager dashboard — backend API.

Exposes read-only server telemetry (host + container resource usage, Caddy
traffic) and a DELIBERATELY NARROW container-control surface: start / stop /
restart only. There is no code path that removes or deletes a container — by
design. Binds to 127.0.0.1 only; this controls Docker and must not be exposed.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# The ONLY container actions this server will ever perform. `rm`/`remove` is
# intentionally absent and must never be added here.
ALLOWED_ACTIONS = {"start", "stop", "restart"}

CADDY_CONTAINER = "caddy"
CADDY_LOGPATH = "/data/access.log"

# Resource-history sampler: persists host CPU/mem/disk/load to sqlite so the
# dashboard can graph usage over time. History starts accumulating when the
# backend first runs (no retroactive data).
_DB = Path(__file__).resolve().parent / "resources.db"
SAMPLE_INTERVAL = 15      # seconds between samples
HISTORY_RETENTION = 49 * 3600  # keep ~2 days


def _init_history_db() -> None:
    con = sqlite3.connect(_DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS samples "
        "(ts REAL PRIMARY KEY, cpu REAL, mem REAL, disk REAL, load1 REAL)"
    )
    con.commit()
    con.close()


def _sampler_loop() -> None:
    con = sqlite3.connect(_DB)
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1.0)  # 1s average
            vm = psutil.virtual_memory()
            du = psutil.disk_usage("/")
            try:
                load1 = psutil.getloadavg()[0]
            except (AttributeError, OSError):
                load1 = 0.0
            now = time.time()
            con.execute(
                "INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?)",
                (now, cpu, vm.percent, du.percent, load1),
            )
            con.execute("DELETE FROM samples WHERE ts < ?", (now - HISTORY_RETENTION,))
            con.commit()
        except Exception:
            pass
        time.sleep(max(1, SAMPLE_INTERVAL - 1))  # cpu_percent already blocked ~1s


_init_history_db()
threading.Thread(target=_sampler_loop, daemon=True).start()

app = FastAPI(title="ServerManager Dashboard API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- helpers

def docker(*args: str, timeout: int = 20) -> str:
    """Run a docker command, returning stdout. Raises on failure."""
    if not shutil.which("docker"):
        raise HTTPException(500, "docker not found on PATH")
    try:
        p = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, f"docker {args[0]} timed out")
    if p.returncode != 0:
        raise HTTPException(500, f"docker {args[0]} failed: {p.stderr.strip()}")
    return p.stdout


def parse_docker_time(s: str) -> float | None:
    """Parse a docker RFC3339Nano timestamp to epoch seconds (None if zero/invalid)."""
    if not s or s.startswith("0001-01-01"):
        return None
    s = s.strip().replace("Z", "+00:00")
    # trim fractional seconds to 6 digits (python max microsecond precision)
    if "." in s:
        head, rest = s.split(".", 1)
        frac = ""
        i = 0
        while i < len(rest) and rest[i].isdigit():
            frac += rest[i]
            i += 1
        s = f"{head}.{frac[:6]}{rest[i:]}"
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def _pct(s: str) -> float:
    try:
        return float(s.strip().rstrip("%"))
    except (ValueError, AttributeError):
        return 0.0


# ---------------------------------------------------------------- containers

def list_container_names() -> set[str]:
    out = docker("ps", "-a", "--format", "{{.Names}}")
    return {n for n in out.splitlines() if n.strip()}


@app.get("/api/containers")
def containers():
    """All containers with state, uptime, ports — running and stopped."""
    rows = [json.loads(l) for l in docker(
        "ps", "-a", "--no-trunc", "--format", "{{json .}}"
    ).splitlines() if l.strip()]

    # batch inspect for precise StartedAt
    started: dict[str, str] = {}
    ids = [r["ID"] for r in rows]
    if ids:
        insp = docker("inspect", "-f", "{{.Id}}|{{.State.StartedAt}}", *ids)
        for line in insp.splitlines():
            if "|" in line:
                cid, ts = line.split("|", 1)
                started[cid] = ts

    now = time.time()
    result = []
    for r in rows:
        state = r.get("State", "")
        start_epoch = parse_docker_time(started.get(r["ID"], ""))
        uptime = int(now - start_epoch) if (state == "running" and start_epoch) else 0
        result.append({
            "id": r["ID"][:12],
            "name": r.get("Names", ""),
            "image": r.get("Image", ""),
            "state": state,                     # running | exited | created | paused
            "status": r.get("Status", ""),      # "Up 3 hours (healthy)" etc.
            "ports": r.get("Ports", ""),
            "uptime_seconds": uptime,
            "started_at": start_epoch,
        })
    result.sort(key=lambda c: (c["state"] != "running", c["name"]))
    return {"containers": result, "count": len(result)}


class ActionResult(BaseModel):
    name: str
    action: str
    state: str
    ok: bool


@app.post("/api/containers/{name}/{action}")
def container_action(name: str, action: str) -> ActionResult:
    """Perform a NON-DESTRUCTIVE lifecycle action: start | stop | restart."""
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(
            400,
            f"action '{action}' not allowed. This server only permits "
            f"{sorted(ALLOWED_ACTIONS)} — never remove/delete.",
        )
    if name not in list_container_names():
        raise HTTPException(404, f"no such container: {name}")

    docker(action, name, timeout=40)

    # report resulting state
    state = docker("inspect", "-f", "{{.State.Status}}", name).strip()
    return ActionResult(name=name, action=action, state=state, ok=True)


# ---------------------------------------------------------------- stats

@app.get("/api/stats")
def stats():
    """Host CPU/mem/disk + per-container resource usage."""
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    try:
        load = psutil.getloadavg()
    except (AttributeError, OSError):
        load = (0.0, 0.0, 0.0)

    host = {
        "cpu_percent": psutil.cpu_percent(interval=0.15),
        "cpu_count": psutil.cpu_count(),
        "load_avg": [round(x, 2) for x in load],
        "mem": {"used": vm.used, "total": vm.total, "percent": vm.percent},
        "disk": {"used": du.used, "total": du.total, "percent": du.percent},
    }

    # per-container usage
    per = []
    try:
        raw = docker(
            "stats", "--no-stream", "--format",
            "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}", timeout=25,
        )
        for line in raw.splitlines():
            parts = line.split("|")
            if len(parts) == 4:
                per.append({
                    "name": parts[0],
                    "cpu_percent": _pct(parts[1]),
                    "mem_usage": parts[2].strip(),
                    "mem_percent": _pct(parts[3]),
                })
    except HTTPException:
        pass
    per.sort(key=lambda c: c["cpu_percent"], reverse=True)

    return {"host": host, "containers": per, "container_count": len(per)}


# ---------------------------------------------------------------- resource history

@app.get("/api/resources/history")
def resources_history(minutes: float = 1440, points: int = 240):
    """Downsampled host CPU/mem/disk/load over the last `minutes` (~`points` buckets)."""
    cutoff = time.time() - minutes * 60
    con = sqlite3.connect(_DB)
    try:
        rows = con.execute(
            "SELECT ts, cpu, mem, disk, load1 FROM samples WHERE ts >= ? ORDER BY ts",
            (cutoff,),
        ).fetchall()
    finally:
        con.close()

    if not rows:
        return {"minutes": minutes, "series": [], "count": 0}

    bucket = max(1.0, (minutes * 60) / max(points, 1))
    agg: dict[int, list] = {}
    for ts, cpu, mem, disk, load1 in rows:
        k = int(ts // bucket)
        a = agg.setdefault(k, [0, 0.0, 0.0, 0.0, 0.0])
        a[0] += 1
        a[1] += cpu
        a[2] += mem
        a[3] += disk
        a[4] += load1

    series = []
    for k in sorted(agg):
        n, c, m, d, l = agg[k]
        series.append({
            "t": k * bucket,
            "cpu": round(c / n, 1),
            "mem": round(m / n, 1),
            "disk": round(d / n, 1),
            "load1": round(l / n, 2),
        })
    return {"minutes": minutes, "bucket_seconds": bucket, "series": series, "count": len(rows)}


# ---------------------------------------------------------------- traffic

def _read_caddy_logs(include_rolled: bool) -> str:
    """Read the current access log; also rolled/gzipped history when requested."""
    if not include_rolled:
        return docker("exec", CADDY_CONTAINER, "cat", CADDY_LOGPATH, timeout=25)
    base = CADDY_LOGPATH[:-4] if CADDY_LOGPATH.endswith(".log") else CADDY_LOGPATH
    # current file, then any rotated (.log) and gzipped (.log.gz) siblings Caddy leaves behind
    cmd = (
        f'cat {CADDY_LOGPATH} 2>/dev/null; '
        f'for f in {base}-*.log; do [ -f "$f" ] && cat "$f"; done 2>/dev/null; '
        f'for f in {base}-*.log.gz; do [ -f "$f" ] && gunzip -c "$f"; done 2>/dev/null; '
        f'true'  # ensure exit 0 even when globs match nothing
    )
    return docker("exec", CADDY_CONTAINER, "sh", "-c", cmd, timeout=45)


def _auto_bucket(minutes: float) -> int:
    """Seconds per data point, chosen so a range yields a sane number of points."""
    if minutes <= 180:      # ≤ 3h  → 1 min
        return 60
    if minutes <= 1440:     # ≤ 24h → 5 min
        return 300
    if minutes <= 10080:    # ≤ 7d  → 1 hour
        return 3600
    return 86400            # 30d   → 1 day


@app.get("/api/traffic")
def traffic(minutes: float = 15, bucket: int = 0):
    """Aggregate the Caddy access log over the last `minutes` into a bucketed series.

    `bucket` = seconds per data point (0 = auto by range). Ranges beyond the live
    file also read rolled/gzipped history.
    """
    bucket = bucket if bucket > 0 else _auto_bucket(minutes)
    cutoff = time.time() - minutes * 60
    include_rolled = minutes > 240  # only pay the decompress cost for longer ranges
    try:
        raw = _read_caddy_logs(include_rolled)
    except HTTPException:
        return {"available": False, "minutes": minutes, "bucket_seconds": bucket,
                "requests": 0, "series": [], "by_host": {}, "status_class": {},
                "rate_limited_429": 0, "top_ips": [], "peak_per_bucket": 0}

    total = bytes_out = rl429 = 0
    by_host: dict[str, int] = {}
    status_class: dict[str, int] = {}
    by_ip: dict[str, int] = {}
    buckets: dict[int, int] = {}
    newest = cutoff

    for line in raw.splitlines():
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
        status = int(e.get("status", 0) or 0)
        total += 1
        bytes_out += int(e.get("size", 0) or 0)
        newest = max(newest, ts)
        host = req.get("host", "?")
        by_host[host] = by_host.get(host, 0) + 1
        cls = f"{status // 100}xx" if status else "0xx"
        status_class[cls] = status_class.get(cls, 0) + 1
        if status == 429:
            rl429 += 1
        ip = req.get("client_ip") or req.get("remote_ip") or "?"
        by_ip[ip] = by_ip.get(ip, 0) + 1
        b = int(ts // bucket)
        buckets[b] = buckets.get(b, 0) + 1

    # dense bucketed series across the window (each point's t = bucket-start epoch)
    start_b = int(cutoff // bucket)
    end_b = int(time.time() // bucket)
    series = [{"t": b * bucket, "count": buckets.get(b, 0)} for b in range(start_b, end_b + 1)]
    peak = max((s["count"] for s in series), default=0)

    top_ips = sorted(by_ip.items(), key=lambda x: -x[1])[:6]
    return {
        "available": True,
        "minutes": minutes,
        "bucket_seconds": bucket,
        "requests": total,
        "requests_per_min": round(total / max(minutes, 1e-9), 2),
        "bytes_out": bytes_out,
        "rate_limited_429": rl429,
        "peak_per_bucket": peak,
        "by_host": dict(sorted(by_host.items(), key=lambda x: -x[1])),
        "status_class": status_class,
        "top_ips": [{"ip": ip, "count": n} for ip, n in top_ips],
        "series": series,
    }


@app.get("/api/health")
def health():
    return {"ok": True, "ts": time.time()}


# ---------------------------------------------------------------- static UI
# Serve the built frontend (web/dist) from the same origin as the API, so the
# whole dashboard is one URL with no CORS/proxy. Only mounted if a build exists;
# in dev, use the Vite server instead. Registered LAST so /api routes win.
_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
