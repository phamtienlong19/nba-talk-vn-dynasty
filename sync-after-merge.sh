#!/usr/bin/env bash
# Normalize local/repo operational state after a human merges a PR on
# GitHub: pull main, archive the completed task pointer, reset
# tasks/ACTIVE.md, refresh ai_exchange/CURRENT_STATE.json and the
# deployment-freshness marker, then re-validate.
#
# Usage:
#   ./sync-after-merge.sh [PR-number]
#
# If PR-number is omitted, it's derived from the current branch's PR (via
# `gh pr view <branch>`) or from ai_exchange/CURRENT_STATE.json's
# working.prUrl.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

STATE_FILE="ai_exchange/CURRENT_STATE.json"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

# --- 1. require clean working tree or fail safely ---------------------------
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is dirty; commit/stash before syncing" >&2
  git status --short >&2
  exit 1
fi

command -v gh >/dev/null 2>&1 || fail "gh CLI not found on PATH"
gh auth status >/dev/null 2>&1 || fail "gh is not authenticated (run: gh auth login)"

# --- 2. determine PR from argument or current state --------------------------
PR_NUMBER="${1:-}"
if [ -z "$PR_NUMBER" ]; then
  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
  PR_NUMBER="$(gh pr view "$CURRENT_BRANCH" --json number -q .number 2>/dev/null || true)"
fi
if [ -z "$PR_NUMBER" ] && [ -f "$STATE_FILE" ]; then
  PR_URL="$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('working',{}).get('prUrl') or '')" 2>/dev/null || true)"
  PR_NUMBER="$(echo "$PR_URL" | grep -oE '[0-9]+$' || true)"
fi
[ -n "$PR_NUMBER" ] || fail "no PR number given and none could be determined; usage: $0 <PR-number>"

# --- 3. query PR state with gh ----------------------------------------------
PR_JSON="$(gh pr view "$PR_NUMBER" --json number,url,state,mergeCommit,headRefName,closingIssuesReferences,title 2>&1)" \
  || fail "could not fetch PR #${PR_NUMBER}: $PR_JSON"

PR_STATE="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['state'])" "$PR_JSON")"

# --- 4. require PR = MERGED --------------------------------------------------
[ "$PR_STATE" = "MERGED" ] || fail "PR #${PR_NUMBER} is ${PR_STATE}, not MERGED"

# --- 5. record linked Issue/PR before cleanup --------------------------------
PR_URL="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['url'])" "$PR_JSON")"
MERGE_COMMIT="$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print((d.get('mergeCommit') or {}).get('oid',''))" "$PR_JSON")"
HEAD_REF="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['headRefName'])" "$PR_JSON")"
ISSUE_NUMBER="$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
refs = d.get('closingIssuesReferences') or []
print(refs[0]['number'] if refs else '')
" "$PR_JSON")"
ISSUE_URL="$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
refs = d.get('closingIssuesReferences') or []
print(refs[0]['url'] if refs else '')
" "$PR_JSON")"
PR_TITLE="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['title'])" "$PR_JSON")"

echo "PR #${PR_NUMBER} (${PR_URL}) MERGED as ${MERGE_COMMIT:0:7}, branch ${HEAD_REF}"
[ -n "$ISSUE_NUMBER" ] && echo "Linked issue: #${ISSUE_NUMBER} (${ISSUE_URL})"

# --- 6/7. checkout main; pull --ff-only --------------------------------------
git checkout main
git pull --ff-only

# --- 8. verify merged commit is present --------------------------------------
if [ -n "$MERGE_COMMIT" ] && ! git merge-base --is-ancestor "$MERGE_COMMIT" HEAD 2>/dev/null; then
  fail "merge commit ${MERGE_COMMIT} is not an ancestor of local main after pull -- refusing to proceed"
fi

CURRENT_MAIN_SHA="$(git rev-parse HEAD)"

# --- 9. archive the completed task pointer -----------------------------------
if [ -f tasks/ACTIVE.md ] && grep -q '^Issue: #' tasks/ACTIVE.md; then
  DATE="$(date -u +"%Y-%m-%d")"
  ARCHIVE_NAME="$(python3 scripts/issue_workflow.py archive-name "${ISSUE_NUMBER:-0}" "$PR_TITLE" "$DATE")"
  ARCHIVE_PATH="tasks/archive/${ARCHIVE_NAME}"
  mkdir -p tasks/archive
  cat > "$ARCHIVE_PATH" <<EOF
# Archived Task

Issue: ${ISSUE_NUMBER:+#$ISSUE_NUMBER }${ISSUE_URL}
PR: ${PR_URL}
Merged commit: ${MERGE_COMMIT}
Completed: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
  git add "$ARCHIVE_PATH"
fi

# --- 10. reset tasks/ACTIVE.md to concise "No active task" state ------------
python3 scripts/issue_workflow.py no-active-task-md > tasks/ACTIVE.md
git add tasks/ACTIVE.md

# --- 11. refresh CURRENT_STATE.json ------------------------------------------
python3 - "$CURRENT_MAIN_SHA" "$PR_URL" <<'PYEOF'
import json
import sys
from datetime import datetime, timezone

sha, pr_url = sys.argv[1], sys.argv[2]
path = "ai_exchange/CURRENT_STATE.json"
with open(path, encoding="utf-8") as f:
    state = json.load(f)

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
state.setdefault("deployed", {})
state["deployed"]["branch"] = "main"
state["deployed"]["commit"] = sha
state["deployed"]["verifiedAt"] = now

state["working"] = {
    "branch": "main",
    "commit": sha,
    "issue": None,
    "prUrl": None,
    "status": "NONE",
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF
git add "$STATE_FILE"

# --- 12. refresh + verify deployment-freshness marker ------------------------
# Anchor to the PR's actual merge commit (MERGE_COMMIT), not the current
# main tip: this run's own upcoming sync commit will advance HEAD past
# whatever we write here, so comparing against a moving HEAD would flag
# "stale" forever (every run re-triggering another one-commit-ahead
# rewrite). MERGE_COMMIT is a fixed, already-existing content commit, so
# the comparison is stable and reruns for the same PR are a true no-op.
MARKER_TARGET="${MERGE_COMMIT:-$CURRENT_MAIN_SHA}"
if [ -f build.json ]; then
  LOCAL_MARKER_SHA="$(python3 -c "import json; print(json.load(open('build.json')).get('commit',''))" 2>/dev/null || echo "")"
else
  LOCAL_MARKER_SHA=""
fi
if [ "$LOCAL_MARKER_SHA" != "$MARKER_TARGET" ]; then
  python3 scripts/deployment_freshness.py write "$MARKER_TARGET" build.json
  git add build.json
fi

# --- 13. re-validate (before committing, so the packet reflects the sync) ---
VALIDATION="FAIL"
./validate.sh >/tmp/dynasty_sync_validate.log 2>&1 && VALIDATION="PASS"

TESTS="FAIL"
python3 -m unittest discover -s tests >/tmp/dynasty_sync_tests.log 2>&1 && TESTS="PASS"

./handoff.sh >/tmp/dynasty_sync_handoff.log 2>&1 || true
if [ -f ai_exchange/REVIEW_PACKET.md ]; then
  git add ai_exchange/REVIEW_PACKET.md
fi

if ! git diff --cached --quiet; then
  git commit -m "chore: sync state after PR #${PR_NUMBER} merge"
  git push origin main
  COMMITTED_SOMETHING=1
else
  COMMITTED_SOMETHING=0
  echo "No state drift to commit."
fi

PUBLIC_URL="$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('publicUrl',''))" 2>/dev/null || true)"
FRESHNESS="unknown"
if [ -n "$PUBLIC_URL" ]; then
  if python3 scripts/deployment_freshness.py check "$PUBLIC_URL" --local-path build.json --attempts 6 --delay 10; then
    FRESHNESS="FRESH"
  else
    FRESHNESS="STALE (Pages has not caught up yet; safe to re-run this script later)"
  fi
fi

# --- 14/15. optionally delete the local merged branch ------------------------
BRANCH_DELETED="skipped"
if [ -n "$HEAD_REF" ] && git show-ref --verify --quiet "refs/heads/${HEAD_REF}"; then
  if [ -t 0 ]; then
    read -r -p "Delete local branch '${HEAD_REF}'? [y/N] " REPLY
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
      git branch -d "$HEAD_REF" && BRANCH_DELETED="deleted"
    else
      BRANCH_DELETED="kept (declined)"
    fi
  else
    BRANCH_DELETED="kept (non-interactive; re-run interactively to delete)"
  fi
fi
if [ "${SYNC_DELETE_REMOTE_BRANCH:-0}" = "1" ]; then
  git push origin --delete "$HEAD_REF" 2>/dev/null && echo "Deleted remote branch ${HEAD_REF}."
fi

# --- 16. print concise final state -------------------------------------------
echo ""
echo "SYNC-AFTER-MERGE"
echo "PR:            #${PR_NUMBER} (${PR_STATE})"
echo "Issue:         ${ISSUE_NUMBER:-none}"
echo "Main:          ${CURRENT_MAIN_SHA:0:7}"
echo "Deployment:    ${FRESHNESS}"
echo "Validation:    ${VALIDATION}"
echo "Tests:         ${TESTS}"
echo "Local branch:  ${HEAD_REF:-none} (${BRANCH_DELETED})"
echo "Active task:   none"

[ "$VALIDATION" = "PASS" ] && [ "$TESTS" = "PASS" ]
