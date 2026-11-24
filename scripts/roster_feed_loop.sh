#!/usr/bin/env bash
# Keep the roster feed fresh: read Yahoo's 16 team pages, publish rosters.json to the roster-data branch, wait, repeat.
# Used by .github/workflows/update-roster-feed.yml (same shape as scripts/live_feed_loop.sh: GitHub's cron is best-effort, so the workflow queues its
# own successor and the loop supplies the cadence).   usage: roster_feed_loop.sh <total_seconds> <interval_seconds>
# A failed build keeps the previous feed (nothing is published) and retries at double the interval; five failures in a row stop the run.
set -u
total="${1:-6900}"; every="${2:-300}"
end=$(( $(date +%s) + total )); fails=0
curl -sf --max-time 20 "https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/roster-data/rosters.json" -o rosters.json || rm -f rosters.json
while [ "$(date +%s)" -lt "$end" ]; do
  start=$(date +%s)
  if python3 scripts/build_roster_feed.py --out rosters.json --previous rosters.json; then
    fails=0
    out="$(mktemp -d)"; cp rosters.json "$out/rosters.json"
    ( cd "$out" && git init -q -b roster-data && git config user.name "github-actions[bot]" \
      && git config user.email "41898282+github-actions[bot]@users.noreply.github.com" && git add rosters.json \
      && git commit -q -m "roster feed $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      && git push -q --force "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" roster-data ) || echo "publish failed"
    wait_for="$every"
  else
    fails=$((fails + 1)); echo "build failed ($fails in a row)"
    [ "$fails" -ge 5 ] && exit 1
    wait_for=$(( every * 2 ))
  fi
  rest=$(( wait_for - ($(date +%s) - start) ))
  [ "$rest" -gt 0 ] || continue
  [ $(( $(date +%s) + rest )) -lt "$end" ] || break
  sleep "$rest"
done
