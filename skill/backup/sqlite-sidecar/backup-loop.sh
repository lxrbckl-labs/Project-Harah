#!/bin/sh
# Generic SQLite backup sidecar. Reads the live database, writes verified snapshots elsewhere, never changes the source.
#   SQLITE_DB      path of the live database inside this container (mount the app's data dir at /live)   required
#   NAME           prefix for snapshot files (e.g. vaultwarden)                                           required
#   PRIMARY        first destination (mount a different drive here), default /backup1
#   SECOND         second destination (another drive or the internal disk), default /backup2; skipped if absent
#   EXTRA_PATHS    space-separated paths tarred alongside each snapshot (keys, config, attachments); optional
#   INTERVAL       seconds between runs, default 300
#   RETAIN_ALL_HOURS=2 RETAIN_HOURLY_HOURS=48 RETAIN_DAILY_DAYS=30 RETAIN_WEEKLY_WEEKS=26 RETAIN_MONTHLY_MONTHS=24
# Layout under each destination: db/<NAME>-<UTC stamp>.sqlite3 (+ .json manifest), files/<NAME>-<stamp>.tar.gz
# (+ .sha256), status/sidecar.json (heartbeat for the healthcheck), status/last-snapshot.json.
set -u
DB="${SQLITE_DB:?SQLITE_DB is required}"; NAME="${NAME:?NAME is required}"
P="${PRIMARY:-/backup1}"; S2="${SECOND:-/backup2}"; INTERVAL="${INTERVAL:-300}"; EXTRA="${EXTRA_PATHS:-}"
ALL_H="${RETAIN_ALL_HOURS:-2}"; HOURLY_H="${RETAIN_HOURLY_HOURS:-48}"; DAILY_D="${RETAIN_DAILY_DAYS:-30}"
WEEKLY_W="${RETAIN_WEEKLY_WEEKS:-26}"; MONTHLY_M="${RETAIN_MONTHLY_MONTHS:-24}"
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "$(ts) $*"; }
warn() { echo "$(ts) WARN $*" >&2; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
status() { # file json
  mkdir -p "$P/status" && printf '%s\n' "$2" > "$P/status/$1.json.tmp" && mv "$P/status/$1.json.tmp" "$P/status/$1.json"
}
# Retention ladder, the same rules as Project-NotesHannah scripts/lib/ladder.sh: keep everything younger than ALL_H
# hours, the newest per hour for HOURLY_H hours, per day for DAILY_D days, per ISO week for WEEKLY_W weeks, per month
# for MONTHLY_M months, and always the newest 3. Prints victims (base names, without extension) in <dir> for <ext>.
victims() { # dir ext
  ls -1 "$1" 2>/dev/null | grep -E "^${NAME}-[0-9]{8}T[0-9]{6}Z\\.$2\$" | sort -r | sed "s/\\.$2\$//" | awk -v now="$(date -u +%s)" \
    -v all_h="$ALL_H" -v hourly_h="$HOURLY_H" -v daily_d="$DAILY_D" -v weekly_w="$WEEKLY_W" -v monthly_m="$MONTHLY_M" -v plen="$(( ${#NAME} + 1 ))" '
    function days_from(y, m, d,   era, yoe, doy, doe) { if (m <= 2) y--; era = int(y / 400); yoe = y - era * 400
      doy = int((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1; doe = yoe * 365 + int(yoe / 4) - int(yoe / 100) + doy
      return era * 146097 + doe - 719468 }
    BEGIN { cd = int(now / 86400); z = cd + 719468; era = int(z / 146097); doe = z - era * 146097
      yoe = int((doe - int(doe / 1460) + int(doe / 36524) - int(doe / 146096)) / 365); y = yoe + era * 400
      doy = doe - (365 * yoe + int(yoe / 4) - int(yoe / 100)); mp = int((5 * doy + 2) / 153); m = mp + (mp < 10 ? 3 : -9)
      if (m <= 2) y++; cur_month = y * 12 + m }
    { name = $0; st = substr(name, plen + 1)
      y = substr(st, 1, 4) + 0; m = substr(st, 5, 2) + 0; d = substr(st, 7, 2) + 0; H = substr(st, 10, 2) + 0; M = substr(st, 12, 2) + 0; S = substr(st, 14, 2) + 0
      days = days_from(y, m, d); e = days * 86400 + H * 3600 + M * 60 + S; age = now - e; n++; keep = 0
      if (n <= 3) keep = 1; if (age < all_h * 3600) keep = 1
      hb = int(e / 3600); wb = int((days + 3) / 7); mb = y * 12 + m
      if (age < hourly_h * 3600 && !(hb in hseen)) { hseen[hb] = 1; keep = 1 }
      if (age < daily_d * 86400 && !(days in dseen)) { dseen[days] = 1; keep = 1 }
      if (age < weekly_w * 7 * 86400 && !(wb in wseen)) { wseen[wb] = 1; keep = 1 }
      if (cur_month - mb < monthly_m && !(mb in mseen)) { mseen[mb] = 1; keep = 1 }
      if (!keep) print name }'
}
prune() { # dir ext
  [ -d "$1" ] || return 0
  for v in $(victims "$1" "$2"); do rm -f "$1/$v.$2" "$1/$v.$2.json" "$1/$v.$2.sha256"; done
  find "$1" -maxdepth 1 -name '.tmp-*' -mmin +60 -exec rm -f {} + 2>/dev/null
}
copy_verified() { # src dst-dir expected-sha  -> 0 ok
  mkdir -p "$2" || return 1; b="$(basename "$1")"
  cp "$1" "$2/.tmp-$b" && [ "$(sha "$2/.tmp-$b")" = "$3" ] && mv "$2/.tmp-$b" "$2/$b" || { rm -f "$2/.tmp-$b"; return 1; }
}
once() {
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"; snap="$NAME-$stamp.sqlite3"; mkdir -p "$P/db" "$P/status" || return 1
  tmp="/tmp/$snap"; rm -f "$tmp"
  sqlite3 "$DB" ".timeout 10000" ".backup '$tmp'" || { rm -f "$tmp"; echo "online backup failed"; return 1; }
  sqlite3 "$tmp" "PRAGMA journal_mode=DELETE;" >/dev/null 2>&1
  ic="$(sqlite3 "$tmp" "PRAGMA integrity_check;" 2>&1)"; [ "$ic" = "ok" ] || { rm -f "$tmp"; echo "integrity_check: $ic"; return 1; }
  d="$(sha "$tmp")"; bytes="$(wc -c < "$tmp" | tr -d ' ')"
  mv "$tmp" "$P/db/.tmp-$snap" && [ "$(sha "$P/db/.tmp-$snap")" = "$d" ] && mv "$P/db/.tmp-$snap" "$P/db/$snap" || { rm -f "$P/db/.tmp-$snap"; echo "snapshot did not land on $P intact"; return 1; }
  printf '{"createdAt":"%s","name":"%s","file":"%s","bytes":%s,"sha256":"%s","integrityCheck":"ok","source":"%s"}\n' "$(ts)" "$NAME" "$snap" "$bytes" "$d" "$DB" > "$P/db/$snap.json"
  files=""; fsha=""
  if [ -n "$EXTRA" ]; then
    have=""; for x in $EXTRA; do [ -e "$x" ] && have="$have $x"; done
    if [ -n "$have" ]; then mkdir -p "$P/files"; tgz="$NAME-$stamp.tar.gz"
      # shellcheck disable=SC2086
      if tar czf "/tmp/$tgz" $have 2>/dev/null; then fsha="$(sha "/tmp/$tgz")"; mv "/tmp/$tgz" "$P/files/$tgz" && echo "$fsha  $tgz" > "$P/files/$tgz.sha256" && files="$tgz"; else rm -f "/tmp/$tgz"; warn "extra files tar failed"; fi
    fi
  fi
  second="not configured"
  if [ -d "$S2" ]; then
    if copy_verified "$P/db/$snap" "$S2/db" "$d" && cp "$P/db/$snap.json" "$S2/db/$snap.json"; then second=ok; else second="FAILED"; fi
    if [ -n "$files" ] && [ "$second" = ok ]; then copy_verified "$P/files/$files" "$S2/files" "$fsha" && cp "$P/files/$files.sha256" "$S2/files/" || second="FAILED (files)"; fi
  fi
  prune "$P/db" sqlite3; prune "$P/files" tar.gz
  [ "$second" = ok ] && { prune "$S2/db" sqlite3; prune "$S2/files" tar.gz; }
  status last-snapshot "{\"at\":\"$(ts)\",\"name\":\"$NAME\",\"file\":\"$snap\",\"bytes\":$bytes,\"sha256\":\"$d\",\"files\":\"$files\",\"secondCopy\":\"$second\"}"
  echo "snapshot $snap ($bytes bytes, integrity ok)${files:+ + $files} second copy: $second"
  case "$second" in FAILED*) return 2;; esac; return 0
}
log "sqlite sidecar for $NAME: $DB every ${INTERVAL}s -> $P (second: $S2); extras: ${EXTRA:-none}"
trap 'log "stopping"; exit 0' TERM INT
fails=0
while :; do
  out="$(once 2>&1)"; rc=$?
  if [ $rc -eq 0 ]; then fails=0; log "$out"; status sidecar "{\"at\":\"$(ts)\",\"ok\":true,\"failures\":0,\"name\":\"$NAME\"}"
  elif [ $rc -eq 2 ]; then fails=$((fails+1)); warn "$out"; status sidecar "{\"at\":\"$(ts)\",\"ok\":false,\"failures\":$fails,\"error\":\"second copy failed\"}"
  else fails=$((fails+1)); warn "snapshot failed ($fails in a row): $out"; status sidecar "{\"at\":\"$(ts)\",\"ok\":false,\"failures\":$fails,\"error\":\"snapshot failed\"}"; fi
  sleep "$INTERVAL" & wait $!
done
