# Shared by the data workflows that open a pull request (rosters, standings, player metadata). Source it; it defines two functions.
#
#   bot_pr_token   -> picks the token to open the PR with. The owner's fine-grained token (secret ROSTER_PR_TOKEN) when it is set and valid:
#                     GitHub treats the author as a person, so the repository's checks run with no "Approve and run workflows" click.
#                     Otherwise the built-in token (works, but GitHub holds the PR's checks for approval). Sets BOT_PR_CHECKS=yes|no.
#   bot_pr_merge N -> wait for PR N's checks to start and ALL pass (up to 30 min), then squash-merge. No auto-merge flag (it merges instantly
#                     when nothing requires a check). Never called for a PR the workflow did not itself prove safe (READY outcome, path guard, tests).
#                     Without the owner's token the checks are held for approval, so nothing is merged and the PR waits for a human.
bot_pr_token() {
  if [ -n "${ROSTER_PR_TOKEN:-}" ] && GH_TOKEN="$ROSTER_PR_TOKEN" gh api user --silent 2>/dev/null; then
    export GH_TOKEN="$ROSTER_PR_TOKEN"; BOT_PR_OPENER="your token"; BOT_PR_CHECKS=yes
  else
    export GH_TOKEN="${DEFAULT_TOKEN:?}"; BOT_PR_OPENER="the built-in token"; BOT_PR_CHECKS=no
    echo "::warning title=PR opened by the bot::ROSTER_PR_TOKEN is not set or no longer valid, so GitHub holds the PR's checks for a maintainer approval and the PR is not merged automatically. See docs/BOT_PRS.md."
  fi
}

bot_pr_merge() {
  local pr="$1" n=0 i
  if [ "$BOT_PR_CHECKS" != "yes" ]; then
    echo "Not merging #$pr: its checks need a maintainer approval (no ROSTER_PR_TOKEN)." >> "$GITHUB_STEP_SUMMARY"; return 0
  fi
  # No auto-merge flag here: when nothing in the repository requires a check, gh merges at once, before the PR's checks have even started
  # (it merged #231 four seconds after opening it). Wait for the checks to exist, then for them all to pass, then squash-merge.
  for i in $(seq 1 12); do
    n=$(gh pr checks "$pr" --json name --jq length 2>/dev/null || echo 0)
    [ "${n:-0}" -gt 0 ] && break
    sleep 15
  done
  if [ "${n:-0}" -eq 0 ]; then
    echo "::warning title=Not merged::#$pr has no checks to wait for after 3 minutes; left open."
    echo "#$pr left open for a human (its checks never started)" >> "$GITHUB_STEP_SUMMARY"; return 0
  fi
  if timeout 1800 gh pr checks "$pr" --watch --interval 20 >/dev/null 2>&1; then
    if gh pr merge "$pr" --squash --delete-branch; then
      echo "Merged #$pr after its checks passed" >> "$GITHUB_STEP_SUMMARY"
      # a PR merged by a bot does not start the deploy's push trigger: ask for it now (the 30-minute clock is only the backstop)
      GH_TOKEN="${DEFAULT_TOKEN:-}" gh workflow run pages.yml --ref main >/dev/null 2>&1 || true
      return 0
    fi
  fi
  echo "::warning title=Not merged::#$pr stays open: its checks did not all pass in 30 minutes, or the merge was refused."
  echo "#$pr left open for a human (checks not green, or merge refused)" >> "$GITHUB_STEP_SUMMARY"
}
