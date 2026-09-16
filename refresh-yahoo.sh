#!/usr/bin/env bash
# Fetch the live Yahoo public Draft Analysis snapshot, normalize it,
# recompute the cap model, and report whether it matches the currently
# published board. Never modifies index.html.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "NBA TALK VN — YAHOO CAP REFRESH"
echo ""

RAW_PATH="$(python3 scripts/fetch_yahoo_draft_analysis.py)"
echo "Source league: $(python3 -c "import json; print(json.load(open('config/yahoo_source.json'))['leagueKey'])")"

python3 scripts/normalize_yahoo_players.py "$RAW_PATH" local_data/yahoo/players_normalized.json

python3 - "$RAW_PATH" <<'PYEOF'
import json
import sys

sys.path.insert(0, "scripts")
from cap_model import compute_cap_model, CapModelError

players = json.load(open("local_data/yahoo/players_normalized.json", encoding="utf-8"))
print(f"Players parsed: {len(players)}")

ranks = {p["oRank"] for p in players}
complete_1_144 = all(r in ranks for r in range(1, 145))
print(f"Ranks 1-144 complete: {'PASS' if complete_1_144 else 'FAIL'}")
print("")

try:
    result = compute_cap_model(players)
except CapModelError as e:
    print(f"CAP MODEL ERROR: {e}", file=sys.stderr)
    sys.exit(1)

for i, band in enumerate(result["bands"], start=1):
    print(f"R{i}: {band:.4f}")
print("")
print(f"Benchmark: {result['benchmark']:.4f}")
print(f"Floor: {result['roundedFloor']}")
print(f"Ceiling: {result['roundedCeiling']}")
print("")

PUBLISHED_FLOOR, PUBLISHED_CEILING = 130, 175
print(f"Current published board: {PUBLISHED_FLOOR}-{PUBLISHED_CEILING}")
print(f"Live Yahoo result:       {result['roundedFloor']}-{result['roundedCeiling']}")
if (result["roundedFloor"], result["roundedCeiling"]) == (PUBLISHED_FLOOR, PUBLISHED_CEILING):
    print("Status: MATCH")
else:
    print("Status: CHANGED — REVIEW BEFORE SEASON SNAPSHOT UPDATE")

snapshot = {
    "fetchedAt": players[0]["sourceTimestamp"] if players else None,
    "rawSnapshot": sys.argv[1],
    "bands": result["bands"],
    "benchmark": result["benchmark"],
    "rawFloor": result["rawFloor"],
    "rawCeiling": result["rawCeiling"],
    "roundedFloor": result["roundedFloor"],
    "roundedCeiling": result["roundedCeiling"],
    "publishedFloor": PUBLISHED_FLOOR,
    "publishedCeiling": PUBLISHED_CEILING,
}
with open("local_data/yahoo/cap_snapshot_latest.json", "w", encoding="utf-8") as f:
    json.dump(snapshot, f, indent=2)
PYEOF
