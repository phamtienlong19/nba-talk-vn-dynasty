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
from cap_model import apply_cap_policy, compute_cap_model, load_cap_policy, CapModelError

players = json.load(open("local_data/yahoo/players_normalized.json", encoding="utf-8"))
print(f"Players parsed: {len(players)}")

print("")

try:
    result = apply_cap_policy(compute_cap_model(players), load_cap_policy())
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
print(f"FORMULA FLOOR: {result['formulaFloor']}")
print(f"FORMULA CEILING: {result['formulaCeiling']}")
print(f"OFFICIAL FLOOR: {result['officialFloor']}")
print(f"OFFICIAL CEILING: {result['officialCeiling']}" + (" (commissioner override)" if result["ceilingOverride"] else ""))
print("")

# The official band is league policy (config/cap_policy.json) and is never
# changed by a refresh. A refresh only reports whether the live Yahoo FORMULA
# result still equals the formula result the official band was approved against.
print(f"Official band (policy):  {result['officialFloor']}-{result['officialCeiling']}")
print(f"Live formula band:       {result['formulaFloor']}-{result['formulaCeiling']}")
print(f"Approved formula band:   {result['approvedFormulaFloor']}-{result['approvedFormulaCeiling']}")
if result["formulaMatchesApproved"]:
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
    "formulaFloor": result["formulaFloor"],
    "formulaCeiling": result["formulaCeiling"],
    "officialFloor": result["officialFloor"],
    "officialCeiling": result["officialCeiling"],
    "ceilingOverride": result["ceilingOverride"],
    "overrideReason": result["overrideReason"],
    "approvedFormulaFloor": result["approvedFormulaFloor"],
    "approvedFormulaCeiling": result["approvedFormulaCeiling"],
    # publishedFloor/Ceiling == the official band currently on the board.
    "publishedFloor": result["officialFloor"],
    "publishedCeiling": result["officialCeiling"],
}
with open("local_data/yahoo/cap_snapshot_latest.json", "w", encoding="utf-8") as f:
    json.dump(snapshot, f, indent=2)
PYEOF

# Commissioner reference exports: normalized snapshot -> Markdown -> XLSX.
# The XLSX is derived from the Markdown (one tabular interpretation); the
# cap model above never reads either file.
python3 scripts/export_yahoo_top300.py local_data/yahoo/players_normalized.json exports/yahoo_top300_proj_dollar_rank.md
python3 scripts/export_yahoo_top300_xlsx.py exports/yahoo_top300_proj_dollar_rank.md exports/yahoo_top300_proj_dollar_rank.xlsx

# Expanded Yahoo player registry (up to 600): the legal/searchable universe
# used by the league-state layer. Separate from the 300-player market
# snapshot above; never read by the cap model or the Top-300 exports.
python3 scripts/build_player_registry.py
