#!/usr/bin/env bash
# Single quick health view. Should fit in one terminal screen.
# Uses cached/current state and lightweight checks -- no expensive
# network work beyond one HTTP fetch for reachability/fingerprint.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "NBA TALK VN DYNASTY"
echo ""

STATE_FILE="ai_exchange/CURRENT_STATE.json"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

get_state() {
  # get_state <python-expr-on-d> <default>
  python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    v = $1
    print(v if v not in (None, '') else '$2')
except Exception:
    print('$2')
" 2>/dev/null || echo "$2"
}

DEPLOYED_BRANCH="$(get_state "d.get('deployed',{}).get('branch')" unknown)"
DEPLOYED_COMMIT="$(get_state "d.get('deployed',{}).get('commit','')[:7]" unknown)"
PUBLIC_URL="$(get_state "d.get('publicUrl')" unknown)"
CAP_FLOOR="$(get_state "d.get('canonicalState',{}).get('capFloor')" '?')"
CAP_CEILING="$(get_state "d.get('canonicalState',{}).get('capCeiling')" '?')"
YAHOO_TS="$(get_state "d.get('canonicalState',{}).get('lastYahooRefresh',{}).get('timestamp')" unknown)"

echo "Deployed main:   ${DEPLOYED_BRANCH}@${DEPLOYED_COMMIT}"

LIVE_FINGERPRINT="unknown"
if [ "$PUBLIC_URL" != "unknown" ] && [ -f build.json ]; then
  if python3 scripts/deployment_freshness.py check "$PUBLIC_URL" --local-path build.json --attempts 1 >/tmp/dynasty_status_fp.log 2>&1; then
    LIVE_FINGERPRINT="FRESH"
  else
    LIVE_FINGERPRINT="STALE"
  fi
elif [ ! -f build.json ]; then
  LIVE_FINGERPRINT="no local build.json"
fi
echo "Live fingerprint: ${LIVE_FINGERPRINT}"

echo "Working branch:  ${BRANCH}"

ACTIVE_ISSUE="none"
if [ -f tasks/ACTIVE.md ]; then
  ISSUE_LINE="$(grep -m1 '^Issue: ' tasks/ACTIVE.md 2>/dev/null | sed 's/^Issue: //')"
  [ -n "$ISSUE_LINE" ] && ACTIVE_ISSUE="$ISSUE_LINE"
fi
echo "Active Issue:    ${ACTIVE_ISSUE}"

PR_LINE="unknown (gh unavailable)"
CI_LINE="unknown (gh unavailable)"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  PR_LINE="$(gh pr view "$BRANCH" --json url,state -q '"\(.url) (\(.state))"' 2>/dev/null || echo none)"
  [ -z "$PR_LINE" ] && PR_LINE="none"
  CI_JSON="$(gh run list --branch "$BRANCH" --limit 1 --json status,conclusion 2>/dev/null || echo '[]')"
  if [ -n "$CI_JSON" ] && [ "$CI_JSON" != "[]" ]; then
    CI_LINE="$(python3 -c "
import json,sys
d=json.load(sys.stdin)
r=d[0]
print(f\"{r['status']}/{r['conclusion']}\")
" <<<"$CI_JSON" 2>/dev/null || echo unknown)"
  else
    CI_LINE="no runs found"
  fi
fi
echo "PR:              ${PR_LINE}"
echo "CI:              ${CI_LINE}"

if ./validate.sh >/tmp/dynasty_validate.log 2>&1; then
  echo "Validation:      PASS"
else
  echo "Validation:      FAIL (see ./validate.sh)"
fi

echo "Yahoo snapshot:  ${YAHOO_TS}"
echo "Published cap:   ${CAP_FLOOR}-${CAP_CEILING}"

ROSTER_LINE="unknown"
if [ -f data/2026-27/franchises.json ] && [ -f data/2026-27/prekeeper_rosters.json ]; then
  ROSTER_LINE="$(python3 -c "
import json
f = json.load(open('data/2026-27/franchises.json'))
r = json.load(open('data/2026-27/prekeeper_rosters.json'))
print(f\"{len(f['franchises'])} franchises, {len(r['assignments'])} assignments\")
" 2>/dev/null || echo "unknown")"
fi
echo "Roster baseline: ${ROSTER_LINE}"

echo "Public URL:      ${PUBLIC_URL}"
