#!/usr/bin/env python3
"""Provisional lottery inputs derived from the published Yahoo standings. DATA ONLY: no draw, no simulation, no UI, no draft order.

    python3 scripts/lottery_order.py                  # JSON to stdout, for the 2027 draft

Four things stay separate: (A) Yahoo's official standings, (B) the provisional reverse-standings order, (C) these provisional
lottery inputs (tickets per config/draft_lottery_rules.json, eligibility per scripts/lottery_eligibility.py), and (D) the
commissioner-adjusted final draft order, which is NOT computed here. Everything returned is labelled provisional.

The rank 3/4 bonus follows the labelled interpretation recorded in config (lottery.rank3And4). Still omitted because the rules leave them
undecided (docs/STANDINGS_REFRESH.md, 'Open league-rule questions'): how the reward lands in rounds 2-3, the effect of under-cap penalties on position, any head-to-head tie-break beyond Yahoo's
printed rank, and the 2027 lottery format. A team's ticket count is a pure function of its Yahoo rank and is only as final as
that rank. Standard library only.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lottery_eligibility as le  # noqa: E402
import yahoo_standings as ys  # noqa: E402

LABEL = "PROVISIONAL: derived from Yahoo standings; not a draft order"


def provisional_lottery(snapshot: dict | None, cfg: dict | None = None, draft: int = 2027) -> dict | None:
    """-> None until the season has started (ranks do not exist yet); else the provisional inputs, worst record first."""
    if not snapshot or not snapshot.get("started"):
        return None
    cfg = cfg or le.load()
    lot = cfg["lottery"]
    tickets = lot["ticketsByRank"]
    elig = le.eligibility(cfg, draft)
    total = lot["totalCombinations"]
    teams = []
    for t in sorted(snapshot["teams"], key=lambda t: -t["rank"]):                    # rank 16 first: Yahoo's order, not recomputed
        n = tickets.get(str(t["rank"]))
        e = elig.get(t["franchiseId"], {})
        teams.append({"franchiseId": t["franchiseId"], "rank": t["rank"], "inLottery": n is not None, "tickets": n,
                      "shareOf%d" % total: None if n is None else round(n / total, 4),
                      "canPick1": e.get("canPick1", True), "canPickTop2": e.get("canPickTop2", True), "restrictions": e.get("reasons", [])})
    b = lot["rank3And4"]
    n = len(snapshot["teams"])
    block = [n + 1 - b["blockRanks"][0], n + 1 - b["blockRanks"][1]]                    # ranks 8..3 of 16 -> picks 9..14
    bonus = {"ranks": b["ranks"], "firstPick": block[0], "block": block, "interpretation": b["interpretation"]}
    for t in teams:
        t["naturalPick"] = n + 1 - t["rank"]
    return {"label": LABEL, "bonus": bonus, "draft": draft, "standingsSourceUpdatedAt": snapshot["sourceUpdatedAt"], "totalCombinations": total,
            "reverseOrder": [t["franchiseId"] for t in teams], "teams": teams,
            "lotteryPicks": lot["drawOrder"], "rounds2And3": lot["rounds2And3"], "rank3And4": lot["rank3And4Bonus"]}


def main(argv=None) -> int:
    out = provisional_lottery(ys.current_snapshot())
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
