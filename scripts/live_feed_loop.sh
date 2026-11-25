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
# Lock evidence (scripts/lineup_log.py): append what each lineup looked like when each game locked to the APPEND-ONLY lineup-log branch (one file per
# day, ordinary commits, never force-pushed, never rewritten). A failure here never stops the feed.
log_dir="lineup-log-work"; log_remote="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
lineup_log() {
  if [ ! -d "$log_dir/.git" ]; then
    rm -rf "$log_dir"
    git clone -q --depth 1 --branch lineup-log "$log_remote" "$log_dir" 2>/dev/null || {
      mkdir -p "$log_dir" && ( cd "$log_dir" && git init -q -b lineup-log && git remote add origin "$log_remote" ); }
    ( cd "$log_dir" && git config user.name "github-actions[bot]" && git config user.email "41898282+github-actions[bot]@users.noreply.github.com" )
  fi
  python3 scripts/lineup_log.py --feed live.json --previous prev.json --log-dir "$log_dir" || { echo "lineup log failed"; return 0; }
  ( cd "$log_dir" && [ -n "$(git status --porcelain)" ] && git add -A && git commit -q -m "lineup log $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    && { git push -q origin lineup-log 2>/dev/null || { git pull -q --rebase origin lineup-log && git push -q origin lineup-log; }; } ) || true
}
# the last published feed carries the closed days' lineup evidence, so a new run does not capture those days again
curl -sf --max-time 20 "https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/live-data/live.json" -o live.json || rm -f live.json
# who actually played, for the lineup review (an injured-list player who played is cleared); optional
curl -sf --max-time 20 "https://raw.githubusercontent.com/${GITHUB_REPOSITORY}/stats-data/player_log.json" -o player-log.json || rm -f player-log.json
while [ "$(date +%s)" -lt "$end" ]; do
  start=$(date +%s)
  cp live.json prev.json 2>/dev/null || true      # the read before this one: each player's status from before the tip
  if python3 scripts/build_live_feed.py --out live.json --schedule-cache schedule-cache.json --day-cache day-cache.json --previous live.json; then
    fails=0
    lineup_log                                                          # before publishing: the review below goes out with the feed
    python3 scripts/lineup_review.py --log-dir "$log_dir" --feed live.json --player-log player-log.json || echo "lineup review failed"
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
