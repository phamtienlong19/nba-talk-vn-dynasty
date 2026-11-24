# Shared by the data workflows that open a pull request (rosters, standings, player metadata). Source it; it defines two functions.
#
#   bot_pr_token   -> picks the token to open the PR with. The owner's fine-grained token (secret ROSTER_PR_TOKEN) when it is set and valid:
#                     GitHub treats the author as a person, so the repository's checks run with no "Approve and run workflows" click.
#                     Otherwise the built-in token (works, but GitHub holds the PR's checks for approval). Sets BOT_PR_CHECKS=yes|no.
#   bot_pr_merge N -> merge PR N once its checks are green: GitHub auto-merge if the repository can queue it, else wait for the checks (up to
#                     30 min) and squash-merge. Never called for a PR the workflow did not itself prove safe (READY outcome, path guard, tests).
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
  local pr="$1"
  if [ "$BOT_PR_CHECKS" != "yes" ]; then
    echo "Not merging #$pr: its checks need a maintainer approval (no ROSTER_PR_TOKEN)." >> "$GITHUB_STEP_SUMMARY"; return 0
  fi
  if gh pr merge "$pr" --auto --squash --delete-branch 2>/dev/null; then
    echo "Auto-merge queued for #$pr" >> "$GITHUB_STEP_SUMMARY"; return 0
  fi
  # Nothing in the repository requires a check, so GitHub refuses to queue: wait for the PR's own checks, then merge.
  sleep 45
  if timeout 1800 gh pr checks "$pr" --watch --interval 30 >/dev/null 2>&1; then
    if gh pr merge "$pr" --squash --delete-branch; then
      echo "Merged #$pr after its checks passed" >> "$GITHUB_STEP_SUMMARY"; return 0
    fi
  fi
  echo "::warning title=Not merged::#$pr stays open: its checks did not pass in time or the merge was refused."
  echo "#$pr left open for a human (checks not green in 30 min, or merge refused)" >> "$GITHUB_STEP_SUMMARY"
}
