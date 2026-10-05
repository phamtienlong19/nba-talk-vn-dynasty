#!/usr/bin/env bash
# Promote a CHANGED Yahoo ranking refresh into exactly ONE candidate PR:
# the refreshed data/yahoo/ snapshot, the mechanically-refreshed
# keeper-board Yahoo display fields, and the mechanically-rebuilt
# FA/DRAFT 60 pool, all in one commit on one branch. Never touches
# discretionary keeper selections (which players are kept/cut) -- see
# scripts/refresh_keeper_board_display.py.
#
# Usage:
#   ./promote-yahoo-refresh.sh <yahoo-refresh-result.json>
#
# On MATCH (per the result JSON's "status"): does nothing, exits 0.
#
# On CHANGED: mechanically regenerates index.html (and exports/), runs the full test
# suite + site validation as a hard gate, stages data/yahoo/ + index.html
# on a deterministic branch (automation/yahoo-refresh), and opens/updates
# exactly one PR against main. Asserts that PR actually exists at the end
# -- CHANGED with no open PR is treated as an operational failure
# (non-zero exit), never a silent/green no-op.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

RESULT_JSON="${1:?usage: promote-yahoo-refresh.sh <yahoo-refresh-result.json>}"

BRANCH="automation/yahoo-refresh"
DATA_DIR="data/yahoo"
ARTIFACT_DIR="artifacts/yahoo-refresh"

# Overridable seams for tests (mirrors sync-after-merge.sh's
# SYNC_AFTER_MERGE_*_CMD pattern) -- production default is the real suite.
TEST_CMD="${PROMOTE_YAHOO_REFRESH_TEST_CMD:-python3 -m unittest discover -s tests}"
VALIDATE_CMD="${PROMOTE_YAHOO_REFRESH_VALIDATE_CMD:-./validate.sh}"
# Commissioner reference exports: normalized snapshot -> Markdown -> XLSX
# (the XLSX is derived from the Markdown, never from Yahoo directly).
EXPORT_CMD="${PROMOTE_YAHOO_REFRESH_EXPORT_CMD:-python3 scripts/export_yahoo_top300.py local_data/yahoo/players_normalized.json exports/yahoo_top300_proj_dollar_rank.md && python3 scripts/export_yahoo_top300_xlsx.py exports/yahoo_top300_proj_dollar_rank.md exports/yahoo_top300_proj_dollar_rank.xlsx}"

STATUS="$(python3 -c "import json; print(json.load(open('$RESULT_JSON'))['status'])")"
echo "status=$STATUS"

if [ "$STATUS" != "CHANGED" ]; then
  # A MATCH in cap policy / market inputs does not guarantee the commissioner
  # exports are fresh: regenerate them and treat any diff vs. the committed
  # copy as a change that needs a PR. Only a MATCH with byte-identical
  # exports is a true no-op.
  echo "MATCH -- regenerating Yahoo Top 300 exports to confirm they are fresh..."
  bash -c "$EXPORT_CMD"
  if [ -d exports ] && [ -n "$(git status --porcelain -- exports)" ]; then
    echo "Exports changed on a MATCH refresh -- promoting as CHANGED."
    STATUS=CHANGED
  else
    echo "MATCH -- exports fresh, no PR needed."
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
      { echo ""; echo "No update required."; } >> "$GITHUB_STEP_SUMMARY"
    fi
    exit 0
  fi
fi

mkdir -p "$ARTIFACT_DIR"

echo "Mechanically refreshing keeper-board Yahoo display fields..."
python3 scripts/refresh_keeper_board_display.py \
  --index-html index.html \
  --yahoo-players local_data/yahoo/players_normalized.json \
  --output index.html \
  --stats-out "$ARTIFACT_DIR/keeper_board_stats.json"

echo "Recomputing team cap totals / floor-ceiling display against the OFFICIAL cap band..."
# OFFICIAL band (commissioner policy), never the raw formula band.
CAP_FLOOR="$(python3 -c "import json; r=json.load(open('$RESULT_JSON')); print((r.get('official') or r['current'])['floor'])")"
CAP_CEILING="$(python3 -c "import json; r=json.load(open('$RESULT_JSON')); print((r.get('official') or r['current'])['ceiling'])")"
python3 scripts/refresh_team_cap_summary.py \
  --index-html index.html \
  --floor "$CAP_FLOOR" --ceiling "$CAP_CEILING" \
  --output index.html \
  --stats-out "$ARTIFACT_DIR/cap_summary_stats.json"

echo "Rebuilding FA/DRAFT 60 pool..."
python3 scripts/build_fa_draft_pool.py

echo "Generating Yahoo Top 300 Markdown + XLSX exports..."
bash -c "$EXPORT_CMD"

echo "Running full test suite + site validation (hard gate before PR)..."
TEST_STATUS=PASS
set +e
$TEST_CMD > "$ARTIFACT_DIR/test-output.log" 2>&1
TEST_RC=$?
$VALIDATE_CMD >> "$ARTIFACT_DIR/test-output.log" 2>&1
VALIDATE_RC=$?
set -e
if [ "$TEST_RC" -ne 0 ] || [ "$VALIDATE_RC" -ne 0 ]; then
  TEST_STATUS=FAIL
fi

if [ "$TEST_STATUS" = "FAIL" ]; then
  echo "::error::Tests/validation failed after mechanical regeneration -- refusing to open a PR with unverified output."
  cat "$ARTIFACT_DIR/test-output.log"
  exit 1
fi

echo "Preparing candidate Yahoo data + PR text..."
python3 scripts/prepare_yahoo_data_pr.py \
  --result "$RESULT_JSON" \
  --current-players local_data/yahoo/players_normalized.json \
  --cap-snapshot local_data/yahoo/cap_snapshot_latest.json \
  --data-dir "$DATA_DIR" \
  --keeper-board-stats "$ARTIFACT_DIR/keeper_board_stats.json" \
  --test-status "$TEST_STATUS" \
  --pr-title-out "$ARTIFACT_DIR/pr_title.txt" \
  --pr-body-out "$ARTIFACT_DIR/pr_body.md" \
  --run-id "${GITHUB_RUN_ID:-}" \
  --run-attempt "${GITHUB_RUN_ATTEMPT:-}" \
  --repository "${GITHUB_REPOSITORY:-}" \
  --server-url "${GITHUB_SERVER_URL:-https://github.com}"

git config user.name "${GIT_AUTHOR_NAME:-github-actions[bot]}"
git config user.email "${GIT_AUTHOR_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"

git fetch origin main
# Safe no-op on the working tree: origin/main is the same commit this job
# already has checked out, so this only (re)points the branch ref, never
# discards the regeneration above.
git checkout -B "$BRANCH" origin/main

git add "$DATA_DIR" index.html
[ -d exports ] && git add exports

if git diff --cached --quiet; then
  echo "::error::Yahoo refresh reported CHANGED but regeneration produced no diff against main -- investigate before trusting CHANGED detection."
  exit 1
fi

git commit -m "data: refresh Yahoo rankings and cap"
git push --force-with-lease origin "$BRANCH"

EXISTING_PR="$(gh pr list --head "$BRANCH" --base main --state open --json number --jq '.[0].number // ""')"
if [ -n "$EXISTING_PR" ]; then
  gh pr edit "$EXISTING_PR" \
    --title "$(cat "$ARTIFACT_DIR/pr_title.txt")" \
    --body-file "$ARTIFACT_DIR/pr_body.md"
  PR_NUMBER="$EXISTING_PR"
else
  gh pr create --base main --head "$BRANCH" \
    --title "$(cat "$ARTIFACT_DIR/pr_title.txt")" \
    --body-file "$ARTIFACT_DIR/pr_body.md"
  PR_NUMBER="$(gh pr list --head "$BRANCH" --base main --state open --json number --jq '.[0].number // ""')"
fi

# Hard failure if CHANGED but no PR actually exists -- never report green
# success for CHANGED + no PR; that state is an operational failure.
if [ -z "$PR_NUMBER" ]; then
  echo "::error::CHANGED refresh completed but no open PR exists for $BRANCH -- operational failure."
  exit 1
fi

PR_URL="$(gh pr view "$PR_NUMBER" --json url --jq .url)"
echo "$PR_URL" > "$ARTIFACT_DIR/pr_url.txt"
echo "$PR_NUMBER" > "$ARTIFACT_DIR/pr_number.txt"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  { echo ""; echo "**PR:** #$PR_NUMBER $PR_URL"; } >> "$GITHUB_STEP_SUMMARY"
fi

echo "PR: #$PR_NUMBER $PR_URL"
