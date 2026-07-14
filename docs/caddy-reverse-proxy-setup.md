# Caddy Reverse Proxy — Homelab Setup

A reproducible guide to standing up **Caddy** as a reverse proxy for a homelab,
with **automatic HTTPS**, **per-IP brute-force rate limiting**, and **JSON access
logging**. This is the exact pattern I run — swap in your own domains, upstream
IPs, and services.

> Works on any Docker host. Notes call out where **Docker Desktop (macOS/Windows)**
> differs from a native **Linux** Docker host.

---

## What you get

- **Automatic TLS** — Caddy fetches & renews Let's Encrypt certs for every domain, no config.
- **One file to route everything** — a `Caddyfile` mapping `sub.domain.com → internal:port`.
- **Brute-force protection** — cap login attempts per client IP on the endpoints that matter.
- **Access logs** — one JSON log of every request, handy for monitoring/debugging.

---

## Prerequisites

1. **Docker + Docker Compose** installed on the server.
2. **A domain** with DNS records (A/AAAA) pointing each subdomain at your server's
   public IP. (For LAN-only, you can use internal DNS, but public certs need public DNS.)
3. **Ports 80 and 443** reachable from the internet (forward them on your router to
   the server). Caddy needs port 80 for the ACME HTTP challenge and 443 for HTTPS.

---

## Step 1 — Project folder

```sh
mkdir -p ~/caddy && cd ~/caddy
```

You'll create three files here: `Dockerfile`, `docker-compose.yml`, `Caddyfile`.

---

## Step 2 — Custom Caddy image (adds the rate-limit plugin)

Rate limiting isn't in stock Caddy — it's a plugin
([`caddy-ratelimit`](https://github.com/mholt/caddy-ratelimit)), so we compile a
tiny custom image. Create **`Dockerfile`**:

```dockerfile
# Stock Caddy + the caddy-ratelimit plugin, compiled in with xcaddy.
FROM caddy:builder AS builder
RUN xcaddy build --with github.com/mholt/caddy-ratelimit

FROM caddy:latest
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

> Don't want rate limiting? Skip this file and use `image: caddy:latest` in the
> compose file below — everything else still works.

---

## Step 3 — Compose file

Create **`docker-compose.yml`**:

```yaml
name: caddy
services:
  caddy:
    build: .                       # builds the Dockerfile above (the rate-limit image)
    # image: caddy:latest          # ...or use this line instead and delete `build: .`
    container_name: caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - caddy_data:/data           # TLS certs live here — persist this!
      - caddy_config:/config
      - ./Caddyfile:/etc/caddy/Caddyfile
    extra_hosts:
      - "host.docker.internal:host-gateway"   # lets Caddy reach services on the host

volumes:
  caddy_data:
  caddy_config:
```

The `caddy_data` volume holds your issued certificates — **keep it** so you don't
re-request certs (Let's Encrypt has rate limits) on every recreate.

---

## Step 4 — The Caddyfile

Create **`Caddyfile`**. This is the whole config — global options, a reusable
logging snippet, then one block per site. Replace domains/IPs with yours.

```caddyfile
# ---- global options ----
{
    # Required so the rate_limit plugin runs before the proxy.
    # (Delete this block if you're using stock caddy without the plugin.)
    order rate_limit before reverse_proxy
}

# ---- reusable access-log snippet ----
# `import accesslog` inside a site block turns on JSON logging for it.
(accesslog) {
    log {
        output file /data/access.log {
            roll_size 50MiB
            roll_keep 5
        }
        format json
    }
}

# ---- a plain reverse-proxied service ----
app.example.com {
    import accesslog
    reverse_proxy 192.168.1.50:8080
    encode gzip
}

# ---- a service WITH brute-force protection on its login endpoint ----
# Example: a password manager. Cap login/admin hits to 8 per minute per IP;
# over that, the client gets 429 Too Many Requests (the real login is unaffected).
vault.example.com {
    import accesslog
    @login path /identity/connect/token /admin /admin/*
    rate_limit @login {
        zone vault_login {
            key    {remote_host}   # per client IP
            events 8               # allowed requests...
            window 1m              # ...per minute
        }
    }
    reverse_proxy 192.168.1.50:8050
    encode gzip
}

# ---- a service on the SAME host as Caddy ----
dashboard.example.com {
    import accesslog
    reverse_proxy host.docker.internal:3000
}
```

**Notes**
- **HTTPS is automatic** — just naming the site (`app.example.com { ... }`) makes
  Caddy get and renew its cert. No cert config needed.
- **Rate limiting is per-site and opt-in.** Put the `rate_limit` block only on the
  endpoints worth protecting (login/auth paths), not the whole site — legit users
  log in a handful of times; an attacker floods one path.
- **Find your login path.** Attackers hit the API endpoint the login form POSTs to,
  not the web page. Common ones: Vaultwarden `→ /identity/connect/token`,
  Immich `→ /api/auth/login`. Check your app's docs or watch the access log.
- **`import accesslog` is per-site** — Caddy has no global "log everything" switch,
  so add it to each block you want logged.

---

## Step 5 — Bring it up

```sh
cd ~/caddy
docker compose up -d --build
docker logs -f caddy        # watch it obtain certificates
```

Give it a minute to issue certs (you'll see `certificate obtained successfully` in
the logs), then visit `https://app.example.com`.

---

## Step 6 — Applying changes later

After editing the `Caddyfile`:

- **Linux Docker host:**
  ```sh
  docker exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
  ```
  (Zero-downtime hot reload.)

- **Docker Desktop (macOS/Windows) — important gotcha:** editing the bind-mounted
  `Caddyfile` and running `caddy reload` often loads a **stale** copy (the container
  is pinned to the file's original inode). Recreate instead:
  ```sh
  docker compose up -d --force-recreate
  ```
  Your certs survive (they're in the named volume). Always validate first:
  ```sh
  docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:latest \
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
  ```

---

## Verifying it works

```sh
# Site reachable + valid cert:
curl -I https://app.example.com

# Rate limiting (repeat the login POST > your limit; later ones should return 429):
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST https://vault.example.com/identity/connect/token
done
# expect: 8 non-429s, then 429 429 429 ...

# Access log:
docker exec caddy tail -n 3 /data/access.log
```

---

## Tuning & tips

- **Rate-limit strength:** lower `events` / widen `window` for stricter limits
  (e.g. `events 5` `window 1m`). It blocks a *single* hammering IP; it won't stop a
  distributed attack — pair it with **2FA** on the app itself, which is the real fix.
- **Reverse proxy over HTTP internally is fine** — Caddy terminates TLS at the edge;
  your `reverse_proxy` targets can be plain `http://internal:port`.
- **Watchtower auto-updates:** a custom-built image (the rate-limit one) has no
  registry, so auto-updaters skip it — it won't silently revert to stock. Rebuild
  manually with `docker compose up -d --build` when you want plugin/Caddy updates.
- **Back up** the `caddy_data` volume and your `Caddyfile`.

That's the whole setup. Ping me if your friend gets stuck on cert issuance — 99% of
the time it's DNS not pointing at the box yet, or port 80/443 not forwarded.
