#!/usr/bin/env python3
"""Yahoo head-to-head matchup pages: read one saved/fetched matchup page, validate it strictly and compute the 9-category result.

Read-only and display-only, like the standings and roster readers: HTML is parsed with `html.parser` and nothing in a page is
executed. Nothing here touches rosters, salaries, the Trade Lab, the draft or the ledger.

    parse_matchup_html(html, cfg)   -> {"week", "weeks", "teams": [2 x {teamId, name, stats, printedWins, marked}], "rosters"}
    category_results(a, b, cfg)     -> per-category winner ("a" | "b" | "t" | None) and each side's win count
    validate(parsed, cfg)           -> (blocking, warnings): Yahoo's printed category wins and highlighted cells must equal our math

A page for a week that has not started shows `-/-` and `-` everywhere: those are stored as null, never 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "yahoo_league.json")
# header text on the page -> stat key. FGM/A* and FTM/A* are "made/attempted"; the rest are plain counts or Yahoo's printed percentages.
HEADERS = {"FGM/A*": "fg", "FG%": "fgPct", "FTM/A*": "ft", "FT%": "ftPct", "3PTM": "tpm", "PTS": "pts", "REB": "reb",
           "AST": "ast", "ST": "st", "BLK": "blk", "TO": "to"}
# the nine scoring categories in Yahoo's column order; `lower` = fewer is better
CATEGORIES = (("fgPct", "FG%", False), ("ftPct", "FT%", False), ("tpm", "3PTM", False), ("pts", "PTS", False),
              ("reb", "REB", False), ("ast", "AST", False), ("st", "ST", False), ("blk", "BLK", False), ("to", "TO", True))
CAT_KEYS = tuple(c[0] for c in CATEGORIES)
VOID = ("void", "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr")


class MatchupError(RuntimeError):
    """A page that is not a readable matchup. `code` is stable (tests and reports key on it)."""

    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def load_config(path=CONFIG):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ a tiny element tree
class _El:
    __slots__ = ("tag", "attrs", "kids", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.parent = tag, dict(attrs), [], parent

    def cls(self):
        return (self.attrs.get("class") or "").split()

    def text(self):
        out = []

        def walk(e):
            for k in e.kids:
                if isinstance(k, str):
                    out.append(k)
                else:
                    walk(k)
        walk(self)
        return re.sub(r"\s+", " ", "".join(out)).strip()

    def find_all(self, pred):
        res = []

        def walk(e):
            for k in e.kids:
                if isinstance(k, _El):
                    if pred(k):
                        res.append(k)
                    walk(k)
        walk(self)
        return res


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _El("root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        el = _El(tag, [(k, v or "") for k, v in attrs], self.cur)
        self.cur.kids.append(el)
        if tag not in VOID:
            self.cur = el

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(_El(tag, [(k, v or "") for k, v in attrs], self.cur))

    def handle_endtag(self, tag):
        e = self.cur
        while e is not None and e.tag != tag:
            e = e.parent
        if e is not None and e.parent is not None:
            self.cur = e.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def _parse_tree(html):
    t = _Tree()
    t.feed(html)
    t.close()
    return t.root


# ------------------------------------------------------------------ cell values
def _num(s):
    s = (s or "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def _made_att(s):
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", s or "")
    return [int(m.group(1)), int(m.group(2))] if m else None


def _team_id(el, league_id):
    for a in el.find_all(lambda e: e.tag == "a" and e.attrs.get("href")):
        m = re.search(r"/nba/%s/(\d+)\b" % re.escape(str(league_id)), a.attrs["href"])
        if m:
            return int(m.group(1)), a.text()
    return None, None


# ------------------------------------------------------------------ parsing
def _header_table(root, league_id):
    for tb in root.find_all(lambda e: e.tag == "table"):
        heads = [th.text() for th in tb.find_all(lambda e: e.tag == "th")]
        if "FGM/A*" in heads and "Team" in heads:
            cols = [HEADERS.get(h) for h in heads]
            rows = []
            for tr in tb.find_all(lambda e: e.tag == "tr"):
                tds = [c for c in tr.kids if isinstance(c, _El) and c.tag == "td"]
                if not tds:
                    continue
                tid, name = _team_id(tds[0], league_id)
                if tid is None:
                    raise MatchupError("NO_TEAM", "a matchup row has no team link")
                stats, marked = {}, []
                for key, td in zip(cols[1:], tds[1:]):
                    if key is None:
                        continue
                    raw = td.text()
                    if key in ("fg", "ft"):
                        stats[key] = _made_att(raw)
                    else:
                        stats[key] = _num(raw)
                    if "Bg-selected" in td.attrs.get("class", ""):
                        marked.append(key)
                wins = _num(tds[len(cols) - 1].text()) if len(tds) >= len(cols) else None
                rows.append({"teamId": tid, "name": name, "stats": stats, "printedWins": wins, "marked": marked})
            return rows
    raise MatchupError("NO_TABLE", "no matchup table with Team and FGM/A* columns")


def _week(root):
    sel = root.find_all(lambda e: e.tag == "option")
    weeks = []
    chosen = None
    for o in sel:
        m = re.search(r"[?&]week=(\d+)", o.attrs.get("value", ""))
        if m and "module=matchup" in o.attrs.get("value", ""):
            n = int(m.group(1))
            weeks.append(n)
            if "selected" in o.attrs:
                chosen = n
    return chosen, weeks


_GAME_RE = re.compile(r"^(?:(?P<res>[WL]), ?(?P<a>\d+)-(?P<b>\d+) (?P<where>vs|@) (?P<opp>[A-Z]{2,3})|(?P<time>\d{1,2}:\d{2} ?[ap]m) (?P<where2>vs|@) (?P<opp2>[A-Z]{2,3}))$")


def _player(td):
    """One player cell: name, Yahoo player id, 'TEAM - POS,POS', injury status flag, game text. Empty slots have name None."""
    a = td.find_all(lambda e: e.tag == "a" and "name" in e.cls() and e.attrs.get("data-ys-playerid", e.attrs.get("href")))
    if not a:
        return {"name": None}
    link = a[0]
    pid = link.attrs.get("data-ys-playerid")
    if not pid:
        m = re.search(r"/players/(\d+)", link.attrs.get("href", ""))
        pid = m.group(1) if m else None
    status = ""
    for sp in td.find_all(lambda e: e.tag == "span" and "ysf-player-status" in e.cls()):
        status = sp.text()
    nba, pos = None, []
    for sp in td.find_all(lambda e: e.tag == "span" and "Fz-xxs" in e.cls() and " - " in e.text()):
        if "ysf-player-status" in sp.cls():
            continue
        left, right = sp.text().split(" - ", 1)
        nba, pos = left.strip(), [p for p in right.split(",") if p]
        break
    game = ""
    for sp in td.find_all(lambda e: e.tag == "span" and "ysf-game-status" in e.cls()):
        game = sp.text()
    return {"name": link.attrs.get("title") or link.text(), "playerId": pid, "nba": nba, "positions": pos, "status": status, "game": game or None}


def _half(tds, key_cols):
    """tds of one side: [pos(hidden), player, 9 stats, spacer]; the stat cells follow the roster header order FG% ... TO."""
    pos = tds[0].text()
    p = _player(tds[1])
    line = {k: (None if p["name"] is None else _num(td.text())) for k, td in zip(key_cols, tds[2:11])}
    p.update({"slot": pos, "line": line})
    return p


ROSTER_COLS = ("fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to")


def _rosters(root, team_ids):
    for tb in root.find_all(lambda e: e.tag == "table"):
        heads = [th.text() for th in tb.find_all(lambda e: e.tag == "th")]
        if heads.count("Player") == 2 and "Pos" in heads:
            out = {team_ids[0]: [], team_ids[1]: []}
            for tr in tb.find_all(lambda e: e.tag == "tr"):
                tds = [c for c in tr.kids if isinstance(c, _El) and c.tag == "td"]
                if not tds:
                    continue
                if len(tds) != 25:
                    raise MatchupError("ROSTER_SHAPE", "a roster row has %d cells, expected 25" % len(tds))
                for tid, part in ((team_ids[0], tds[0:12]), (team_ids[1], tds[13:25])):
                    p = _half(part, ROSTER_COLS)
                    if p["name"] is not None or p["slot"] not in ("",):
                        out[tid].append(p)
            return out
    return None


def parse_matchup_html(html: str, cfg: dict) -> dict:
    root = _parse_tree(html)
    league_id = cfg.get("leagueId")
    teams = _header_table(root, league_id)
    if len(teams) != 2:
        raise MatchupError("TEAMS", "expected two teams in the matchup table, found %d" % len(teams))
    week, weeks = _week(root)
    if week is None:
        raise MatchupError("NO_WEEK", "the page does not say which week it shows")
    ids = [t["teamId"] for t in teams]
    if ids[0] == ids[1]:
        raise MatchupError("TEAMS", "the same team appears on both sides")
    return {"leagueId": str(league_id), "week": week, "weeks": weeks, "teams": teams, "rosters": _rosters(root, ids)}


# ------------------------------------------------------------------ category math
def _pct(pair):
    return None if not pair or not pair[1] else pair[0] / pair[1]


def _value(stats, key):
    if key == "fgPct":
        return _pct(stats.get("fg"))
    if key == "ftPct":
        return _pct(stats.get("ft"))
    return stats.get(key)


def category_results(a: dict, b: dict) -> dict:
    """Winner of each of the nine categories for two stat dicts. None = not decidable yet (the week has no data, or no attempts)."""
    res, wa, wb = {}, 0, 0
    for key, _label, lower in CATEGORIES:
        x, y = _value(a, key), _value(b, key)
        if x is None or y is None:
            res[key] = None
            continue
        if x == y:
            res[key] = "t"
        elif (x < y) == lower:
            res[key] = "a"
            wa += 1
        else:
            res[key] = "b"
            wb += 1
    return {"cats": res, "a": wa, "b": wb, "t": sum(1 for v in res.values() if v == "t"), "decided": all(v is not None for v in res.values())}


def matchup_result(parsed: dict) -> dict:
    a, b = parsed["teams"]
    r = category_results(a["stats"], b["stats"])
    r["teams"] = [a["teamId"], b["teamId"]]
    return r


def validate(parsed: dict, cfg: dict | None = None) -> tuple:
    """Blocking problems reject the capture; warnings do not. Yahoo's own numbers are the reference: our math must reproduce them."""
    bad, warn = [], []
    a, b = parsed["teams"]
    res = category_results(a["stats"], b["stats"])
    started = res["decided"]
    if started:
        if (a["printedWins"], b["printedWins"]) != (res["a"], res["b"]):
            bad.append("printed category wins %s-%s differ from the computed %s-%s" % (a["printedWins"], b["printedWins"], res["a"], res["b"]))
        for side, t in (("a", a), ("b", b)):
            want = sorted(k for k, v in res["cats"].items() if v == side)
            if sorted(k for k in t["marked"] if k in CAT_KEYS) != want:
                warn.append("highlighted cells for team %s differ from the computed winners %s" % (t["teamId"], want))
    else:
        if (a["printedWins"] or 0) or (b["printedWins"] or 0):
            bad.append("a week with no stats prints category wins")
        if any(v for t in (a, b) for k, v in t["stats"].items() if v is not None and k not in ("fg", "ft") and v):
            warn.append("some categories have numbers while others are empty")
    if parsed.get("rosters") is None:
        warn.append("no roster table on the page")
    return bad, warn
