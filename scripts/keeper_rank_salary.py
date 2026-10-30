#!/usr/bin/env python3
"""Build config/keeper_salary_by_rank.json: the keeper salary a player carries at each ACTUAL descending rank.

Owner rule (2026-10-30): rank dictates salary, and the rank is a player's real position when the Yahoo Top 300 is sorted by
projected $ (highest first), not Yahoo's O-Rank column (Sandro Mamukelashvili is $3 at O-Rank 139 but sits at position 116).
The table is that sorted $ curve: salaryByRank[i] is the salary of rank i+1; every rank past the end carries $0. `order` is the
default ranking (player keys, rank 1 first) the What-If keeper board starts from.

Same ordering as the cap model and the Top-300 export (scripts/cap_model.py draft_order, scripts/export_yahoo_top300.py):
projected $ descending, O-Rank ascending inside an equal-dollar tier. Standard library plus cap_model only.

Usage: python3 scripts/keeper_rank_salary.py [players_normalized.json] [out.json]
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cap_model as cm  # noqa: E402

ROOT = os.path.join(HERE, "..")
PLAYERS = os.path.join(ROOT, "data", "yahoo", "players_normalized.json")
PROVENANCE = os.path.join(ROOT, "data", "yahoo", "provenance.json")
OUT = os.path.join(ROOT, "config", "keeper_salary_by_rank.json")


class RankSalaryError(ValueError):
    pass


def ranked(players: list) -> list:
    """Players in actual descending order: projected $ desc, O-Rank asc, name."""
    rows = sorted(players, key=lambda p: (-float(p["capDollars"]), int(p["oRank"]), p["name"]))
    keys = [p["playerKey"] for p in rows]
    if len(set(keys)) != len(keys):
        raise RankSalaryError("duplicate player keys in the Yahoo snapshot")
    return rows


def build(players: list, source: dict | None = None) -> dict:
    rows = ranked(players)
    salaries = [float(p["capDollars"]) for p in rows]
    if any(a < b for a, b in zip(salaries, salaries[1:])):
        raise RankSalaryError("salaries are not non-increasing in rank order")
    if any(s != int(s) for s in salaries):
        raise RankSalaryError("projected $ must be whole dollars")
    paid = [int(s) for s in salaries if s > 0]
    model = cm.compute_cap_model(players)
    return {
        "version": 1,
        "rule": "Keeper salary = the salary at the player's ACTUAL descending rank (projected $ sorted high to low, ties by Yahoo O-Rank), "
                "not his O-Rank. Ranks past the end of salaryByRank carry $0. Owner decision 2026-10-30.",
        "source": dict(source or {}, players=len(rows), paidRanks=len(paid)),
        "capModel": {"top144Sum": model["top144Sum"], "benchmark": model["benchmark"],
                     "formulaFloor": model["roundedFloor"], "formulaCeiling": model["roundedCeiling"]},
        "salaryByRank": paid,
        "order": [p["playerKey"] for p in rows],
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    src = argv[0] if argv else PLAYERS
    out = argv[1] if len(argv) > 1 else OUT
    with open(src, encoding="utf-8") as f:
        players = json.load(f)
    prov = {}
    if os.path.exists(PROVENANCE):
        with open(PROVENANCE, encoding="utf-8") as f:
            prov = json.load(f)
    data = build(players, {"file": os.path.relpath(src, ROOT) if os.path.abspath(src).startswith(os.path.abspath(ROOT)) else src,
                           "fetchedAt": prov.get("fetchedAt"), "league": prov.get("source")})
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, out)
    print(f"wrote {os.path.relpath(out, ROOT)}: {len(data['order'])} ranked, {len(data['salaryByRank'])} paid, top ${data['salaryByRank'][0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
