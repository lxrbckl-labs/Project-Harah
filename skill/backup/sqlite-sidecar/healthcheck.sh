#!/bin/sh
# Healthy when the sidecar's last run succeeded and its heartbeat is younger than MAX_AGE seconds (default 660).
f="${PRIMARY:-/backup1}/status/sidecar.json"; max="${MAX_AGE:-660}"
[ -f "$f" ] || exit 1
grep -q '"ok":true' "$f" || exit 1
at="$(sed -E 's/.*"at":"([^"]+)".*/\1/' "$f")"
now="$(date -u +%s)"; then="$(date -u -d "$at" +%s 2>/dev/null)" || exit 1
[ $((now - then)) -lt "$max" ]
