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
import subprocess
import time
from datetime import datetime, timezone

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# The ONLY container actions this server will ever perform. `rm`/`remove` is
# intentionally absent and must never be added here.
ALLOWED_ACTIONS = {"start", "stop", "restart"}

CADDY_CONTAINER = "caddy"
CADDY_LOGPATH = "/data/access.log"

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


# ---------------------------------------------------------------- traffic

@app.get("/api/traffic")
def traffic(minutes: float = 15):
    """Aggregate the Caddy access log over the last `minutes`, with a per-minute series."""
    cutoff = time.time() - minutes * 60
    try:
        raw = docker("exec", CADDY_CONTAINER, "cat", CADDY_LOGPATH, timeout=25)
    except HTTPException:
        return {"available": False, "minutes": minutes, "requests": 0,
                "series": [], "by_host": {}, "status_class": {},
                "rate_limited_429": 0, "top_ips": []}

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
        buckets[int(ts // 60)] = buckets.get(int(ts // 60), 0) + 1

    # dense per-minute series across the window
    start_min = int(cutoff // 60)
    end_min = int(time.time() // 60)
    series = [{"minute": m, "count": buckets.get(m, 0)} for m in range(start_min, end_min + 1)]

    top_ips = sorted(by_ip.items(), key=lambda x: -x[1])[:6]
    return {
        "available": True,
        "minutes": minutes,
        "requests": total,
        "requests_per_min": round(total / max(minutes, 1e-9), 2),
        "bytes_out": bytes_out,
        "rate_limited_429": rl429,
        "by_host": dict(sorted(by_host.items(), key=lambda x: -x[1])),
        "status_class": status_class,
        "top_ips": [{"ip": ip, "count": n} for ip, n in top_ips],
        "series": series,
    }


@app.get("/api/health")
def health():
    return {"ok": True, "ts": time.time()}
