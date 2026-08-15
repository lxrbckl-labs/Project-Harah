"""
ServerManager dashboard — backend API.

Exposes read-only server telemetry (host + container resource usage, Caddy
traffic) and a DELIBERATELY NARROW container-control surface: start / stop /
restart only. There is no code path that removes or deletes a container — by
design. Binds to 127.0.0.1 only; this controls Docker and must not be exposed.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.request
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
    con.execute("CREATE TABLE IF NOT EXISTS csamples (ts REAL, name TEXT, cpu REAL, mem REAL)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_csamples ON csamples(name, ts)")
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
            # per-container usage (docker stats); defs resolve after import completes
            try:
                raw = docker("stats", "--no-stream", "--format",
                             "{{.Name}}|{{.CPUPerc}}|{{.MemPerc}}", timeout=20)
                cs = []
                for line in raw.splitlines():
                    p = line.split("|")
                    if len(p) == 3:
                        cs.append((now, p[0], _pct(p[1]), _pct(p[2])))
                if cs:
                    con.executemany("INSERT INTO csamples VALUES (?,?,?,?)", cs)
                    con.execute("DELETE FROM csamples WHERE ts < ?", (now - HISTORY_RETENTION,))
            except Exception:
                pass
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


def _health_from_status(status: str) -> str:
    s = status.lower()
    if "(unhealthy)" in s:
        return "unhealthy"
    if "(healthy)" in s:
        return "healthy"
    if "health: starting" in s or "(starting)" in s:
        return "starting"
    return "none"


_BYTE_UNITS = {"B": 1, "KB": 1e3, "KIB": 1024, "MB": 1e6, "MIB": 1024 ** 2,
               "GB": 1e9, "GIB": 1024 ** 3, "TB": 1e12, "TIB": 1024 ** 4}


def _parse_bytes(s: str) -> float:
    m = re.match(r"\s*([\d.]+)\s*([KMGT]?i?B)", s or "", re.I)
    if not m:
        return 0.0
    return float(m.group(1)) * _BYTE_UNITS.get(m.group(2).upper(), 1)


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

    # batch inspect: StartedAt, restart count, restarting, compose project.
    # (health comes from the ps Status string — inspecting .State.Health errors on
    #  containers that have no healthcheck.)
    meta: dict[str, dict] = {}
    ids = [r["ID"] for r in rows]
    if ids:
        fmt = ('{{.Id}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Restarting}}|'
               '{{if .Config.Labels}}{{index .Config.Labels "com.docker.compose.project"}}{{end}}')
        for line in docker("inspect", "-f", fmt, *ids).splitlines():
            parts = line.split("|")
            if len(parts) >= 5:
                meta[parts[0]] = {
                    "started": parts[1],
                    "restart_count": int(parts[2]) if parts[2].lstrip("-").isdigit() else 0,
                    "restarting": parts[3] == "true",
                    "project": parts[4] if parts[4] not in ("", "<no value>") else "",
                }

    now = time.time()
    result = []
    for r in rows:
        state = r.get("State", "")
        m = meta.get(r["ID"], {})
        start_epoch = parse_docker_time(m.get("started", ""))
        uptime = int(now - start_epoch) if (state == "running" and start_epoch) else 0
        rc = m.get("restart_count", 0)
        crash = bool(m.get("restarting")) or (rc >= 3 and state == "running" and uptime < 600)
        result.append({
            "id": r["ID"][:12],
            "name": r.get("Names", ""),
            "image": r.get("Image", ""),
            "state": state,                     # running | exited | created | paused
            "status": r.get("Status", ""),      # "Up 3 hours (healthy)" etc.
            "ports": r.get("Ports", ""),
            "uptime_seconds": uptime,
            "started_at": start_epoch,
            "health": _health_from_status(r.get("Status", "")),  # healthy|unhealthy|starting|none
            "restart_count": rc,
            "crash_looping": crash,
            "project": m.get("project", ""),
        })
    result.sort(key=lambda c: (c["state"] != "running", c["project"] or "~", c["name"]))
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


@app.get("/api/containers/{name}/logs")
def container_logs(name: str, tail: int = 200):
    """Recent stdout+stderr for a container (read-only). Many apps log to stderr."""
    if name not in list_container_names():
        raise HTTPException(404, f"no such container: {name}")
    tail = max(1, min(tail, 2000))
    try:
        p = subprocess.run(
            ["docker", "logs", "--tail", str(tail), "--timestamps", name],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "docker logs timed out")
    return {"name": name, "tail": tail, "logs": p.stdout or ""}


@app.get("/api/containers/{name}/history")
def container_history(name: str, minutes: float = 360, points: int = 200):
    """Downsampled per-container CPU% / mem% over the last `minutes`."""
    cutoff = time.time() - minutes * 60
    con = sqlite3.connect(_DB)
    try:
        rows = con.execute(
            "SELECT ts, cpu, mem FROM csamples WHERE name=? AND ts>=? ORDER BY ts",
            (name, cutoff),
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return {"name": name, "series": [], "count": 0}
    bucket = max(1.0, (minutes * 60) / max(points, 1))
    agg: dict[int, list] = {}
    for ts, cpu, mem in rows:
        a = agg.setdefault(int(ts // bucket), [0, 0.0, 0.0])
        a[0] += 1
        a[1] += cpu
        a[2] += mem
    series = [{"t": k * bucket, "cpu": round(c / n, 1), "mem": round(m / n, 1)}
              for k, (n, c, m) in sorted(agg.items())]
    return {"name": name, "series": series, "count": len(rows)}


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

    # macOS: psutil.used (active+wired) diverges from .percent (total-available).
    # Use total-available consistently so used / free / percent all correlate
    # (and match Activity Monitor's "Memory Used").
    mem_used = vm.total - vm.available
    host = {
        "cpu_percent": psutil.cpu_percent(interval=0.15),
        "cpu_count": psutil.cpu_count(),
        "load_avg": [round(x, 2) for x in load],
        "mem": {"used": mem_used, "total": vm.total,
                "free": vm.available, "percent": round(mem_used / vm.total * 100, 1)},
        "disk": {"used": du.used, "total": du.total, "percent": du.percent},
    }

    # per-container usage + aggregate Docker VM memory
    per = []
    docker_used = 0.0
    docker_total = 0.0   # the Docker Desktop VM's memory limit (shared across containers)
    try:
        raw = docker(
            "stats", "--no-stream", "--format",
            "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}", timeout=25,
        )
        for line in raw.splitlines():
            parts = line.split("|")
            if len(parts) == 4:
                used_str, _, limit_str = parts[2].partition("/")
                docker_used += _parse_bytes(used_str)
                docker_total = max(docker_total, _parse_bytes(limit_str))
                per.append({
                    "name": parts[0],
                    "cpu_percent": _pct(parts[1]),
                    "mem_usage": parts[2].strip(),
                    "mem_percent": _pct(parts[3]),
                })
    except HTTPException:
        pass
    per.sort(key=lambda c: c["cpu_percent"], reverse=True)

    docker_mem = {
        "used": int(docker_used),
        "total": int(docker_total),
        "percent": round(docker_used / docker_total * 100, 1) if docker_total else 0.0,
    }
    return {"host": host, "containers": per, "container_count": len(per), "docker_mem": docker_mem}


@app.get("/api/storage")
def storage():
    """Mounted volumes — the boot disk plus external drives under /Volumes/."""
    mounts, seen = [], set()
    for p in psutil.disk_partitions(all=True):
        mp = p.mountpoint
        if mp in seen or not p.device.startswith("/dev/"):
            continue
        if not (mp == "/" or mp.startswith("/Volumes/")):
            continue
        try:
            u = psutil.disk_usage(mp)
        except OSError:
            continue
        if u.total == 0:
            continue
        seen.add(mp)
        mounts.append({
            "mount": mp,
            "name": "Macintosh HD" if mp == "/" else mp.split("/")[-1],
            "device": p.device, "fstype": p.fstype,
            "total": u.total, "used": u.used, "free": u.free, "percent": u.percent,
            "external": mp.startswith("/Volumes/"),
            "containers": [],
        })
    mounts.sort(key=lambda m: (not m["external"], -m["total"]))

    # attribute running containers to the drives they bind-mount onto
    vol_c: dict[str, set] = {m["mount"]: set() for m in mounts}
    try:
        ids = docker("ps", "-q").split()
        if ids:
            fmt = '{{.Name}}~{{range .Mounts}}{{if eq .Type "bind"}}{{.Source}}|{{end}}{{end}}'
            for line in docker("inspect", "-f", fmt, *ids).splitlines():
                name, _, srcs = line.partition("~")
                name = name.lstrip("/")
                for src in filter(None, srcs.split("|")):
                    p = src[len("/host_mnt"):] if src.startswith("/host_mnt") else src  # Docker Desktop prefix
                    p = p or "/"
                    best = None
                    for m in mounts:
                        mp = m["mount"]
                        if p == mp or p.startswith(mp.rstrip("/") + "/"):
                            if best is None or len(mp) > len(best):
                                best = mp
                    if best:
                        vol_c[best].add(name)
    except Exception:
        pass
    for m in mounts:
        m["containers"] = sorted(vol_c[m["mount"]])
    return {"volumes": mounts}


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


# ---------------------------------------------------------------- db backups

BACKUP_DIR = Path("/Users/alexarbuckle/servermanager-backups")
_backup_status: dict = {}   # container -> {state, ts, size?, file?, error?}


def _pg_containers() -> list:
    """Postgres containers with their POSTGRES_USER/DB from env."""
    out = docker("ps", "-a", "--format", "{{.Names}}\t{{.Image}}\t{{.State}}")
    result = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or "postgres" not in parts[1].lower():
            continue
        name, image, state = parts[0], parts[1], parts[2]
        user, db = "postgres", ""
        try:
            env = docker("inspect", "-f", "{{range .Config.Env}}{{println .}}{{end}}", name)
            for e in env.splitlines():
                if e.startswith("POSTGRES_USER="):
                    user = e.split("=", 1)[1]
                elif e.startswith("POSTGRES_DB="):
                    db = e.split("=", 1)[1]
        except Exception:
            pass
        result.append({"name": name, "image": image, "state": state, "user": user, "db": db})
    return result


def _latest_backup(name: str):
    if not BACKUP_DIR.exists():
        return None
    files = sorted(BACKUP_DIR.glob(f"{name}-*.sql.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    st = files[0].stat()
    return {"file": files[0].name, "ts": st.st_mtime, "size": st.st_size}


def _run_backup(name: str, user: str) -> None:
    _backup_status[name] = {"state": "running", "ts": time.time()}
    out_path = BACKUP_DIR / f"{name}-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}.sql.gz"
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            f"docker exec {name} pg_dumpall -U {user} | gzip > '{out_path}'",
            shell=True, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0:
            out_path.unlink(missing_ok=True)
            _backup_status[name] = {"state": "error", "ts": time.time(),
                                    "error": (proc.stderr.strip()[-300:] or "pg_dumpall failed")}
            return
        _backup_status[name] = {"state": "done", "ts": time.time(),
                                "size": out_path.stat().st_size, "file": out_path.name}
    except Exception as e:
        _backup_status[name] = {"state": "error", "ts": time.time(), "error": str(e)}


@app.get("/api/backups")
def backups():
    dbs = _pg_containers()
    for d in dbs:
        d["last_backup"] = _latest_backup(d["name"])
        d["status"] = _backup_status.get(d["name"], {"state": "idle"})
    return {"databases": dbs, "backup_dir": str(BACKUP_DIR)}


@app.post("/api/backups/{name}")
def backup_now(name: str):
    dbs = {d["name"]: d for d in _pg_containers()}
    if name not in dbs:
        raise HTTPException(404, f"no postgres container named {name}")
    if dbs[name]["state"] != "running":
        raise HTTPException(409, "container is not running — start it before backing up")
    if _backup_status.get(name, {}).get("state") == "running":
        raise HTTPException(409, "a backup is already running for this database")
    threading.Thread(target=_run_backup, args=(name, dbs[name]["user"]), daemon=True).start()
    return {"started": name}


# ---------------------------------------------------------------- repo grooming (harah)

GROOMING_STATE = Path.home() / ".harah" / "grooming-state.json"


@app.get("/api/grooming")
def grooming():
    """State of the harah repo-grooming routine (dependabot upkeep).

    Written by ~/.claude/skills/harah/grooming/groom.sh after every pass."""
    try:
        if GROOMING_STATE.exists():
            return json.loads(GROOMING_STATE.read_text())
    except Exception as e:
        return {"error": str(e)}
    return {"last_run": None, "dry_run": False, "merged": [], "queued": [],
            "totals": {"merged": 0, "queued": 0, "repos_with_prs": 0}}


# ---------------------------------------------------------------- pinned containers

_PINS_PATH = Path(__file__).resolve().parent / "pins.json"


def _load_pins() -> list:
    try:
        if _PINS_PATH.exists():
            return sorted(set(json.loads(_PINS_PATH.read_text())))
    except Exception:
        pass
    return []


@app.get("/api/pins")
def get_pins():
    return {"pinned": _load_pins()}


class PinReq(BaseModel):
    name: str
    pinned: bool


@app.post("/api/pins")
def set_pin(body: PinReq):
    pins = set(_load_pins())
    pins.add(body.name) if body.pinned else pins.discard(body.name)
    try:
        _PINS_PATH.write_text(json.dumps(sorted(pins)))
    except Exception as e:
        raise HTTPException(500, f"could not save pins: {e}")
    return {"pinned": sorted(pins)}


@app.get("/api/health")
def health():
    return {"ok": True, "ts": time.time()}


# ---------------------------------------------------------------- guardian (auto-defense)
# Watches the Caddy access log for brute-force / flooding and, ONLY for containers
# explicitly armed while the master switch is on, auto-stops them (never deletes).
# Detection always runs (informational); enforcement is opt-in and gated.

GUARDIAN_CFG_PATH = Path(__file__).resolve().parent / "guardian_config.json"
CADDYFILE_HOST_PATH = "/Users/alexarbuckle/caddyfile"

_guardian_lock = threading.Lock()
_guardian = {
    "enabled": False,           # master enforcement switch
    "armed": [],                # container names eligible for auto-stop
    "window_sec": 60,
    "ip_req_threshold": 40,     # requests from one IP in window → attack
    "auth_fail_threshold": 20,  # 401/403/429 to a host in window → attack
    "cooldown_sec": 300,
    "ignore_private": True,     # fully exempt private/LAN/loopback source IPs from detection
    "allowlist": [],            # extra exact IPs / prefixes to always permit
    "banned_ips": [],           # IPs blocked at Caddy (respond 403)
}

CADDY_IMAGE = "caddy-ratelimit:latest"
CADDY_COMPOSE = "/Users/alexarbuckle/docker-bare-run/caddy/docker-compose.yml"
_threats: list = []
_actions: list = []
_cooldowns: dict = {}


def _load_guardian_cfg() -> None:
    try:
        if GUARDIAN_CFG_PATH.exists():
            data = json.loads(GUARDIAN_CFG_PATH.read_text())
            for k in list(_guardian):
                if k in data:
                    _guardian[k] = data[k]
    except Exception:
        pass


def _save_guardian_cfg() -> None:
    try:
        GUARDIAN_CFG_PATH.write_text(json.dumps(_guardian, indent=2))
    except Exception:
        pass


def _is_private_ip(ip: str) -> bool:
    return (not ip or ip == "?" or ip.startswith(("10.", "192.168.", "127.", "172.",
            "::1", "fd", "fe80")))


def _exempt(ip: str, cfg: dict) -> bool:
    """Permitted sources that never count toward attack detection."""
    if cfg.get("ignore_private") and _is_private_ip(ip):
        return True
    return any(ip == a or ip.startswith(a) for a in cfg.get("allowlist", []))


_geoip_cache: dict = {}


def _geoip(ip: str):
    """Best-effort country/city for a public IP (cached). None for private/unknown."""
    if ip in _geoip_cache:
        return _geoip_cache[ip]
    result = None
    if not _is_private_ip(ip):
        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city"
            with urllib.request.urlopen(url, timeout=4) as r:
                d = json.loads(r.read().decode())
            if d.get("status") == "success":
                result = {"country": d.get("country"), "cc": d.get("countryCode"), "city": d.get("city")}
        except Exception:
            result = None
    _geoip_cache[ip] = result
    return result


def _host_container_map() -> dict:
    """host → container, from Caddyfile upstream ports matched to docker published ports."""
    port2c: dict = {}
    try:
        out = docker("ps", "-a", "--format", "{{.Names}}\t{{.Ports}}")
        for line in out.splitlines():
            if "\t" not in line:
                continue
            name, ports = line.split("\t", 1)
            for p in re.findall(r":(\d+)->", ports):
                port2c.setdefault(p, name)
    except Exception:
        pass
    mapping: dict = {}
    try:
        txt = Path(CADDYFILE_HOST_PATH).read_text()
        cur = None
        for raw in txt.splitlines():
            s = raw.strip()
            if s.endswith("{") and "." in s.split()[0] and not s.startswith(("(", "{")):
                cur = s[:-1].strip()
            m = re.search(r"reverse_proxy\s+\S*?:(\d+)", s)
            if m and cur and cur not in mapping and m.group(1) in port2c:
                mapping[cur] = port2c[m.group(1)]
    except Exception:
        pass
    return mapping


def _detect_once() -> None:
    global _threats
    with _guardian_lock:
        cfg = dict(_guardian)
    cutoff = time.time() - cfg["window_sec"]
    try:
        raw = _read_caddy_logs(False)
    except HTTPException:
        return

    per_host: dict = {}
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
        host = req.get("host", "?")
        ip = req.get("client_ip") or req.get("remote_ip") or "?"
        if _exempt(ip, cfg):        # permitted source (LAN/local or allowlisted) — ignore
            continue
        status = int(e.get("status", 0) or 0)
        h = per_host.setdefault(host, {"ips": {}, "fails": 0, "total": 0})
        h["total"] += 1
        h["ips"][ip] = h["ips"].get(ip, 0) + 1
        if status in (401, 403, 429):
            h["fails"] += 1

    mapping = _host_container_map()
    threats = []
    for host, d in per_host.items():
        top_ip, top_n = max(d["ips"].items(), key=lambda x: x[1]) if d["ips"] else ("?", 0)
        if not (top_n >= cfg["ip_req_threshold"] or d["fails"] >= cfg["auth_fail_threshold"]):
            continue
        container = mapping.get(host)
        sev = "high" if (top_n >= cfg["ip_req_threshold"] * 2
                         or d["fails"] >= cfg["auth_fail_threshold"] * 2) else "elevated"
        priv = _is_private_ip(top_ip)
        threats.append({
            "host": host, "container": container, "top_ip": top_ip, "top_ip_count": top_n,
            "auth_fails": d["fails"], "total": d["total"], "window_sec": cfg["window_sec"],
            "private": priv, "severity": sev, "ts": time.time(), "geo": _geoip(top_ip),
        })
        if (cfg["enabled"] and container and container in cfg["armed"]
                and _cooldowns.get(container, 0) < time.time()):
            try:
                docker("stop", container, timeout=40)
                _cooldowns[container] = time.time() + cfg["cooldown_sec"]
                _actions.insert(0, {
                    "container": container, "host": host, "top_ip": top_ip,
                    "reason": f"{top_n} req / {d['fails']} auth-fails from {top_ip} in {cfg['window_sec']}s",
                    "ts": time.time(),
                })
                del _actions[20:]
            except Exception:
                pass
    threats.sort(key=lambda t: -max(t["top_ip_count"], t["auth_fails"]))
    _threats = threats


def _guardian_loop() -> None:
    while True:
        try:
            _detect_once()
        except Exception:
            pass
        time.sleep(15)


def _render_accesslog_snippet(banned: list) -> list:
    out = ["(accesslog) {"]
    if banned:
        out.append("\t@__sm_banned remote_ip " + " ".join(banned))
        out.append("\trespond @__sm_banned 403")
    out += [
        "\tlog {",
        "\t\toutput file /data/access.log {",
        "\t\t\troll_size 50MiB",
        "\t\t\troll_keep 5",
        "\t\t}",
        "\t\tformat json",
        "\t}",
        "}",
    ]
    return out


def _rewrite_caddyfile(text: str, banned: list) -> str | None:
    """Replace the (accesslog) snippet block, injecting a ban matcher if needed."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == "(accesslog) {"), None)
    if start is None:
        return None
    depth, end = 0, None
    for j in range(start, len(lines)):
        depth += lines[j].count("{") - lines[j].count("}")
        if depth == 0:
            end = j
            break
    if end is None:
        return None
    return "\n".join(lines[:start] + _render_accesslog_snippet(banned) + lines[end + 1:]) + "\n"


def _apply_bans(banned: list) -> None:
    """Write banned IPs into the Caddyfile (validated) and reload Caddy."""
    text = Path(CADDYFILE_HOST_PATH).read_text()
    new = _rewrite_caddyfile(text, banned)
    if new is None:
        raise RuntimeError("could not locate the (accesslog) snippet in the Caddyfile")
    tmp = CADDYFILE_HOST_PATH + ".smnew"
    Path(tmp).write_text(new)
    try:
        v = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{tmp}:/etc/caddy/Caddyfile:ro", CADDY_IMAGE,
             "caddy", "validate", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"],
            capture_output=True, text=True, timeout=60)
        if v.returncode != 0:
            raise RuntimeError("caddy validate failed: " + (v.stderr.strip()[-300:] or "unknown"))
        shutil.copy2(CADDYFILE_HOST_PATH, CADDYFILE_HOST_PATH + ".bak.bans")
        with open(CADDYFILE_HOST_PATH, "w") as f:   # in-place write keeps inode → reload works
            f.write(new)
    finally:
        Path(tmp).unlink(missing_ok=True)
    r = subprocess.run(
        ["docker", "exec", CADDY_CONTAINER, "caddy", "reload",
         "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"],
        capture_output=True, text=True, timeout=40)
    if r.returncode != 0:  # reload flaky on Docker Desktop bind mounts → force-recreate
        subprocess.run(["docker", "compose", "-f", CADDY_COMPOSE, "up", "-d", "--force-recreate"],
                       capture_output=True, text=True, timeout=90)


class BanReq(BaseModel):
    ip: str
    banned: bool


@app.post("/api/guardian/ban")
def guardian_ban(body: BanReq):
    ip = body.ip.strip()
    if not ip or _is_private_ip(ip):
        raise HTTPException(400, "refusing to ban a private/LAN/loopback IP")
    with _guardian_lock:
        bans = set(_guardian.get("banned_ips", []))
        bans.add(ip) if body.banned else bans.discard(ip)
        _guardian["banned_ips"] = sorted(bans)
        _save_guardian_cfg()
        current = list(_guardian["banned_ips"])
    try:
        _apply_bans(current)
    except Exception as e:
        raise HTTPException(500, f"saved, but applying to Caddy failed: {e}")
    return {"banned_ips": current}


@app.get("/api/guardian")
def guardian_status():
    with _guardian_lock:
        cfg = dict(_guardian)
    return {**cfg, "threats": _threats, "actions": _actions[:10], "mapping": _host_container_map()}


class GuardianToggle(BaseModel):
    enabled: bool


@app.post("/api/guardian/toggle")
def guardian_toggle(body: GuardianToggle):
    with _guardian_lock:
        _guardian["enabled"] = body.enabled
        _save_guardian_cfg()
        return {"enabled": _guardian["enabled"]}


class GuardianArm(BaseModel):
    container: str
    armed: bool


@app.post("/api/guardian/arm")
def guardian_arm(body: GuardianArm):
    with _guardian_lock:
        armed = set(_guardian["armed"])
        armed.add(body.container) if body.armed else armed.discard(body.container)
        _guardian["armed"] = sorted(armed)
        _save_guardian_cfg()
        return {"armed": _guardian["armed"]}


class GuardianConfig(BaseModel):
    ignore_private: bool | None = None
    allowlist: list[str] | None = None
    ip_req_threshold: int | None = None
    auth_fail_threshold: int | None = None


@app.post("/api/guardian/config")
def guardian_config(body: GuardianConfig):
    with _guardian_lock:
        for k, v in body.model_dump(exclude_none=True).items():
            if k in _guardian:
                _guardian[k] = v
        _save_guardian_cfg()
        return {k: _guardian[k] for k in ("ignore_private", "allowlist",
                                          "ip_req_threshold", "auth_fail_threshold")}


_load_guardian_cfg()
threading.Thread(target=_guardian_loop, daemon=True).start()


# ---------------------------------------------------------------- static UI
# Serve the built frontend (web/dist) from the same origin as the API, so the
# whole dashboard is one URL with no CORS/proxy. Only mounted if a build exists;
# in dev, use the Vite server instead. Registered LAST so /api routes win.
_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")
