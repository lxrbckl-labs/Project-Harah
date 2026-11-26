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
Add the site block → `import accesslog` and `import security` inside it → **if
the app has a login, add its rate limit (below) before the first apply** → run
`tools/caddy-ensure-logging.py --caddyfile ~/caddyfile --fix` → validate → apply.

The rate limit (guardrail in SERVER.md): find the path the login form POSTs
credentials to (browser devtools → Network, or the app's API docs; for an
admin panel, its path prefix too), then inside the site block, before
`reverse_proxy`:
```caddyfile
	# Brute-force protection: cap login attempts per client IP.
	# <path> = the endpoint the login form POSTs to.
	@<site>_auth path <login-POST-path> [<admin-path> <admin-path>/*]
	rate_limit @<site>_auth {
		zone <site>_auth {
			key {remote_host}
			events 8
			window 1m
		}
	}
```
Eight events a minute per client is the house setting (Vaultwarden and Immich
run it); a real user never hits it, a dictionary run gets 429 after the eighth
try. Prove it after the apply: nine bad logins from one machine in under a
minute, the ninth answers 429. `{remote_host}` is the real client only because
Caddy terminates TLS itself; behind another proxy it would be that proxy's
address, so re-check the key if the topology ever changes.

### Audit login rate limits
```sh
skill/caddy/login-limits.sh            # reads ~/caddyfile; pass another path to check a draft
```
Read-only. Lists every site block, whether it carries a `rate_limit`, and the
known login endpoint (the table is in the script; add a line when a new app
with a login is hosted). A site marked `LOGIN` without `rate_limit` is the gap
the guardrail talks about: take the list to Alex with the proposed endpoint
and apply on his word, one site per validated apply. A site marked `unknown`
needs a look at the app before it can be called safe.

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
