#!/usr/bin/env bash
# Install the harah resolver launchd job. Run on the MINI.
#
# The schedule is owned by set-cadence.sh (which the dashboard's Resolver panel
# also drives), so the two can never write different plists. An existing
# cadence is PRESERVED across re-installs.
#
# Runs in the GUI domain deliberately — headless `claude -p` needs the login
# Keychain for its OAuth subscription token; a system-domain daemon cannot
# reach it and the agent dies silently.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="$(cat "$HOME/.harah/resolver-cadence" 2>/dev/null || echo daily)"

bash "$HERE/set-cadence.sh" "$MODE" "resolver enable.sh" --force

launchctl list | grep harah-resolver && echo "✓ harah resolver installed (cadence: $MODE)"
