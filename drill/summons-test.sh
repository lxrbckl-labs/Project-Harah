#!/usr/bin/env bash
# Summons drill target (2026-08-23): this script ships with a deliberate
# syntax error. The drill: @harah is summoned to fix it on this branch.
set -euo pipefail
greet() {
  echo "harah summons drill: $1"
# deliberate: missing closing brace for greet()
greet "hello"
