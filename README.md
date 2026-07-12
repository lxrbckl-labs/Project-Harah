# ServerManager

A portable toolkit + agent playbook for **monitoring Docker + Caddy servers**.

Point an agent (or yourself) at any server running Docker behind a Caddy reverse
proxy, follow [`AGENT.md`](AGENT.md), and come out the other side with request
monitoring, container health checks, and scheduled reporting in place.

ServerManager is deliberately **Docker- and Caddy-oriented**. It assumes:

- Docker is the container runtime (`docker ps`, `docker exec`, … are available).
- A **Caddy** container is the reverse proxy, with its `Caddyfile` reachable
  (typically a bind mount from the host).

## What's here

| Path | Purpose |
|------|---------|
| [`AGENT.md`](AGENT.md) | The setup playbook — the ordered steps an agent follows to instrument a server. |
| `tools/` | The monitors themselves. Self-contained, stdlib-only where possible. |
| `templates/` | Drop-in fragments: the Caddy access-log snippet, a launchd scheduling plist. |
| `lib/` | Shared helpers used by the tools. |
| `config.example.env` | Per-server settings (container name, log path, thresholds). Copy to `config.env`. |

## Tools

- **`tools/caddy-traffic.py`** — reads Caddy's JSON access log and reports request
  volume, throughput, status-code mix, per-site breakdown, top client IPs, and
  rate-limit (429) activity over a rolling window. `--watch` to loop, `--json`
  for machine output.
- **`tools/caddy-ensure-logging.py`** — coverage guard. Caddy logs per-site, so a
  newly-added subdomain with no `import accesslog` is invisible to the monitor.
  This scans the Caddyfile and flags (`--check`) or auto-injects (`--fix`) the
  logging snippet into any site block that's missing it. Run it after adding
  channels so coverage never drifts.

## Quickstart

```sh
cp config.example.env config.env      # then edit for this server
python3 tools/caddy-traffic.py -n 15  # last 15 min of traffic through Caddy
```

See [`AGENT.md`](AGENT.md) for the full "instrument a fresh server" flow.
