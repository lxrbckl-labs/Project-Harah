# ServerManager — Agent Playbook

This is the ordered procedure an agent follows to set up monitoring on a
**Docker + Caddy** server. It assumes shell access to the host (local or over
SSH) and that Docker is usable without prompting.

The goal state: Caddy is emitting access logs, the ServerManager tools are
installed and runnable, and at least the traffic monitor is scheduled to run on
an interval with its output captured.

> **Guardrails.** Monitoring is read-only, but instrumenting a server is not.
> Adding access logging and (re)starting Caddy touches a live reverse proxy.
> - Never touch application containers or their data — only the Caddy layer.
> - Prefer reversible actions; `stop`, never `rm`, unless explicitly told.
> - Confirm before anything that recreates/restarts a container in production.
> - Back up the `Caddyfile` before editing it.

---

## Step 0 — Discover the server

Build a picture before changing anything.

```sh
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Identify:
- **The Caddy container** — usually named `caddy`, image `caddy*`. Note the name.
- **How its Caddyfile is provided** — inspect the mounts:
  ```sh
  docker inspect <caddy> --format '{{json .Mounts}}'
  ```
  Most setups **bind-mount** the Caddyfile from the host (e.g.
  `/host/path/Caddyfile:/etc/caddy/Caddyfile`). Record the host path — that's the
  file you edit.
- **The sites** — read the Caddyfile to enumerate the reverse-proxied hosts.

Record findings in `config.env` (copy from `config.example.env`): at minimum the
Caddy container name and the access-log path you'll use.

---

## Step 1 — Instrument Caddy with access logging

Caddy does **not** log requests by default, and there is **no global switch** —
access logging is enabled per-site with a `log` directive. ServerManager's
pattern: define one reusable snippet and `import` it into every site block, all
writing to a single JSON log inside the `caddy_data` volume.

1. **Back up** the Caddyfile: `cp <caddyfile> <caddyfile>.bak.<date>`.
2. Add the snippet from [`templates/accesslog.snippet`](templates/accesslog.snippet)
   near the top of the Caddyfile (after any global `{ ... }` options block).
3. Add `import accesslog` as the first line inside **each** site block.
4. **Validate** before applying — run against the running image so plugins match:
   ```sh
   docker run --rm -v <caddyfile>:/etc/caddy/Caddyfile:ro <caddy-image> \
     caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
   ```

The log lands at `/data/access.log` inside the container (in the `caddy_data`
volume) — no new mounts required.

---

## Step 2 — Apply the config

> ⚠️ **Docker Desktop single-file bind-mount gotcha.** On Docker Desktop
> (macOS/Windows), editing the host Caddyfile and running `caddy reload` inside
> the running container often **fails** — the container's mount is pinned to the
> file's original inode and reads a stale/truncated copy (validation passes on
> the host file, but reload errors on a bogus line). `caddy fmt` in a throwaway
> container edits in place and is fine; live `reload` after a host edit is not.

**Reliable apply:** recreate the container so it re-mounts the current file.
Caddy's certs live in **external named volumes**, so a recreate is safe and keeps
them:

```sh
docker compose -f <caddy-compose-dir>/docker-compose.yml up -d --force-recreate
```

On a native-Linux Docker host (not Docker Desktop), `docker exec <caddy> caddy
reload --config /etc/caddy/Caddyfile --adapter caddyfile` is usually reliable —
prefer it there to avoid the restart blip.

**Verify** logging works:
```sh
curl -sk https://<a-site>/ -o /dev/null
docker exec <caddy> sh -c 'tail -n1 /data/access.log'
```
You should see a JSON line with `request.host`, `status`, `size`, etc.

---

## Step 3 — Install the tools

Place this repo on the host (or run it remotely). The tools read the log via
`docker exec <caddy> cat <logpath>`, so they need Docker access, not a mount.

Smoke-test the traffic monitor:
```sh
python3 tools/caddy-traffic.py -n 15
```

---

## Step 4 — Schedule

Pick a cadence and capture output.

- **Quick / foreground:** `caddy-traffic.py -n 10 --watch` (lasts as long as the
  shell stays open).
- **Background on macOS:** install a launchd agent from
  [`templates/launchd.plist`](templates/launchd.plist) — fill in the interval and
  an output path, then `launchctl load` it.
- **Background on Linux:** a `cron` entry or systemd timer running the same command.

Decide where output goes: a rolling text log for humans, and/or `--json` piped to
a file a future dashboard can read.

---

## Step 5 — (Optional) Alerting & health

Extensions to layer on once the base is running:
- Flag spikes in `429` (rate-limit) or `5xx` counts between runs.
- Container health: `docker ps` unhealthy/exited containers.
- Cert expiry: inspect Caddy's stored certs for near-expiry domains.
- Disk / volume pressure on the Docker host.

Each becomes a new `tools/` citizen following the same shape: read-only, config-driven, `--json`-capable.

---

## Reference implementation

The canonical worked example is the author's Mac homelab (Docker Desktop, ~45
containers, Caddy fronting `*.lxrbckl.com`). The rate-limiting + access-logging
setup there is what this playbook generalizes.
