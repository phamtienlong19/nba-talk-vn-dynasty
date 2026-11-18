#!/usr/bin/env bash
# For every open same-repo PR that GitHub reports as CONFLICTING: merge main into its branch; if the only conflict is the generated data blocks of
# index.html, take main's line, re-run the embeds, validate, push the merge to the PR branch and start the validation run. Anything else is left alone.
# Never pushes to main. Used by .github/workflows/heal-generated-conflicts.yml.  Needs: gh (GH_TOKEN), python3, git.
set -u
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
sleep "${HEAL_WAIT:-30}"                      # GitHub computes mergeability lazily after a push to main
git fetch -q origin main
prs=$(gh pr list --state open --json number,headRefName,isCrossRepository,mergeable --jq '.[] | select(.mergeable=="CONFLICTING" and .isCrossRepository==false) | "\(.number)\t\(.headRefName)"')
[ -n "$prs" ] || { echo "no conflicting PRs"; exit 0; }
while IFS=$'\t' read -r n b; do
  echo "== PR #$n ($b)"
  git fetch -q origin "$b" || continue
  git checkout -q -f -B heal "origin/$b" || continue
  if git merge --no-edit origin/main >/tmp/merge.out 2>&1; then echo "merges cleanly here; nothing to heal"; continue; fi
  other=$(git diff --name-only --diff-filter=U | grep -v '^index.html$' || true)
  if [ -n "$other" ]; then echo "real conflict in: $other (left for a human)"; git merge --abort; continue; fi
  if ! python3 scripts/resolve_generated_conflicts.py index.html; then echo "index.html conflict is not only generated blocks (left for a human)"; git merge --abort; continue; fi
  if ! { python3 scripts/build_league_state.py sync-ledger && python3 scripts/build_league_state.py embed && python3 scripts/what_if.py embed && python3 scripts/live_page.py embed; } >/dev/null; then
    echo "re-embedding failed (left for a human)"; git merge --abort 2>/dev/null; git reset -q --hard; continue; fi
  if ! ./validate.sh >/tmp/validate.out 2>&1; then echo "validation failed after healing (left for a human)"; tail -5 /tmp/validate.out; git reset -q --hard; continue; fi
  git add -A
  git commit -q -m "Merge main into $b (generated data blocks in index.html re-embedded automatically)"
  if git push -q origin "heal:$b"; then
    gh workflow run validate.yml --ref "$b" >/dev/null 2>&1 || true        # pushes made with the built-in token do not start the PR checks themselves
    gh pr comment "$n" --body "Main moved and this PR's generated blocks in \`index.html\` conflicted. They were re-embedded from the data and the merge was pushed (Heal Generated Conflicts workflow). Validation was run before the push; the full checks were started on this branch." >/dev/null 2>&1 || true
    echo "healed #$n"
  else
    echo "push refused (for example main changed a workflow file): left for a human"; git reset -q --hard
  fi
done <<< "$prs"
