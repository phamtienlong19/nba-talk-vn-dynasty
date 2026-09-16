#!/usr/bin/env bash
# Regenerate ai_exchange/REVIEW_PACKET.md from current repo state.
#
# Usage: ./handoff.sh   (root wrapper) or scripts/handoff.sh directly.
#
# Read-only with respect to canonical league state: never modifies
# data/, index.html, or docs/. Only writes ai_exchange/REVIEW_PACKET.md.
# Does not commit. Degrades gracefully if `gh` is unavailable or no PR
# exists yet.
#
# Optional: if ai_exchange/REVIEW_NOTES.md exists with "## Issues" and/or
# "## Decisions Required" sections, their content is spliced into the
# packet verbatim (this script still owns REVIEW_PACKET.md itself --
# REVIEW_NOTES.md is just a place to leave real findings for it to pick
# up, per CLAUDE.md's "regenerated, not hand-authored" rule).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

OUT="ai_exchange/REVIEW_PACKET.md"
BASE_BRANCH="main"

# --- task ---------------------------------------------------------------
TASK_TITLE="No active task"
TASK_FILE="tasks/ACTIVE.md"
if [ -f "$TASK_FILE" ]; then
  ISSUE_LINE="$(grep -m1 '^Issue: ' "$TASK_FILE" 2>/dev/null | sed 's/^Issue: //')"
  TITLE_LINE="$(grep -m1 '^Title: ' "$TASK_FILE" 2>/dev/null | sed 's/^Title: //')"
  if [ -n "$TITLE_LINE" ]; then
    if [[ "$ISSUE_LINE" =~ ^#?[0-9]+$ ]]; then
      TASK_TITLE="Issue ${ISSUE_LINE#\#}: ${TITLE_LINE}"
    else
      TASK_TITLE="${TITLE_LINE}"
    fi
  else
    HEADING="$(grep -m1 '^# ' "$TASK_FILE" | sed 's/^# //')"
    [ -n "$HEADING" ] && TASK_TITLE="$HEADING"
  fi
fi

# --- git ------------------------------------------------------------------
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
DIRTY="$(git status --porcelain 2>/dev/null)"
WORKING_TREE="$([ -z "$DIRTY" ] && echo clean || echo dirty)"
REPO_URL="$(git remote get-url origin 2>/dev/null || echo none)"
REPO_URL="${REPO_URL%.git}"
# Strip any embedded credentials (e.g. CI's x-access-token:<token>@) --
# this packet gets committed, so it must never carry a live secret.
REPO_URL="$(echo "$REPO_URL" | sed -E 's#(://)[^/@]*@#\1#')"

DIFF_STAT="(no diff against ${BASE_BRANCH})"
CHANGED_FILES="(none)"
if git rev-parse --verify "$BASE_BRANCH" >/dev/null 2>&1 && [ "$BRANCH" != "$BASE_BRANCH" ]; then
  DIFF_STAT="$(git --no-pager diff --stat "${BASE_BRANCH}...HEAD" 2>/dev/null || echo "(diff unavailable)")"
  CHANGED_FILES="$(git diff --name-only "${BASE_BRANCH}...HEAD" 2>/dev/null | sed 's/^/- /')"
  [ -z "$CHANGED_FILES" ] && CHANGED_FILES="(none)"
fi

# --- GitHub (optional) ------------------------------------------------------
GH_AVAILABLE=0
PR_LINE="none"
CI_LINE="unknown"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  GH_AVAILABLE=1
  PR_JSON="$(gh pr view "$BRANCH" --json url,state,title 2>/dev/null || true)"
  if [ -n "$PR_JSON" ]; then
    PR_LINE="$(python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['url']} ({d['state']})\")" <<<"$PR_JSON" 2>/dev/null || echo none)"
  fi
  CI_JSON="$(gh run list --branch "$BRANCH" --limit 1 --json status,conclusion,name 2>/dev/null || true)"
  if [ -n "$CI_JSON" ] && [ "$CI_JSON" != "[]" ]; then
    CI_LINE="$(python3 -c "
import json,sys
d=json.load(sys.stdin)
if d:
    r=d[0]
    print(f\"{r['name']}: {r['status']}/{r['conclusion']}\")
else:
    print('no runs found')
" <<<"$CI_JSON" 2>/dev/null || echo "unknown")"
  else
    CI_LINE="no runs found for this branch"
  fi
fi
GH_LINE="$([ "$GH_AVAILABLE" -eq 1 ] && echo available || echo unavailable)"

# --- deployment -------------------------------------------------------------
PUBLIC_URL="unknown"
if [ -f ai_exchange/CURRENT_STATE.json ]; then
  PUBLIC_URL="$(python3 -c "import json; print(json.load(open('ai_exchange/CURRENT_STATE.json')).get('publicUrl','unknown'))" 2>/dev/null || echo unknown)"
fi
LIVE_HTTP="unknown"
if [ "$PUBLIC_URL" != "unknown" ] && [ -n "$PUBLIC_URL" ]; then
  if curl --fail --silent --max-time 10 --location "$PUBLIC_URL" >/dev/null 2>&1; then
    LIVE_HTTP="OK"
  else
    LIVE_HTTP="FAIL or not yet propagated"
  fi
fi
FINGERPRINT="unknown"
if [ "$LIVE_HTTP" = "OK" ] && [ -f build.json ]; then
  if python3 scripts/deployment_freshness.py check "$PUBLIC_URL" --local-path build.json --attempts 1 >/tmp/dynasty_fingerprint.log 2>&1; then
    FINGERPRINT="FRESH"
  else
    FINGERPRINT="STALE (live build.json does not match local -- see docs/DEPLOYMENT_FRESHNESS.md)"
  fi
elif [ ! -f build.json ]; then
  FINGERPRINT="no local build.json"
fi

# --- validation ---------------------------------------------------------
SITE_VALIDATION="FAIL"
if ./validate.sh >/tmp/dynasty_handoff_validate.log 2>&1; then
  SITE_VALIDATION="PASS"
fi

TEST_RESULT="FAIL"
TEST_SUMMARY=""
if TEST_OUT="$(python3 -m unittest discover -s tests 2>&1)"; then
  TEST_RESULT="PASS"
else
  TEST_RESULT="FAIL"
fi
TEST_SUMMARY="$(echo "$TEST_OUT" | tail -1)"

YAHOO_REFRESH="not run this session"
LAST_YAHOO_FILE="$(ls -t local_data/yahoo/draft_analysis_*.json 2>/dev/null | head -1 || true)"
if [ -n "$LAST_YAHOO_FILE" ]; then
  YAHOO_REFRESH="last local snapshot: $(basename "$LAST_YAHOO_FILE")"
fi

# --- canonical state ------------------------------------------------------
ROSTER_LINE="unknown"
if [ -f data/2026-27/franchises.json ] && [ -f data/2026-27/prekeeper_rosters.json ]; then
  ROSTER_LINE="$(python3 -c "
import json
f = json.load(open('data/2026-27/franchises.json'))
r = json.load(open('data/2026-27/prekeeper_rosters.json'))
print(f\"{len(f['franchises'])} franchises, {len(r['assignments'])} assignments\")
" 2>/dev/null || echo "unknown")"
fi

CAP_SNAPSHOT="unknown"
YAHOO_SOURCE_TS="unknown"
if [ -f ai_exchange/CURRENT_STATE.json ]; then
  CAP_SNAPSHOT="$(python3 -c "
import json
d = json.load(open('ai_exchange/CURRENT_STATE.json')).get('canonicalState', {})
print(f\"{d.get('capFloor','?')}-{d.get('capCeiling','?')}\")
" 2>/dev/null || echo "unknown")"
  YAHOO_SOURCE_TS="$(python3 -c "
import json
d = json.load(open('ai_exchange/CURRENT_STATE.json')).get('canonicalState', {})
print(d.get('lastYahooRefresh', {}).get('timestamp', 'unknown'))
" 2>/dev/null || echo "unknown")"
fi

# --- optional hand-off notes (issues / decisions required) -----------------
NOTES_FILE="ai_exchange/REVIEW_NOTES.md"
ISSUES_BLOCK="(none)"
DECISIONS_BLOCK="(none)"
if [ -f "$NOTES_FILE" ]; then
  EXTRACTED="$(python3 -c "
import re
text = open('$NOTES_FILE', encoding='utf-8').read()
def section(name):
    m = re.search(rf'^## {name}\s*\n(.*?)(?=\n## |\Z)', text, re.S | re.M)
    if not m:
        return '(none)'
    body = m.group(1).strip()
    return body if body else '(none)'
print(section('Issues'))
print('---REVIEW-NOTES-SPLIT---')
print(section('Decisions Required'))
" 2>/dev/null || true)"
  if [ -n "$EXTRACTED" ]; then
    ISSUES_BLOCK="${EXTRACTED%%---REVIEW-NOTES-SPLIT---*}"
    DECISIONS_BLOCK="${EXTRACTED#*---REVIEW-NOTES-SPLIT---}"
    ISSUES_BLOCK="$(echo "$ISSUES_BLOCK" | sed '$d')"
    [ -z "$ISSUES_BLOCK" ] && ISSUES_BLOCK="(none)"
    [ -z "$DECISIONS_BLOCK" ] && DECISIONS_BLOCK="(none)"
  fi
fi

GENERATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

STATUS="READY_FOR_REVIEW"
[ "$SITE_VALIDATION" = "FAIL" ] && STATUS="BLOCKED"
[ "$TEST_RESULT" = "FAIL" ] && STATUS="BLOCKED"

cat > "$OUT" <<EOF
# Review Packet

Generated: ${GENERATED_AT}

## Task
${TASK_TITLE}

## Status
${STATUS}

## Git
Branch: ${BRANCH}
Commit: ${COMMIT}
Base: ${BASE_BRANCH}
Working tree: ${WORKING_TREE}

## GitHub
Repository: ${REPO_URL}
GitHub CLI: ${GH_LINE}
PR: ${PR_LINE}
CI: ${CI_LINE}

## Deployment
Public URL: ${PUBLIC_URL}
HTTP: ${LIVE_HTTP}
Fingerprint: ${FINGERPRINT}

## Changes
\`\`\`
${DIFF_STAT}
\`\`\`

## Validation
- site validation: ${SITE_VALIDATION}
- tests: ${TEST_RESULT} (${TEST_SUMMARY})
- Yahoo refresh: ${YAHOO_REFRESH}
- live HTTP: ${LIVE_HTTP}

## Canonical State
Roster baseline: ${ROSTER_LINE}
Cap snapshot: ${CAP_SNAPSHOT}
Yahoo source timestamp: ${YAHOO_SOURCE_TS}

## Files Changed
${CHANGED_FILES}

## Issues
${ISSUES_BLOCK}

## Decisions Required
${DECISIONS_BLOCK}

## Suggested Next Step
Open/update the PR from \`${BRANCH}\` if not already done, then request human/ChatGPT review of this packet.
EOF

echo "Wrote ${OUT}"
[ "$STATUS" = "BLOCKED" ] && exit 1
exit 0
