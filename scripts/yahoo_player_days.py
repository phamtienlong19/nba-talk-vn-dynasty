#!/usr/bin/env python3
"""Yahoo's public player list for ONE day (`/nba/<league>/players?status=ALL&stat1=S_D&date=YYYY-MM-DD&count=<offset>`): every player's line that
day, whoever held them. Read-only, anonymous, display data only (docs/LIVE_DATA.md).

    parse_page(html) -> rows in the shape yahoo_teamday.parse_team_day returns (slot None: this list knows no fantasy lineup)

A page is accepted only if it is really a one-day view: a MIN* column and no player with more than one game (with a missing or ignored date Yahoo
serves season figures in the same table)."""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo_matchups as ym  # noqa: E402
import yahoo_teamday as ytd  # noqa: E402

PAGE = 25
_GAME = re.compile(r"[WL], \d+-\d+\s+(?:vs|@)\s*[A-Z]{2,4}")


def url_for(cfg, date, offset=0) -> str:
    return "https://basketball.fantasysports.yahoo.com/nba/%s/players?status=ALL&pos=P&sort=AR&sdir=1&stat1=S_D&date=%s&count=%d" % (cfg["leagueId"], date, offset)


def parse_page(html: str) -> list:
    """The players of one page. A page past the end has a table and no rows; anything that is not a one-day player table is an error."""
    root = ym._parse_tree(html)
    for tb in root.find_all(lambda e: e.tag == "table"):
        heads = [th.text().strip() for th in tb.find_all(lambda e: e.tag == "th")]
        if "Players" not in heads or "GP*" not in heads:
            continue
        if "MIN*" not in heads or [h for h in heads if h][-1] != "TO":
            raise ym.MatchupError("COLUMNS", "not a one-day player table: %s" % heads[-14:])
        out = []
        for tr in tb.find_all(lambda e: e.tag == "tr"):
            tds = [c for c in tr.kids if isinstance(c, ym._El) and c.tag == "td"]
            link = next((a for a in tr.find_all(lambda e: e.tag == "a" and "name" in e.cls() and e.attrs.get("data-ys-playerid"))), None)
            if link is None:
                continue
            if len(tds) < len(ytd.TAIL) + 5:
                raise ym.MatchupError("ROW_SHAPE", "a player row has %d cells" % len(tds))
            games = tds[-len(ytd.TAIL) - 4].text().strip()                                     # GP*, pre-season, current, % ros, then the line
            cells = {k: td.text().strip() for k, td in zip(ytd.TAIL, tds[-len(ytd.TAIL):])}
            game = next((m.group(0) for m in (_GAME.search(td.text()) for td in tds[:3]) if m), None)
            minutes = ytd._minutes(cells["min"])
            out.append({"slot": None, "playerId": link.attrs["data-ys-playerid"], "name": link.attrs.get("title") or link.text(), "game": game,
                        "min": minutes if minutes not in ("0", "0:00") else None, "fg": ym._made_att(cells["fg"]), "ft": ym._made_att(cells["ft"]),
                        "line": {k: ym._num(cells[k]) for k in ("fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to")}, "gp": games})
        for r in out:
            gp = ym._num(r.pop("gp"))
            if gp is not None and gp > 1:
                raise ym.MatchupError("NOT_A_DAY", "%s shows %s games: this is not a one-day view" % (r["name"], gp))
        return out
    raise ym.MatchupError("NO_TABLE", "no player table on the page")
