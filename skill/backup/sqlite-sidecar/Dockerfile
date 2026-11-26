# sqlite-backup-sidecar: a tiny container that snapshots a live SQLite database (online backup API) onto one drive,
# copies the snapshot to a second place with checksums, keeps a retention ladder, and reports a heartbeat.
# Built locally on the mini: docker build -t sqlite-backup-sidecar:local .   (README.md)
FROM alpine:3.20
RUN apk add --no-cache sqlite tar coreutils
COPY backup-loop.sh /usr/local/bin/backup-loop.sh
RUN chmod +x /usr/local/bin/backup-loop.sh
COPY healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh
HEALTHCHECK --interval=60s --timeout=5s --retries=3 --start-period=60s CMD ["/usr/local/bin/healthcheck.sh"]
ENTRYPOINT ["/usr/local/bin/backup-loop.sh"]
