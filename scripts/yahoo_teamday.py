#!/usr/bin/env python3
"""One Yahoo team page for one day (`/nba/<league>/<team>?date=YYYY-MM-DD&stat1=S&stat2=D`): each player's slot that day and the day's line with
minutes and made/attempted, which the matchup page does not carry. Read-only, display data only (docs/LIVE_DATA.md)."""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo_matchups as ym  # noqa: E402

TAIL = ("min", "fg", "fgPct", "ft", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to", "")      # the last 13 cells of a player row
HEAD_TAIL = ("MIN*", "FGM/A*", "FG%", "FTM/A*", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO")


def _minutes(s):
    m = re.fullmatch(r"\s*(\d+):(\d{2})\s*", s or "")
    return "%d:%s" % (int(m.group(1)), m.group(2)) if m else None


def url_for(cfg, team_id, date) -> str:
    return cfg["pageUrl"].format(leagueId=cfg["leagueId"], teamId=int(team_id)) + "?date=%s&stat1=S&stat2=D" % date


def parse_team_day(html: str) -> list:
    """-> [{slot, playerId, name, nba, positions, status, game, min, fg:[m,a]|None, ft:[m,a]|None, line:{pct/count stats}}] for every filled slot."""
    root = ym._parse_tree(html)
    for tb in root.find_all(lambda e: e.tag == "table"):
        heads = [th.text().strip() for th in tb.find_all(lambda e: e.tag == "th")]
        if "FGM/A*" not in heads:
            continue
        tail = [h for h in heads if h][-len(HEAD_TAIL):]
        if tuple(tail) != HEAD_TAIL:
            raise ym.MatchupError("TEAM_SHAPE", "the stat columns are not the expected ones: %s" % tail)
        out = []
        for tr in tb.find_all(lambda e: e.tag == "tr"):
            tds = [c for c in tr.kids if isinstance(c, ym._El) and c.tag == "td"]
            if len(tds) < len(TAIL) + 2:
                continue
            p = ym._player(tds[1])
            if p["name"] is None:
                continue
            cells = {k: td.text().strip() for k, td in zip(TAIL, tds[-len(TAIL):])}
            out.append({"slot": tds[0].text().strip(), "playerId": p["playerId"], "name": p["name"], "nba": p["nba"], "positions": p["positions"],
                        "status": p["status"], "game": p["game"], "min": _minutes(cells["min"]),
                        "fg": ym._made_att(cells["fg"]), "ft": ym._made_att(cells["ft"]),
                        "line": {k: ym._num(cells[k]) for k in ("fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to")}})
        if not out:
            raise ym.MatchupError("NO_ROWS", "the team page has a stat table but no player rows")
        return out
    raise ym.MatchupError("NO_TABLE", "no roster table with FGM/A* columns")
