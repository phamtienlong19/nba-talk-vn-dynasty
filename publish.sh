#!/usr/bin/env bash
# Sanitize, validate, and publish a new board HTML as index.html, then
# commit and push to origin/main.
#
# Usage:
#   ./publish.sh ~/Downloads/new-board.html
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <path-to-new-board.html>" >&2
  exit 2
fi

SRC="$1"
if [ ! -f "$SRC" ]; then
  echo "ERROR: source file not found: $SRC" >&2
  exit 1
fi

TMP_CANDIDATE="$(mktemp -t nba-talk-vn-dynasty-candidate).html"
trap 'rm -f "$TMP_CANDIDATE"' EXIT

python3 - "$SRC" "$TMP_CANDIDATE" <<'PYEOF'
import re
import sys

src_path, out_path = sys.argv[1], sys.argv[2]
with open(src_path, encoding="utf-8") as f:
    content = f.read()

# Strip local Yahoo @font-face blocks (this board is not allowed to depend
# on runtime font binaries we do not publish).
content = re.sub(r"@font-face\{[^}]*\}\s*", "", content, flags=re.DOTALL)

forbidden = ["/mnt/data", "file://", "assets/fonts"]
for token in forbidden:
    if token in content:
        print(f"REJECTED: candidate still contains forbidden reference '{token}'", file=sys.stderr)
        sys.exit(1)

if re.search(r"\.woff2?", content, re.IGNORECASE):
    print("REJECTED: candidate still references a .woff/.woff2 file", file=sys.stderr)
    sys.exit(1)

with open(out_path, "w", encoding="utf-8") as f:
    f.write(content)
PYEOF

echo "Sanitized candidate written, validating..."

# Validate the candidate in place of index.html without touching the real
# file until validation passes.
cp index.html "${TMP_CANDIDATE}.backup" 2>/dev/null || true
cp "$TMP_CANDIDATE" index.html
if ! ./validate.sh; then
  echo "REJECTED: candidate failed validation; index.html left unchanged" >&2
  if [ -f "${TMP_CANDIDATE}.backup" ]; then
    mv "${TMP_CANDIDATE}.backup" index.html
  fi
  exit 1
fi
rm -f "${TMP_CANDIDATE}.backup"

echo "Validation passed. Diff summary:"
git --no-pager diff --stat -- index.html || true

git add index.html ai_exchange/CURRENT_STATE.json 2>/dev/null || git add index.html

TS="$(date -u +"%Y-%m-%d %H:%M")"
git commit -m "update: refresh league board ${TS}"

# Record a deployment-freshness marker for this content commit (see
# scripts/deployment_freshness.py). Committed separately so it can record
# the real SHA of the commit above -- see that script's docstring for why.
CONTENT_SHA="$(git rev-parse HEAD)"
python3 scripts/deployment_freshness.py write "$CONTENT_SHA" build.json
git add build.json
git commit -m "chore: record build marker ${CONTENT_SHA:0:7}"

git push origin main

echo "Waiting for GitHub Pages to redeploy..."
sleep 15

./scripts/check_live.sh || echo "WARNING: live check did not confirm the update yet; check manually."

PUBLIC_URL="$(python3 -c "import json; print(json.load(open('ai_exchange/CURRENT_STATE.json')).get('publicUrl',''))" 2>/dev/null || true)"
if [ -n "$PUBLIC_URL" ]; then
  python3 scripts/deployment_freshness.py check "$PUBLIC_URL" --local-path build.json \
    || echo "WARNING: live build.json fingerprint does not match this push yet; check manually."
fi

echo "Publish complete."
git status --short
