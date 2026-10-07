#!/usr/bin/env python3
"""Build the expanded Yahoo PLAYER REGISTRY (the legal/searchable player
universe) from a raw Yahoo Draft Analysis snapshot that requested up to 600
players (config/yahoo_source.json `registryUrl`).

This is deliberately separate from data/yahoo/players_normalized.json (the
300-player market snapshot the cap model, Top-300 exports and FA/DRAFT
recommendation read): the registry answers "who can be selected", the
recommendation board answers "who do we suggest". Identity is the Yahoo
player_id / player_key; names are display only.

Usage:
    python3 scripts/build_player_registry.py                 # fetch live (registryUrl)
    python3 scripts/build_player_registry.py --raw FILE.json # build from a saved raw snapshot
Writes data/yahoo/player_registry.json (deterministic, sorted by Yahoo OR).
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_yahoo_draft_analysis import fetch_raw, load_config, validate_shape  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEFAULT_OUT = os.path.join(REPO_ROOT, "data", "yahoo", "player_registry.json")
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "config", "yahoo_source.json")


class RegistryError(ValueError):
    pass


def _or_rank(player: dict):
    for entry in player.get("player_ranks", []) or []:
        rank = entry.get("player_rank", {})
        if rank.get("rank_type") == "OR" and rank.get("rank_value") is not None:
            try:
                return int(rank["rank_value"])
            except (TypeError, ValueError):
                return None
    return None


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_registry(raw: dict, fetched_at: str | None = None) -> dict:
    league = raw["fantasy_content"]["league"]
    players, seen = [], set()
    for entry in validate_shape(raw):
        p = entry.get("player", entry)
        pid, pkey = p.get("player_id"), p.get("player_key")
        if not pid or not pkey:
            raise RegistryError(f"player without player_id/player_key: {p.get('name')}")
        if pkey in seen:
            raise RegistryError(f"duplicate Yahoo player_key {pkey}")
        seen.add(pkey)
        eligible = [e.get("position") for e in p.get("eligible_positions", []) or [] if e.get("position")]
        headshot = (p.get("headshot") or {}).get("url") or p.get("image_url")
        players.append({
            "playerId": str(pid),
            "playerKey": pkey,
            "name": (p.get("name") or {}).get("full"),
            "nbaTeam": p.get("editorial_team_abbr"),
            "displayPosition": p.get("display_position"),
            "eligiblePositions": eligible,
            "projectedAuctionValue": _num(p.get("projected_auction_value")),
            "oRank": _or_rank(p),
            "headshotUrl": headshot,
        })
    players.sort(key=lambda r: (r["oRank"] is None, r["oRank"] or 0, r["playerId"]))
    return {
        "source": league.get("league_key"),
        "fetchedAt": fetched_at,
        "playerCount": len(players),
        "note": "Legal/searchable player universe (Yahoo expanded draft analysis). "
                "Identity = playerKey. The FA/DRAFT 60 is a recommendation over this, not the universe.",
        "players": players,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default=None, help="saved raw draft-analysis JSON (skips the network fetch)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    args = ap.parse_args()
    if args.raw:
        with open(args.raw, encoding="utf-8") as f:
            raw = json.load(f)
        fetched_at = os.path.basename(args.raw)
    else:
        import datetime
        raw = json.loads(fetch_raw(load_config(args.config)["registryUrl"]))
        fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    reg = build_registry(raw, fetched_at)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Wrote {reg['playerCount']} players -> {args.out}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"PLAYER REGISTRY ERROR: {e}", file=sys.stderr)
        sys.exit(1)
