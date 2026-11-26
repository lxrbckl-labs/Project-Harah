# sqlite-backup-sidecar: the data-durability pattern for the mini's apps

**Goal (Alex, 2026-11-23): not losing data.** Any app on the mini whose state is a SQLite database gets this shape:

1. **The live database stays where SQLite is safe**, in a Docker named volume (preferred: SQLite locking and WAL
   files are unreliable on Docker Desktop bind mounts to the external drives, and a file-sharing stall can corrupt the
   one copy that matters; Core's Postgres hit exactly that on 2026-11-22) or, for older stacks, wherever it already is.
   Nothing here moves the live data.
2. **A sidecar container in the same compose project** snapshots it every 5 minutes with SQLite's online backup API
   (never a file copy of a database in use), runs `PRAGMA integrity_check`, checksums the file, writes it to ONE
   external drive, then copies it to a SECOND place with the checksum verified, and keeps a retention ladder
   (everything for 2 h, hourly for 48 h, daily for 30 d, weekly for 26 w, monthly for 24 m; the newest 3 always).
3. **Why a container and not launchd**: on macOS a launchd job cannot read or write the external drives without a
   privacy grant (TCC), and the host-side jobs failed silently for a week because of it. Containers reach the drives
   through Docker's own file sharing, no grant needed, and restart with the stack.
4. **A heartbeat the healthcheck reads** (`status/sidecar.json`), so a dead backup shows as an unhealthy container in
   `docker ps` and on ServerManager instead of a quiet gap.

## This image

`Dockerfile` + `backup-loop.sh`: alpine with sqlite3, GNU tar and coreutils. Built locally, never pushed:

    cd ~/lxrbckl-dev/Project-Harah/skill/backup/sqlite-sidecar && docker build -t sqlite-backup-sidecar:local .

Environment: `SQLITE_DB` (path inside the container), `NAME` (file prefix), `PRIMARY` (default /backup1),
`SECOND` (default /backup2, skipped when not mounted), `EXTRA_PATHS` (space-separated paths tarred beside each
snapshot: keys, config, attachments; missing ones are skipped), `INTERVAL` (seconds, default 300), `RETAIN_*`.

Mounts: the app's data at `/live` (read-write: SQLite needs the `-shm` file even to read a WAL database; the script
only reads), the first destination at `/backup1` on a DIFFERENT drive from the live data, the second at `/backup2`.

Layout under each destination: `db/<NAME>-<UTCstamp>.sqlite3` with a `.json` manifest (bytes, sha256, integrity),
`files/<NAME>-<stamp>.tar.gz` with `.sha256`, `status/last-snapshot.json`, `status/sidecar.json`.

Compose service template (vaultwarden's, `~/docker-bare-run/vaultwarden/docker-compose.yml`):

    vw-backup:
      image: sqlite-backup-sidecar:local
      pull_policy: never
      restart: unless-stopped
      init: true
      network_mode: none
      read_only: true
      tmpfs: ["/tmp:rw,noexec,nosuid,nodev,size=256m,mode=1777"]
      cap_drop: [ALL]
      security_opt: ["no-new-privileges:true"]
      mem_limit: 128m
      pids_limit: 64
      environment: { SQLITE_DB: /live/db.sqlite3, NAME: vaultwarden, INTERVAL: "300",
                     EXTRA_PATHS: "/live/rsa_key.pem /live/attachments /live/sends /live/config.json" }
      volumes:
        - "/Volumes/NVME2/vw-data:/live"
        - "/Volumes/NVME1/vaultwarden-backups:/backup1"
        - "/Users/alexarbuckle/backups/vaultwarden:/backup2"
      healthcheck: (see the file; it checks status/sidecar.json is ok and under 11 minutes old)

Start only the new service so the app is not recreated: `docker compose up -d --no-deps <service>`.

## Restore

Stop the app, copy the chosen `db/<NAME>-<stamp>.sqlite3` over the live database (remove stale `-wal`/`-shm` files
beside it first), restore `files/` extras if needed, start the app. Verify the snapshot before use:
`sqlite3 <file> "PRAGMA integrity_check;"` and compare `sha256sum <file>` with the manifest.

## Deployed with it

| app | live data | first copy | second copy | since |
|---|---|---|---|---|
| Vaultwarden | /Volumes/NVME2/vw-data (bind) | /Volumes/NVME1/vaultwarden-backups | ~/backups/vaultwarden | 2026-11-23 |
| NotesHannah | Docker volume `notes-db` | /Volumes/NVME1/notes/backups/db | /Volumes/NVME2/notes-backups/db | 2026-11-23, its own sidecar (`backup` service, `deploy/tools/backup-loop.mjs`, reuses the app's `db-snapshot.mjs`) |

Not covered by this pattern: a fire or theft that takes the mini and both drives (needs an off-site copy; NotesHannah's
`RESTIC_REMOTE_REPOSITORY` is the hook), and Postgres-backed apps (Immich keeps its own nightly `pg_dump` under
`/Volumes/NVME1/immich/backups`; Core's Postgres has `com.hivedeck.core-backup`).
