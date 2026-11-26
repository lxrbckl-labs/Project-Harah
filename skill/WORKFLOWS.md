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
`tools/caddy-traffic.py -n 60` for a window summary. To attribute by source, parse `/data/access.log` inside
the caddy container. Remember the IP-masking gotcha (SKILL.md) before
concluding anything about "attackers".

### Back up a database
By hand, per Postgres container, into `~/servermanager-backups/` (the command
the retired dashboard's panel ran; `POSTGRES_USER` is in the container's env):
```sh
docker exec <container> pg_dumpall -U <user> | gzip > ~/servermanager-backups/<container>-$(date +%Y%m%d-%H%M%S).sql.gz
```
There is **no schedule and no button** — a backup happens only when someone
runs this.

### Add or change a scheduled routine
Machinery goes in `skill/<name>/` with a self-locating `enable.sh`/`disable.sh`
(plist points at the script beside it, so moving the checkout is survivable).
Then verify it **the way launchd runs it** — a manual run proves nothing:
```sh
bash skill/<name>/enable.sh
launchctl kickstart -k gui/$(id -u)/com.alex.<label>
launchctl list | grep <label>          # exit code MUST be 0 — 126 = TCC block
tail -20 ~/Library/Logs/harah-<name>.log
```
Keep the checkout out of `~/Documents`, `~/Desktop`, `~/Downloads` (TCC blocks
launchd there). Anything driving a `claude -p` agent must be a **GUI-domain**
LaunchAgent — the OAuth token lives in the login Keychain. Give any agent
routine a `--dry-run` and use it before the first live pass.

### Check security alerts / why grooming's schedule changed
```sh
tail -20 ~/Library/Logs/harah-alerts.log        # last pass + any cadence change
cat ~/.harah/grooming-cadence                   # baseline | seconds
bash skill/alerts/alerts.sh                     # force a pass now (read-only)
bash skill/grooming/set-cadence.sh baseline     # manually return to daily 04:30
```
The same state is in `~/.harah/alerts-state.json`. Escalated cadence only makes
grooming run sooner — see `grooming/POLICY.md`, "Cadence is not authority".

### Ship a change
Commit **and push** — the repo
tracks `origin/main`, and Alex expects this to happen automatically without
being asked:
```sh
cd ~/lxrbckl-dev/Project-Harah && git add -A && git commit -m "…" && git push origin main
```
