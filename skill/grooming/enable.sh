#!/usr/bin/env bash
# Install the harah repo-grooming launchd job. Run on the MINI.
#
# The schedule itself is owned by set-cadence.sh (which the alerts routine also
# calls to correlate cadence with open alert severity). This script just picks
# the mode and delegates, so the two can never write different plists.
#
# An already-escalated cadence is PRESERVED across re-installs — re-running this
# after an alert escalation won't quietly drop grooming back to daily.
#
# Self-locating: works from any checkout of Project-Harah (re-run after moving).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="$(cat "$HOME/.harah/grooming-cadence" 2>/dev/null || echo baseline)"

bash "$HERE/set-cadence.sh" "$MODE" "grooming enable.sh" --force

launchctl list | grep harah-grooming && echo "✓ harah grooming installed (cadence: $MODE)"
