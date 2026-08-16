# ServerManager Dashboard

A dark, glassmorphic web dashboard for monitoring a Docker + Caddy server —
host resource usage, Caddy traffic, and container lifecycle control.

- **Frontend:** React + TypeScript (Vite), with a [ReactBits](https://reactbits.dev)
  **Aurora** WebGL background.
- **Backend:** FastAPI. Reads Docker + the Caddy access log; exposes host stats,
  traffic, and a **start / stop / restart only** container-control API.

## Safety model

- **No delete, ever.** The backend's `ALLOWED_ACTIONS` is `{start, stop, restart}`.
  There is no code path that removes a container; `remove`/`rm`/`kill`/`delete`
  return HTTP 400.
- **Localhost-only.** The API controls Docker — run it bound to `127.0.0.1` and do
  **not** expose it through Caddy. Add authenticated remote access as a deliberate
  step later if needed.

## Run it

Backend (terminal 1):
```sh
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # first time
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8770
```

Frontend (terminal 2):
```sh
cd web
npm install          # first time
npm run dev          # http://localhost:5173  (proxies /api to :8770)
```

Open http://localhost:5173.

## Serve on the LAN (single service)

Build the frontend once; FastAPI then serves the UI **and** API from one port.
Bind to `0.0.0.0` to reach it from other devices:

```sh
cd web && npm run build          # produces web/dist (served automatically if present)
cd ../backend
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8770
```

Then browse to `http://<server-lan-ip>:8770` from any device on the network.

## Run it as a service (the mini)

Don't hand-start it in a terminal — that leaves an orphan process that dies
with the terminal and never comes back after a reboot. Install the launchd
job instead (builds are still your job: `cd web && npm run build` first):

```sh
./enable.sh          # installs com.lxrbckl.servermanager-dashboard, verifies /api/health
./disable.sh         # stops and uninstalls it
```

`enable.sh` is self-locating — re-run it after moving the checkout. It sets
`KeepAlive` (respawns on crash) and `RunAtLoad` (survives reboot), releases
`:8770` from any hand-started uvicorn, and logs to
`~/Library/Logs/servermanager-dashboard.log`.
macOS may prompt to allow incoming connections the first time. ⚠️ There is **no
auth** — only do this on a fully trusted network.

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/containers` | all containers: state, uptime, ports |
| POST | `/api/containers/{name}/{start\|stop\|restart}` | lifecycle (never delete) |
| GET  | `/api/stats` | host CPU/mem/disk + per-container usage |
| GET  | `/api/traffic?minutes=N` | Caddy traffic aggregate + per-minute series |
| GET  | `/api/health` | liveness |
