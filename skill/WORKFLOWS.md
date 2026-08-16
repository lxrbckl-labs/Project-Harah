# Standard workflows (on-demand — read when actually doing the task)

### Change the Caddy config
```sh
cp ~/caddyfile ~/caddyfile.bak.$(date +%F)
# edit, then validate against the CUSTOM image (it has the rate-limit plugin):
docker run --rm -v ~/caddyfile:/etc/caddy/Caddyfile:ro caddy-ratelimit:latest \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose -f ~/docker-bare-run/caddy/docker-compose.yml up -d --force-recreate
```
Caddy runs a **custom image** (`caddy-ratelimit:latest`, stock Caddy +
`caddy-ratelimit` compiled via xcaddy, see `~/docker-bare-run/caddy/Dockerfile`).
If it's ever missing, rebuild before composing or the container won't start.

### Add a subdomain
Add the site block → `import accesslog` inside it → run
`tools/caddy-ensure-logging.py --caddyfile ~/caddyfile --fix` → validate → apply.

### Investigate traffic or a suspected attack
`tools/caddy-traffic.py -n 60` for a window summary, or read the dashboard's
Caddy Traffic panel. To attribute by source, parse `/data/access.log` inside
the caddy container. Remember the IP-masking gotcha (SKILL.md) before
concluding anything about "attackers".

### Back up a database
The dashboard's Database Backups panel runs `pg_dumpall` per Postgres
container into `~/servermanager-backups/`. There is **no schedule yet** —
backups are manual.

### Ship a change
Build the frontend if you touched it, then commit **and push** — the repo
tracks `origin/main`, and Alex expects this to happen automatically without
being asked:
```sh
cd ~/Documents/ServerManager && git add -A && git commit -m "…" && git push origin main
```
