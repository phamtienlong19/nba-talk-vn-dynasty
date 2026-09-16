#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "NBA TALK VN DYNASTY"
echo ""

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"
DIRTY="$(git status --porcelain 2>/dev/null)"
REMOTE="$(git remote get-url origin 2>/dev/null || echo "none")"

echo "Branch:        $BRANCH"
echo "Commit:        $COMMIT"
echo "Working tree:  $([ -z "$DIRTY" ] && echo clean || echo dirty)"
echo "Repository:    $REMOTE"

PUBLIC_URL="unknown"
if [ -f ai_exchange/CURRENT_STATE.json ]; then
  PUBLIC_URL="$(python3 -c "import json; print(json.load(open('ai_exchange/CURRENT_STATE.json')).get('publicUrl','unknown'))" 2>/dev/null || echo unknown)"
fi
echo "Public URL:    $PUBLIC_URL"

if ./validate.sh >/tmp/dynasty_validate.log 2>&1; then
  echo "Validation:    PASS"
else
  echo "Validation:    FAIL (see ./validate.sh)"
fi

if [ "$PUBLIC_URL" != "unknown" ] && [ -n "$PUBLIC_URL" ]; then
  if curl --fail --silent --max-time 10 --location "$PUBLIC_URL" >/dev/null 2>&1; then
    echo "Live HTTP:     OK"
  else
    echo "Live HTTP:     FAIL or not yet propagated"
  fi
else
  echo "Live HTTP:     unknown (no public URL recorded)"
fi

if [ -f index.html ]; then
  HASH="$(shasum -a 256 index.html | cut -d' ' -f1)"
  echo "Board hash:    $HASH"
fi

echo "Published cap: 130-175"

LAST_YAHOO="$(ls -t local_data/yahoo/draft_analysis_*.json 2>/dev/null | head -1)"
if [ -n "$LAST_YAHOO" ]; then
  echo "Last Yahoo refresh: $(basename "$LAST_YAHOO")"
else
  echo "Last Yahoo refresh: none recorded locally"
fi

LAST_COMMIT_DATE="$(git log -1 --format=%cd --date=iso 2>/dev/null || echo unknown)"
echo "Last update:   $LAST_COMMIT_DATE"
