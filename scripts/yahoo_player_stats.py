#!/usr/bin/env python3
"""Yahoo's public player list (`/nba/<league>/players?status=T&stat1=<window>&count=<offset>`): per-player averages for a window.

Read-only and display-only, like the other Yahoo readers. Windows: this season (`S_AS_2026`), the last 7 / 14 / 30 days (`S_AL7`, `S_AL14`,
`S_AL30`) and the two previous seasons (`S_AS_2025`, `S_AS_2024`). A page lists 25 players; `count` is the offset. A player with no games in
a window shows dashes, stored as null (never 0).

    parse_page(html)            -> [{playerId, name, gp, min, fg, ft, tpm, pts, reb, ast, st, blk, to, ros, rank}]
    build(by_window, at)        -> the document published as player_stats.json
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo_matchups as ym  # noqa: E402

SCHEMA = "yahoo-player-stats/1"
PAGE = 25
WINDOWS = (("season", "S_AS_2026"), ("l7", "S_AL7"), ("l14", "S_AL14"), ("l30", "S_AL30"), ("y2025", "S_AS_2025"), ("y2024", "S_AS_2024"))
# the 16 value cells before the trailing spacer, in Yahoo's column order
COLS = ("gp", "preRank", "rank", "ros", "min", "fg", "fgPct", "ft", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to")
TAIL = len(COLS) + 1


def url_for(cfg, window, offset=0) -> str:
    return "https://basketball.fantasysports.yahoo.com/nba/%s/players?status=T&pos=P&sort=AR&sdir=1&stat1=%s&count=%d" % (cfg["leagueId"], window, offset)


def _minutes(s):
    m = re.fullmatch(r"\s*(\d+):(\d{2})\s*", s or "")
    return round(int(m.group(1)) + int(m.group(2)) / 60, 1) if m else None


def _pct(s):
    m = re.fullmatch(r"\s*(\d+)\s*%\s*", s or "")
    return int(m.group(1)) if m else None


def parse_page(html: str) -> list:
    """The player rows of one list page. A page that has no player table is an error; a page past the end has a table and no rows."""
    root = ym._parse_tree(html)
    out, found = [], False
    for tb in root.find_all(lambda e: e.tag == "table"):
        heads = [th.text() for th in tb.find_all(lambda e: e.tag == "th")]
        if "Players" not in heads or "GP*" not in heads:
            continue
        found = True
        if [h for h in heads if h][-1] != "TO":
            raise ym.MatchupError("COLUMNS", "the player table does not end with TO: %s" % heads[-4:])
        for tr in tb.find_all(lambda e: e.tag == "tr"):
            tds = [c for c in tr.kids if isinstance(c, ym._El) and c.tag == "td"]
            link = None
            for a in tr.find_all(lambda e: e.tag == "a" and "name" in e.cls() and e.attrs.get("data-ys-playerid")):
                link = a
                break
            if not link:
                continue
            if len(tds) < TAIL + 1:
                raise ym.MatchupError("ROW_SHAPE", "a player row has %d cells" % len(tds))
            v = [c.text() for c in tds[-TAIL:-1]]
            r = dict(zip(COLS, v))
            out.append({"playerId": link.attrs["data-ys-playerid"], "name": link.attrs.get("title") or link.text(), "gp": ym._num(r["gp"]),
                        "min": _minutes(r["min"]), "fgPct": ym._num(r["fgPct"]), "ftPct": ym._num(r["ftPct"]),
                        "tpm": ym._num(r["tpm"]), "pts": ym._num(r["pts"]), "reb": ym._num(r["reb"]), "ast": ym._num(r["ast"]),
                        "st": ym._num(r["st"]), "blk": ym._num(r["blk"]), "to": ym._num(r["to"]), "ros": _pct(r["ros"]), "rank": ym._num(r["rank"])})
        break
    if not found:
        raise ym.MatchupError("NO_TABLE", "no player table on the page")
    return out


# the keys kept per window and in this order; the file stores arrays (ids -> rows) to stay small
KEEP = ("gp", "min", "pts", "reb", "ast", "st", "blk", "tpm", "fgPct", "ftPct", "to")


def build(by_window: dict, at: str, source: str = "Yahoo public player lists") -> dict:
    """{windows: {key: {playerId: [values in KEEP order]}}, keys: KEEP}. A window that was not captured is simply absent."""
    wins = {}
    for key, rows in by_window.items():
        wins[key] = {r["playerId"]: [r[k] for k in KEEP] for r in rows}
    return {"schema": SCHEMA, "capturedAt": at, "source": source, "keys": list(KEEP), "windows": wins}
