#!/usr/bin/env python3
"""Normalize a raw Yahoo Draft Analysis snapshot into flat player rows.

Standard library only. Field mappings below were verified against a real
fetched response (see docs/YAHOO_DATA_SOURCE.md) -- they are not guesses.

    playerId         player.player_id
    playerKey        player.player_key
    name             player.name.full
    nbaTeam          player.editorial_team_abbr
    eligiblePositions  [p.position for p in player.eligible_positions]
    oRank            int(player_rank.rank_value) where rank_type == "OR"
    capDollars       float(player.projected_auction_value)
                     -- confirmed authoritative: recomputing the current
                        league cap model over this field reproduces the
                        published R1-R9 / benchmark / 130-175 band exactly.
    auctionValue     float(player.average_auction_cost) if present
                     -- kept alongside capDollars for reference; NOT used
                        by the cap model (see docs/YAHOO_DATA_SOURCE.md
                        for why the two diverge).
    expertRanks      raw player.player_ranks list, preserved as-is
    sourceTimestamp  passed in / read from snapshot filename
    sourceLeagueKey  fantasy_content.league.league_key from the snapshot

Players missing an "OR" rank or a parseable projected_auction_value are
skipped with a warning printed to stderr rather than silently coerced --
callers that need strict completeness should check the returned skip list.
"""
from __future__ import annotations

import json
import sys


class NormalizationError(ValueError):
    pass


def _get_o_rank(player: dict):
    for entry in player.get("player_ranks", []) or []:
        rank = entry.get("player_rank", {})
        if rank.get("rank_type") == "OR" and rank.get("rank_value") is not None:
            try:
                return int(rank["rank_value"])
            except (TypeError, ValueError):
                return None
    return None


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_player(player: dict, source_league_key: str, source_timestamp: str):
    """Return a normalized row dict, or None if the player lacks required fields."""
    o_rank = _get_o_rank(player)
    cap_dollars = _to_float(player.get("projected_auction_value"))

    if o_rank is None or cap_dollars is None:
        return None

    eligible_positions = [
        p.get("position")
        for p in player.get("eligible_positions", []) or []
        if p.get("position")
    ]

    return {
        "playerId": player.get("player_id"),
        "playerKey": player.get("player_key"),
        "name": (player.get("name") or {}).get("full"),
        "nbaTeam": player.get("editorial_team_abbr"),
        "eligiblePositions": eligible_positions,
        "oRank": o_rank,
        "capDollars": cap_dollars,
        "auctionValue": _to_float(player.get("average_auction_cost")),
        "expertRanks": player.get("player_ranks"),
        "sourceTimestamp": source_timestamp,
        "sourceLeagueKey": source_league_key,
    }


def normalize_snapshot(raw: dict, source_timestamp: str = "") -> dict:
    """Normalize a full raw Yahoo response dict.

    Returns {"players": [...normalized rows...], "skipped": [<player_id or name>, ...]}.
    Raises NormalizationError if the response no longer has the expected shape.
    """
    try:
        league = raw["fantasy_content"]["league"]
        raw_players = league["players"]
    except (KeyError, TypeError) as e:
        raise NormalizationError(f"unexpected snapshot shape: {e}") from e

    if not isinstance(raw_players, list):
        raise NormalizationError("league.players is not a list")

    league_key = league.get("league_key", "")

    normalized = []
    skipped = []
    for entry in raw_players:
        player = entry.get("player") if isinstance(entry, dict) else None
        if player is None:
            skipped.append(str(entry)[:80])
            continue
        row = normalize_player(player, league_key, source_timestamp)
        if row is None:
            skipped.append(player.get("player_id") or (player.get("name") or {}).get("full"))
            continue
        normalized.append(row)

    return {"players": normalized, "skipped": skipped}


def main():
    if len(sys.argv) != 3:
        print(
            "usage: normalize_yahoo_players.py <raw-snapshot.json> <output.json>",
            file=sys.stderr,
        )
        sys.exit(2)

    raw_path, out_path = sys.argv[1], sys.argv[2]
    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    source_timestamp = ""
    # draft_analysis_2026-09-16T101300Z.json -> 2026-09-16T101300Z
    base = raw_path.rsplit("/", 1)[-1]
    if base.startswith("draft_analysis_") and base.endswith(".json"):
        source_timestamp = base[len("draft_analysis_"):-len(".json")]

    try:
        result = normalize_snapshot(raw, source_timestamp)
    except NormalizationError as e:
        print(f"NORMALIZATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if result["skipped"]:
        print(
            f"WARNING: skipped {len(result['skipped'])} players missing "
            f"oRank/capDollars",
            file=sys.stderr,
        )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result["players"], f, indent=2, ensure_ascii=False)

    print(f"Normalized {len(result['players'])} players -> {out_path}")


if __name__ == "__main__":
    main()
