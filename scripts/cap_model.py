#!/usr/bin/env python3
"""Pure cap-model calculation over Yahoo player rows.

Standard library only. No network access. No hardcoded R1-R9 results --
those are test fixtures/expectations, not part of the calculation itself.

The benchmark simulates a Yahoo salary-cap draft, so players are ordered
by PROJECTED AUCTION VALUE (capDollars) descending -- NOT by Yahoo
O-Rank. O-Rank order is not salary order (e.g. a $5 player at O-Rank 123
is drafted ahead of a $4 player at O-Rank 97). O-Rank is used only as a
deterministic tie-break inside an equal-dollar tier.

Input: an iterable of player rows, each with at least:
    capDollars  number, projected auction value ($0 is valid)
    oRank       int, Yahoo O-Rank, unique across the input (tie-break only)

The current league model takes the first 144 players (nine bands of 16)
in that order. Row order in the input does not matter.
"""
from __future__ import annotations

BAND_SIZE = 16
NUM_BANDS = 9
REQUIRED_PLAYERS = BAND_SIZE * NUM_BANDS  # 144
NUM_TEAMS = 16
FLOOR_FACTOR = 0.85
CEILING_FACTOR = 1.15


class CapModelError(ValueError):
    """Raised when input player rows do not satisfy the cap model's
    structural requirements (too few players, duplicates, etc.)."""


def draft_order(players) -> list:
    """Return (capDollars, oRank) pairs in simulated salary-draft order:
    capDollars DESC, then Yahoo O-Rank ASC within an equal-dollar tier."""
    seen_ranks = set()
    pairs = []
    for row in players:
        if "oRank" not in row or "capDollars" not in row:
            raise CapModelError(
                "each player row requires 'oRank' and 'capDollars'"
            )
        rank = row["oRank"]
        dollars = row["capDollars"]

        if not isinstance(rank, int) or isinstance(rank, bool):
            raise CapModelError(f"oRank must be an int, got {rank!r}")
        if not isinstance(dollars, (int, float)) or isinstance(dollars, bool):
            raise CapModelError(f"capDollars must be numeric, got {dollars!r}")
        if rank in seen_ranks:
            raise CapModelError(f"duplicate oRank: {rank}")
        seen_ranks.add(rank)
        pairs.append((float(dollars), rank))

    if len(pairs) < REQUIRED_PLAYERS:
        raise CapModelError(
            f"need at least {REQUIRED_PLAYERS} players, got {len(pairs)}"
        )
    pairs.sort(key=lambda t: (-t[0], t[1]))
    return pairs


def compute_cap_model(players) -> dict:
    """Compute R1-R9, benchmark, and floor/ceiling from player rows.

    Returns a dict with keys: top144Sum, bands (list R1..R9), benchmark,
    rawFloor, rawCeiling, roundedFloor, roundedCeiling.

    bands[i] is the mean projected $ of the i-th group of 16 in salary-draft
    order; benchmark = sum(bands) = top144Sum / 16.

    Rounding uses Python's round() (nearest whole dollar; round-half-to-even
    on exact .5 ties, which do not occur in current data).
    """
    top = draft_order(players)[:REQUIRED_PLAYERS]
    dollars = [d for d, _ in top]

    bands = [
        sum(dollars[i * BAND_SIZE:(i + 1) * BAND_SIZE]) / BAND_SIZE
        for i in range(NUM_BANDS)
    ]
    top_sum = sum(dollars)
    benchmark = top_sum / NUM_TEAMS
    raw_floor = benchmark * FLOOR_FACTOR
    raw_ceiling = benchmark * CEILING_FACTOR

    return {
        "top144Sum": top_sum,
        "bands": bands,
        "benchmark": benchmark,
        "rawFloor": raw_floor,
        "rawCeiling": raw_ceiling,
        "roundedFloor": round(raw_floor),
        "roundedCeiling": round(raw_ceiling),
    }


def main():
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: cap_model.py <normalized-players.json>", file=sys.stderr)
        sys.exit(2)

    with open(sys.argv[1], encoding="utf-8") as f:
        players = json.load(f)

    try:
        result = compute_cap_model(players)
    except CapModelError as e:
        print(f"CAP MODEL ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
