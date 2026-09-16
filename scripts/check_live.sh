#!/usr/bin/env bash
# Verify the public GitHub Pages URL is live and serving the expected board.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

URL="${DYNASTY_PUBLIC_URL:-}"
if [ -z "$URL" ]; then
  if [ -f ai_exchange/CURRENT_STATE.json ]; then
    URL="$(python3 -c "import json; print(json.load(open('ai_exchange/CURRENT_STATE.json')).get('publicUrl',''))" 2>/dev/null || true)"
  fi
fi

if [ -z "$URL" ]; then
  echo "ERROR: no public URL known (set DYNASTY_PUBLIC_URL or populate ai_exchange/CURRENT_STATE.json)" >&2
  exit 1
fi

ATTEMPTS=6
DELAY=10

for i in $(seq 1 "$ATTEMPTS"); do
  BODY="$(curl --fail --location --silent --max-time 15 "$URL" || true)"
  if [ -n "$BODY" ] && echo "$BODY" | grep -q "NBA TALK VN DYNASTY" && echo "$BODY" | grep -q 'id="draft-order"'; then
    echo "LIVE: $URL"
    exit 0
  fi
  echo "attempt $i/$ATTEMPTS: not live yet, retrying in ${DELAY}s..."
  sleep "$DELAY"
done

echo "ERROR: $URL did not respond as expected after $ATTEMPTS attempts" >&2
exit 1
