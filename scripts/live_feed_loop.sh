#!/usr/bin/env bash
# Keep the live feed fresh for a while: build it, publish it to the live-data branch, wait, repeat.
# Used by .github/workflows/update-live-data.yml. GitHub's cron is best-effort and in practice starts runs tens of minutes late, so
# the workflow starts this loop on a schedule and the loop supplies the cadence itself.
#   usage: live_feed_loop.sh <total_seconds> <game_hours_interval_seconds>
# Outside game hours (NBA games land about 22:00-07:00 UTC, weekend afternoons from 16:00 UTC) it only refreshes every 15 minutes.
# A failed build keeps the previous feed (nothing is published) and retries at double the interval; five failures in a row stop the run.
set -u
total="${1:-6900}"; game_every="${2:-240}"
pick() {  # seconds between builds now
  h=$((10#$(date -u +%H))); d=$(date -u +%u)
  if [ "$h" -ge 22 ] || [ "$h" -le 7 ] || { [ "$h" -ge 16 ] && [ "$d" -ge 6 ]; }; then echo "$game_every"; else echo 900; fi
}
end=$(( $(date +%s) + total )); fails=0
while [ "$(date +%s)" -lt "$end" ]; do
  start=$(date +%s)
  if python3 scripts/build_live_feed.py --out live.json --schedule-cache schedule-cache.json; then
    fails=0
    out="$(mktemp -d)"; cp live.json "$out/live.json"
    ( cd "$out" && git init -q -b live-data && git config user.name "github-actions[bot]" \
      && git config user.email "41898282+github-actions[bot]@users.noreply.github.com" && git add live.json \
      && git commit -q -m "live feed $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      && git push -q --force "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" live-data ) || echo "publish failed"
    wait_for="$(pick)"
  else
    fails=$((fails + 1)); echo "build failed ($fails in a row)"
    [ "$fails" -ge 5 ] && exit 1
    wait_for=$(( $(pick) * 2 ))
  fi
  rest=$(( wait_for - ($(date +%s) - start) ))
  [ "$rest" -gt 0 ] || continue
  [ $(( $(date +%s) + rest )) -lt "$end" ] || break      # the next build would fall past the end: stop, the next run takes over
  sleep "$rest"
done
