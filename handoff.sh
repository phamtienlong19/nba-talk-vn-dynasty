#!/usr/bin/env bash
# Root wrapper. See scripts/handoff.sh.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec scripts/handoff.sh "$@"
