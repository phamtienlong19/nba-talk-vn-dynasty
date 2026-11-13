#!/usr/bin/env python3
"""A day-by-day game log per player, from Yahoo's team pages (`yahoo_teamday.parse_team_day`). Only closed days; only rows where the player
played (minutes or a shot attempt); a closed day never changes, so each day is captured once and kept. Display data only: nothing here
touches rosters, salaries, the Trade Lab, the draft or the ledger (docs/LIVE_DATA.md).

    {"capturedAt": ..., "days": ["2026-11-02", ...],                       # the days already captured
     "p": {"6167": [[date, slot, opp, min, fgm, fga, ftm, fta, tpm, pts, reb, ast, st, blk, to, yahooTeamId], ...]}}   # newest last
"""
from __future__ import annotations

import datetime
import re

COLS = ("date", "slot", "opp", "min", "fgm", "fga", "ftm", "fta", "tpm", "pts", "reb", "ast", "st", "blk", "to", "team")
_OPP = re.compile(r"\d+-\d+\s+(.+)$")


def opponent(game):
    """'L, 118-125 vs TOR' -> 'vs TOR' (None when the page gave no game)."""
    m = _OPP.search(game or "")
    return m.group(1).strip() if m else None


def played(r) -> bool:
    return bool(r.get("min")) or bool(r.get("fg") and r["fg"][1])


def row_for(date, team_id, r):
    ln, fg, ft = r["line"], r.get("fg") or [0, 0], r.get("ft") or [0, 0]
    return [date, r["slot"], opponent(r.get("game")), r.get("min"), fg[0], fg[1], ft[0], ft[1],
            ln.get("tpm") or 0, ln.get("pts") or 0, ln.get("reb") or 0, ln.get("ast") or 0, ln.get("st") or 0, ln.get("blk") or 0, ln.get("to") or 0,
            int(team_id)]


def add_day(doc, date, rows_by_team):
    """Merge one closed day (`{teamId: [parse_team_day rows]}`) into the document. Idempotent: a day already kept is not added twice."""
    if date in doc["days"]:
        return 0
    n = 0
    for tid, rows in rows_by_team.items():
        for r in rows:
            if r.get("playerId") is None or not played(r):
                continue
            doc["p"].setdefault(str(r["playerId"]), []).append(row_for(date, tid, r))
            n += 1
    doc["days"] = sorted(doc["days"] + [date])
    return n


def empty():
    return {"capturedAt": None, "days": [], "p": {}}


def closed_dates(cfg, today):
    """Every date from the season's first Monday up to the day before `today` (Pacific)."""
    d = datetime.date.fromisoformat(cfg["seasonStartMonday"])
    out = []
    while d < today:
        out.append(d)
        d += datetime.timedelta(days=1)
    return out


def valid(doc) -> bool:
    if not isinstance(doc, dict) or not isinstance(doc.get("days"), list) or not isinstance(doc.get("p"), dict):
        return False
    return all(isinstance(v, list) and all(isinstance(r, list) and len(r) == len(COLS) for r in v) for v in doc["p"].values())
