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

print("")

try:
    result = compute_cap_model(players)
except CapModelError as e:
    print(f"CAP MODEL ERROR: {e}", file=sys.stderr)
    sys.exit(1)

# Salary-draft order (projected $ DESC, O-Rank ASC tie-break) -- see
# scripts/cap_model.py. O-Rank never defines the cap buckets.
for i, band in enumerate(result["bands"], start=1):
    print(f"R{i}: {band:.4f}")
print("")
print(f"TOP-144 PROJECTED-$ SUM: {result['top144Sum']:g}")
print(f"BENCHMARK: {result['benchmark']:.4f}")
print(f"RAW FLOOR: {result['rawFloor']:.4f}")
print(f"RAW CEILING: {result['rawCeiling']:.4f}")
print(f"PUBLISHED FLOOR: {result['roundedFloor']}")
print(f"PUBLISHED CEILING: {result['roundedCeiling']}")
print("")

try:
    canonical_state = json.load(open("ai_exchange/CURRENT_STATE.json", encoding="utf-8"))
    PUBLISHED_FLOOR = canonical_state["canonicalState"]["capFloor"]
    PUBLISHED_CEILING = canonical_state["canonicalState"]["capCeiling"]
except (OSError, KeyError, json.JSONDecodeError):
    # Defensive fallback only -- ai_exchange/CURRENT_STATE.json is the
    # canonical published floor/ceiling (see CLAUDE.md source hierarchy);
    # a hardcoded constant here would silently drift stale the moment a
    # future PR promotes a new floor/ceiling, as happened previously.
    PUBLISHED_FLOOR, PUBLISHED_CEILING = 130, 175
print(f"Current published board: {PUBLISHED_FLOOR}-{PUBLISHED_CEILING}")
print(f"Live Yahoo result:       {result['roundedFloor']}-{result['roundedCeiling']}")
if (result["roundedFloor"], result["roundedCeiling"]) == (PUBLISHED_FLOOR, PUBLISHED_CEILING):
    print("Status: MATCH")
else:
    print("Status: CHANGED — REVIEW BEFORE SEASON SNAPSHOT UPDATE")

snapshot = {
    "top144Sum": result["top144Sum"],
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

# Commissioner reference exports: normalized snapshot -> Markdown -> XLSX.
# The XLSX is derived from the Markdown (one tabular interpretation); the
# cap model above never reads either file.
python3 scripts/export_yahoo_top300.py local_data/yahoo/players_normalized.json exports/yahoo_top300_proj_dollar_rank.md
python3 scripts/export_yahoo_top300_xlsx.py exports/yahoo_top300_proj_dollar_rank.md exports/yahoo_top300_proj_dollar_rank.xlsx
