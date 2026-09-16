#!/usr/bin/env bash
# Start implementation on a GitHub Issue: prepare a task branch + lightweight
# tasks/ACTIVE.md pointer, then launch Claude Code to implement it.
#
# Usage:
#   ./work-issue.sh <issue-number>
#
# GitHub Issues are the canonical task specification (see CLAUDE.md).
# This script does not embed the issue body into the Claude invocation --
# Claude reads tasks/ACTIVE.md, which points at the issue, and fetches the
# issue itself via `gh`.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

usage() {
  echo "usage: $0 <issue-number>" >&2
  exit 2
}

# --- 1. require exactly one numeric issue number ---------------------------
[ "$#" -eq 1 ] || usage
ISSUE_NUMBER="$1"
[[ "$ISSUE_NUMBER" =~ ^[0-9]+$ ]] || {
  echo "ERROR: issue number must be numeric, got '${ISSUE_NUMBER}'" >&2
  exit 2
}

# --- 2. require gh auth status success --------------------------------------
command -v gh >/dev/null 2>&1 || {
  echo "ERROR: gh CLI not found on PATH" >&2
  exit 1
}
gh auth status >/dev/null 2>&1 || {
  echo "ERROR: gh is not authenticated (run: gh auth login)" >&2
  exit 1
}

# --- 3. require clean working tree ------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree is dirty; commit or stash before starting a new issue" >&2
  git status --short >&2
  exit 1
fi

# --- 6/7. fetch issue; fail clearly if closed or not found ------------------
echo "Fetching issue #${ISSUE_NUMBER}..."
if ! ISSUE_JSON="$(gh issue view "$ISSUE_NUMBER" --json number,title,url,state,labels 2>&1)"; then
  echo "ERROR: could not fetch issue #${ISSUE_NUMBER}:" >&2
  echo "$ISSUE_JSON" >&2
  exit 1
fi

ISSUE_STATE="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['state'])" "$ISSUE_JSON")"
if [ "$ISSUE_STATE" != "OPEN" ]; then
  echo "ERROR: issue #${ISSUE_NUMBER} is ${ISSUE_STATE}, not OPEN" >&2
  exit 1
fi

ISSUE_TITLE="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['title'])" "$ISSUE_JSON")"
ISSUE_URL="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['url'])" "$ISSUE_JSON")"
ISSUE_LABELS="$(python3 -c "import json,sys; print(','.join(l['name'] for l in json.loads(sys.argv[1])['labels']))" "$ISSUE_JSON")"

# --- 8. derive a concise branch name -----------------------------------------
BRANCH="$(python3 scripts/issue_workflow.py branch-name "$ISSUE_NUMBER" "$ISSUE_TITLE" "$ISSUE_LABELS")"
echo "Issue: #${ISSUE_NUMBER} — ${ISSUE_TITLE}"
echo "Branch: ${BRANCH}"

# --- 4/5. git checkout main; git pull --ff-only ------------------------------
git checkout main
git pull --ff-only

# --- 9/10/11. refuse to overwrite an unrelated branch; else create/reuse ----
if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  EXISTING_ISSUE="$(git show "${BRANCH}:tasks/ACTIVE.md" 2>/dev/null | { grep -m1 '^Issue: ' || true; } | sed 's/^Issue: #\{0,1\}//')"
  if [ "$EXISTING_ISSUE" != "$ISSUE_NUMBER" ]; then
    echo "ERROR: branch '${BRANCH}' already exists and is not clearly for issue #${ISSUE_NUMBER}" >&2
    echo "  (found tasks/ACTIVE.md Issue: ${EXISTING_ISSUE:-<none/unreadable>} on that branch)" >&2
    echo "Resolve manually before retrying, e.g.: git branch -D ${BRANCH}" >&2
    exit 1
  fi
  echo "Branch '${BRANCH}' already exists for this issue; reusing it."
  git checkout "${BRANCH}"
else
  git checkout -b "${BRANCH}"
fi

# --- 11. generate lightweight tasks/ACTIVE.md pointer -----------------------
GENERATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
python3 scripts/issue_workflow.py active-md "$ISSUE_NUMBER" "$ISSUE_URL" "$ISSUE_TITLE" "$BRANCH" "$GENERATED_AT" > tasks/ACTIVE.md

# --- 12. update operational state to show selected issue/branch -------------
python3 - "$BRANCH" "$ISSUE_NUMBER" <<'PYEOF'
import json
import sys

branch, issue = sys.argv[1], int(sys.argv[2])
path = "ai_exchange/CURRENT_STATE.json"
with open(path, encoding="utf-8") as f:
    state = json.load(f)

state.setdefault("working", {})
state["working"]["branch"] = branch
state["working"]["issue"] = issue
state["working"]["commit"] = None
state["working"]["prUrl"] = None
state["working"]["status"] = "IN_PROGRESS"

with open(path, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF

git add tasks/ACTIVE.md ai_exchange/CURRENT_STATE.json
if ! git diff --cached --quiet; then
  git commit -m "chore: start issue #${ISSUE_NUMBER} (${BRANCH})"
else
  echo "tasks/ACTIVE.md and CURRENT_STATE.json already reflect issue #${ISSUE_NUMBER}; nothing to commit."
fi

# --- 13. launch Claude Code --------------------------------------------------
PROMPT="Read CLAUDE.md and execute the active GitHub Issue referenced by tasks/ACTIVE.md. Implement only that issue, validate, run ./handoff.sh, push the branch, and open a PR with Closes #${ISSUE_NUMBER}. Do not merge."

CAN_LAUNCH_NONINTERACTIVE=0
if command -v claude >/dev/null 2>&1 && claude --help 2>/dev/null | grep -qE -- '-p, --print'; then
  CAN_LAUNCH_NONINTERACTIVE=1
fi

if [ "$CAN_LAUNCH_NONINTERACTIVE" -eq 1 ]; then
  echo ""
  echo "Launching Claude Code (non-interactive, --permission-mode auto)..."
  # `auto` mirrors this repo's normal working mode: proceed without
  # stopping for routine tool approvals, but still able to decline/stop
  # on a genuinely blocking decision. Never bypassPermissions/
  # dangerously-skip-permissions here -- this invocation touches the
  # network (git push, gh pr create).
  exec claude -p --permission-mode auto "$PROMPT"
else
  echo ""
  echo "Claude CLI not found, or this installed version does not support"
  echo "non-interactive (-p) launch. Branch and ACTIVE pointer are ready."
  echo "Run this manually:"
  echo ""
  echo "  claude -p --permission-mode auto \"$PROMPT\""
  echo ""
fi
