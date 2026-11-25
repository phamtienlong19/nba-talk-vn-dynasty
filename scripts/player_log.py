#!/usr/bin/env python3
"""A day-by-day game log per player, from Yahoo's team pages (`yahoo_teamday.parse_team_day`). Only closed days; only rows where the player
played (minutes or a shot attempt); a closed day never changes, so each day is captured once and kept. Display data only: nothing here
touches rosters, salaries, the Trade Lab, the draft or the ledger (docs/LIVE_DATA.md).

    {"capturedAt": ..., "days": ["2026-11-02", ...],                       # the days already captured
     "p": {"6167": [[date, slot, opp, min, fgm, fga, ftm, fta, tpm, pts, reb, ast, st, blk, to, yahooTeamId], ...]}}   # newest last

A team page only knows the players a fantasy team held that day. The other games of a rostered player come from Yahoo's one-day player list
(scripts/backfill_player_log.py) with slot null and team 0; a team-page line for the same day replaces such a line.
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


NO_TIME = (None, "", "0", "0:00")          # a team page prints 0 minutes for a player who sat out: not a game played


def played(r) -> bool:
    line = r.get("line") or {}
    return r.get("min") not in NO_TIME or bool(r.get("fg") and r["fg"][1]) or bool(r.get("ft") and r["ft"][1]) \
        or any(line.get(k) for k in ("tpm", "pts", "reb", "ast", "st", "blk", "to"))


def prune(doc) -> int:
    """Drop stored lines of games not played (kept by an earlier version: no minutes and nothing recorded). -> lines dropped."""
    n = 0
    for pid, rows in list(doc["p"].items()):
        keep = [r for r in rows if r[3] not in NO_TIME or any(r[4:15])]
        n += len(rows) - len(keep)
        if keep:
            doc["p"][pid] = keep
        else:
            del doc["p"][pid]
    return n


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
            have = doc["p"].setdefault(str(r["playerId"]), [])
            have[:] = [x for x in have if not (x[0] == date and x[1] is None)]     # the team page knows his lineup slot: it replaces a list line
            have.append(row_for(date, tid, r))
            have.sort(key=lambda x: x[0])
            n += 1
    doc["days"] = sorted(doc["days"] + [date])
    return n


def fill(doc, full, ids) -> int:
    """Add to `doc` the games of the players `ids` that `full` (every player, from the one-day list) has and `doc` lacks. -> lines added."""
    n = 0
    for pid in ids:
        rows = full["p"].get(str(pid))
        if not rows:
            continue
        have = doc["p"].setdefault(str(pid), [])
        dates = {x[0] for x in have}
        new = [r for r in rows if r[0] not in dates]
        if new:
            have.extend(new)
            have.sort(key=lambda x: x[0])
            n += len(new)
    return n


def agreement(doc, date, rows) -> tuple:
    """(lines compared, lines equal) between the team-page lines `doc` holds for a day and the one-day list's rows for it. Minutes are left out
    (the two pages round them differently)."""
    mine = {str(r["playerId"]): row_for(date, 0, r) for r in rows if r.get("playerId") is not None and played(r)}
    total = same = 0
    for pid, have in doc["p"].items():
        for x in have:
            if x[0] == date and x[1] is not None and pid in mine:
                total += 1
                same += x[4:15] == mine[pid][4:15]
    return total, same


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
