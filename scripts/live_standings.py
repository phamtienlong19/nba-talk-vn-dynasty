#!/usr/bin/env python3
"""Standings from weekly matchup results: the official table (finished weeks) and the live table (finished weeks + the week in
progress), with ties, the playoff picture and the projected reverse order. DISPLAY / EVIDENCE ONLY.

    tally(results)                    -> {teamId: {"w", "l", "t"}} from stored finished weeks
    table(official, live, divisions)  -> rows with record, pct, shared rank for equal records, movement vs the official table
    playoff_picture(rows, cfg)        -> 8 seeds: both division leaders plus the best remaining records; ties at the line are marked
    projected_snapshot(rows, order)   -> a standings-snapshot-shaped dict for scripts/lottery_order.py (ties broken by `order`, marked)

Rules used (docs/LIVE_DATA.md): a tie counts half (7-1-1 = .833, as Yahoo prints it); games back = ((division leader W - W) + (L - division leader L)) / 2,
ties ignored (Yahoo measures it from the division leader); teams with equal records share a rank and are marked tied: Yahoo prints no regular-season tiebreaker and its order
within ties does not follow head-to-head or points, so none is invented. The live table counts only categories that are already
decided in the week in progress (a category with no attempts yet is skipped), and is always labelled PROVISIONAL.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo_matchups as ym  # noqa: E402

LABEL = "PROVISIONAL: if the week ended now"


def _blank():
    return {"w": 0, "l": 0, "t": 0}


def tally(weeks: dict) -> dict:
    """Records from stored finished-week documents ({week: doc}) keyed by Yahoo team id."""
    out = {}
    for _w, doc in sorted(weeks.items()):
        for m in doc["matchups"]:
            r = m["result"]
            a, b = (t["teamId"] for t in m["teams"])
            for tid, wins, losses in ((a, r["a"], r["b"]), (b, r["b"], r["a"])):
                t = out.setdefault(tid, _blank())
                t["w"] += wins
                t["l"] += losses
                t["t"] += r["t"]
    return out


def live_results(pages: list) -> dict:
    """{teamId: {"w","l","t"}} from matchup pages of the week in progress. Only decided categories count."""
    out = {}
    for p in pages:
        res = ym.matchup_result(p)
        a, b = res["teams"]
        for tid, wins, losses in ((a, res["a"], res["b"]), (b, res["b"], res["a"])):
            out[tid] = {"w": wins, "l": losses, "t": res["t"], "decided": res["decided"]}
    return out


def pct(rec) -> float | None:
    n = rec["w"] + rec["l"] + rec["t"]
    return None if not n else (rec["w"] + 0.5 * rec["t"]) / n


def _ranked(records: dict) -> list:
    """Teams best first by pct; equal records share the same (competition) rank and are flagged `tied`."""
    items = sorted(records.items(), key=lambda kv: (-(pct(kv[1]) or 0.0), kv[0]))
    rows, last = [], None
    for i, (tid, rec) in enumerate(items):
        key = (rec["w"], rec["l"], rec["t"])
        rank = rows[-1]["rank"] if last == key else i + 1
        rows.append({"teamId": tid, "w": rec["w"], "l": rec["l"], "t": rec["t"], "pct": pct(rec), "rank": rank})
        last = key
    for r in rows:
        r["tied"] = sum(1 for x in rows if x["rank"] == r["rank"]) > 1
    if rows:
        top = rows[0]
        for r in rows:
            r["gb"] = ((top["w"] - r["w"]) + (r["l"] - top["l"])) / 2
    return rows


def table(official: dict, live: dict | None = None, divisions: dict | None = None) -> list:
    """The standings if the week in progress ended now (`live` None = the official table). `official` / `live` map team id -> record."""
    base = _ranked(official)
    pos = {r["teamId"]: r for r in base}
    merged = {}
    for tid, rec in official.items():
        add = (live or {}).get(tid) or _blank()
        merged[tid] = {k: rec[k] + add[k] for k in ("w", "l", "t")}
    rows = _ranked(merged)
    leader = {}
    for r in rows:                                                                   # Yahoo's games back is measured from the DIVISION leader
        leader.setdefault((divisions or {}).get(r["teamId"]), r)
    for r in rows:
        d = (divisions or {}).get(r["teamId"])
        top = leader.get(d) if d is not None else rows[0]
        r["gbOverall"] = r["gb"]
        r["gb"] = ((top["w"] - r["w"]) + (r["l"] - top["l"])) / 2
    for r in rows:
        o = pos[r["teamId"]]
        r.update({"division": (divisions or {}).get(r["teamId"]), "officialRank": o["rank"], "officialRecord": [o["w"], o["l"], o["t"]],
                  "moved": o["rank"] - r["rank"], "label": LABEL if live else "official"})
    return rows


def playoff_picture(rows: list, cfg: dict | None = None) -> dict:
    """8 playoff teams: each division's winner advances, seeded by overall record, and the best remaining records fill the other spots
    (Yahoo settings 2026-11-02: 'Division winners advance but seeded by overall standings'). Honest about ties: a division whose top
    records are level marks those teams `divisionTie` (one of them takes the division spot, undecided), and a team level with the last
    team in is 'bubble', not 'in' or 'out'."""
    spots = (cfg or {}).get("teams", 8)
    divs = sorted({r["division"] for r in rows if r.get("division")})
    status, leaders, div_tie = {}, {}, set()
    reserved = []
    for d in divs:
        members = sorted((r for r in rows if r["division"] == d), key=lambda r: (r["rank"], r["teamId"]))
        top = [r for r in members if r["rank"] == members[0]["rank"]]
        leaders[d] = [r["teamId"] for r in top]
        reserved.append(top[0])                                                      # the division spot (the first of any level teams)
        if len(top) > 1:
            div_tie.update(r["teamId"] for r in top)
    taken = {r["teamId"] for r in reserved}
    pool = sorted((r for r in rows if r["teamId"] not in taken), key=lambda r: (r["rank"], r["teamId"]))
    open_spots = max(0, spots - len(reserved))
    line = pool[open_spots - 1]["pct"] if 0 < open_spots <= len(pool) else None
    for r in reserved:
        status[r["teamId"]] = "in"
    for i, r in enumerate(pool):
        status[r["teamId"]] = "in" if i < open_spots else "out"
    if line is not None:                                                             # level with the last spot: still open
        level = [r for r in pool if r["pct"] == line]
        if any(status[r["teamId"]] == "out" for r in level):
            for r in level:
                status[r["teamId"]] = "bubble"
    qualified = [r for r in rows if status.get(r["teamId"]) == "in"]
    seeds = {r["teamId"]: i + 1 for i, r in enumerate(sorted(qualified, key=lambda r: (r["rank"], r["teamId"])))}
    return {"spots": spots, "status": status, "seeds": seeds, "divisionLeaders": leaders, "divisionTie": sorted(div_tie), "linePct": line}


def projected_snapshot(rows: list, official_order: list | None = None, source_updated_at: str = "") -> dict:
    """A standings-snapshot-shaped dict (`started`, `teams` with unique ranks) so scripts/lottery_order.py can run on the projected
    table. Equal records are ordered by `official_order` (team ids, best first) and listed in `tiedRanks`; that order is a stand-in,
    not a rule."""
    pos = {tid: i for i, tid in enumerate(official_order or [])}
    ordered = sorted(rows, key=lambda r: (r["rank"], pos.get(r["teamId"], 99), r["teamId"]))
    return {"started": True, "sourceUpdatedAt": source_updated_at, "label": LABEL,
            "teams": [{"teamId": r["teamId"], "rank": i + 1, "tied": r["tied"]} for i, r in enumerate(ordered)],
            "tiedRanks": sorted({r["rank"] for r in rows if r["tied"]})}
