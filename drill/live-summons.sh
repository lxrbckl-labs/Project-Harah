#!/usr/bin/env bash
# Live summons demo (2026-08-23 ~04:10): shipped with a deliberate syntax
# error. Alex summons the REAL listener on the mini to fix it — end to end.
set -euo pipefail
announce() {
  echo "the sleeper has awakened: $1"
# deliberate: missing closing brace
announce "harah lives"
