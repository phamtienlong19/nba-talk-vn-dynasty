#!/usr/bin/env python3
"""Pure cap-model calculation over Yahoo-ranked player rows.

Standard library only. No network access. No hardcoded R1-R9 results --
those are test fixtures/expectations, not part of the calculation itself.

Input: an iterable of player rows, each with at least:
    oRank       int, Yahoo O-Rank, 1-based, unique across the input
    capDollars  number, projected/auction cap dollars ($0 is valid)

The current league model requires ranks 1-144 (nine bands of 16) to be
present and unique. Row order in the input does not matter.
"""
from __future__ import annotations

BAND_SIZE = 16
NUM_BANDS = 9
REQUIRED_RANKS = BAND_SIZE * NUM_BANDS  # 144
FLOOR_FACTOR = 0.85
CEILING_FACTOR = 1.15


class CapModelError(ValueError):
    """Raised when input player rows do not satisfy the cap model's
    structural requirements (missing ranks, duplicates, etc.)."""


def _validate_and_index(players):
    by_rank = {}
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

        if rank in by_rank:
            raise CapModelError(f"duplicate oRank: {rank}")
        by_rank[rank] = float(dollars)

    missing = [r for r in range(1, REQUIRED_RANKS + 1) if r not in by_rank]
    if missing:
        raise CapModelError(
            f"missing required oRank values (need 1-{REQUIRED_RANKS}): "
            f"{missing[:10]}{'...' if len(missing) > 10 else ''}"
        )

    return by_rank


def band_average(by_rank: dict, band_index: int) -> float:
    """band_index is 1-based: 1 -> ranks 1-16, 2 -> ranks 17-32, ..."""
    start = (band_index - 1) * BAND_SIZE + 1
    end = band_index * BAND_SIZE
    values = [by_rank[r] for r in range(start, end + 1)]
    return sum(values) / len(values)


def compute_cap_model(players) -> dict:
    """Compute R1-R9, benchmark, and floor/ceiling from player rows.

    Returns a dict with keys: bands (list R1..R9), benchmark, rawFloor,
    rawCeiling, roundedFloor, roundedCeiling.

    Rounding: raw floor/ceiling are rounded to the nearest whole dollar
    using banker's-rounding-free "round half up" via Python's round(),
    which for these values resolves unambiguously (no .5 ties expected
    in real cap data; if one occurs, round() uses round-half-to-even).
    """
    by_rank = _validate_and_index(players)

    bands = [band_average(by_rank, i) for i in range(1, NUM_BANDS + 1)]
    benchmark = sum(bands)
    raw_floor = benchmark * FLOOR_FACTOR
    raw_ceiling = benchmark * CEILING_FACTOR

    return {
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
