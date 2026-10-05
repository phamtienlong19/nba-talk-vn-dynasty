#!/usr/bin/env python3
"""Build the machine-readable Yahoo refresh result artifact.

Consumes the outputs `./refresh-yahoo.sh` already produces (the cap
snapshot and the normalized player list) -- no re-fetching, no
re-parsing of raw Yahoo JSON. Standard library only.

Usage:
    python3 scripts/build_yahoo_refresh_result.py \
        --cap-snapshot local_data/yahoo/cap_snapshot_latest.json \
        --current-players local_data/yahoo/players_normalized.json \
        --source-config config/yahoo_source.json \
        --output artifacts/yahoo-refresh-result.json \
        [--previous-players previous/players_normalized.json] \
        [--published-players data/yahoo/players_normalized.json] \
        [--exports-md exports/yahoo_top300_proj_dollar_rank.md]

CAP status compares the live FORMULA band to the formula band the official
league band was approved against (cap snapshot `approvedFormula*`), never to
the official band itself -- the official band (e.g. 131-178) is commissioner
policy and a refresh can't change it. Status is also CHANGED when the live
Yahoo snapshot differs from the published one (--published-players) or the
committed Top-300 export is stale vs. the live snapshot (--exports-md).

If --previous-players is omitted or the file doesn't exist, rankingChanges
is emitted as an empty list with rankingChangesNote explaining why (e.g.
no prior tracked run to diff against yet).
"""
from __future__ import annotations

import argparse
import json
import os


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_ranking_changes(current_players, previous_players):
    """Compare oRank -> player identity between two normalized snapshots.

    Returns a list of {"oRank": int, "previousPlayer": str|None,
    "currentPlayer": str|None} for every rank where the occupant changed.
    """
    current_by_rank = {p["oRank"]: p.get("name") for p in current_players}
    previous_by_rank = {p["oRank"]: p.get("name") for p in previous_players}

    changes = []
    for rank in sorted(set(current_by_rank) | set(previous_by_rank)):
        current_name = current_by_rank.get(rank)
        previous_name = previous_by_rank.get(rank)
        if current_name != previous_name:
            changes.append({
                "oRank": rank,
                "previousPlayer": previous_name,
                "currentPlayer": current_name,
            })
    return changes


PLAYER_FIELDS = ("name", "nbaTeam", "eligiblePositions", "oRank", "capDollars")


def snapshot_differs(current_players, published_players) -> bool:
    """True if any market field differs between two normalized snapshots
    (timestamps / raw expert ranks are deliberately ignored)."""
    def key(players):
        return sorted(
            (tuple(json.dumps(p.get(f), sort_keys=True, ensure_ascii=False) for f in PLAYER_FIELDS)
             for p in players)
        )
    return key(current_players) != key(published_players)


def exports_stale(current_players, md_path) -> bool:
    """True if the committed Markdown export isn't what the live snapshot renders."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from export_yahoo_top300 import ExportError, build_rows, render_markdown
    if not os.path.isfile(md_path):
        return True
    try:
        fresh = render_markdown(build_rows(current_players))
    except ExportError:
        return True
    with open(md_path, encoding="utf-8") as f:
        return f.read() != fresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cap-snapshot", required=True)
    parser.add_argument("--current-players", required=True)
    parser.add_argument("--source-config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--previous-players", default=None)
    parser.add_argument("--published-players", default=None)
    parser.add_argument("--exports-md", default=None)
    args = parser.parse_args()

    cap_snapshot = load_json(args.cap_snapshot)
    current_players = load_json(args.current_players)
    source_config = load_json(args.source_config)

    # Baseline = the FORMULA band the official band was approved against
    # (falls back to the published band for snapshots without a policy).
    previous = {
        "floor": cap_snapshot.get("approvedFormulaFloor", cap_snapshot["publishedFloor"]),
        "ceiling": cap_snapshot.get("approvedFormulaCeiling", cap_snapshot["publishedCeiling"]),
    }
    current = {
        "floor": cap_snapshot["roundedFloor"],
        "ceiling": cap_snapshot["roundedCeiling"],
    }
    reasons = []
    if current != previous:
        reasons.append("formulaBandChanged")
    if args.published_players and os.path.isfile(args.published_players):
        if snapshot_differs(current_players, load_json(args.published_players)):
            reasons.append("yahooSnapshotChanged")
    if args.exports_md and exports_stale(current_players, args.exports_md):
        reasons.append("exportsStale")
    status = "CHANGED" if reasons else "MATCH"

    result = {
        "source": source_config["leagueKey"],
        "fetchedAt": cap_snapshot.get("fetchedAt"),
        "status": status,
        "previous": previous,
        "current": current,
        "reasons": reasons,
        "rankingChanges": [],
    }
    if "officialFloor" in cap_snapshot:
        result["official"] = {
            "floor": cap_snapshot["officialFloor"],
            "ceiling": cap_snapshot["officialCeiling"],
            "ceilingOverride": cap_snapshot.get("ceilingOverride", False),
            "overrideReason": cap_snapshot.get("overrideReason"),
        }

    if args.previous_players and os.path.isfile(args.previous_players):
        previous_players = load_json(args.previous_players)
        result["rankingChanges"] = build_ranking_changes(current_players, previous_players)
    else:
        result["rankingChangesNote"] = (
            "no previous tracked-run snapshot available to diff against "
            "(first run, or previous run's artifact expired/unavailable)"
        )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Wrote {args.output}: status={status}")


if __name__ == "__main__":
    main()
