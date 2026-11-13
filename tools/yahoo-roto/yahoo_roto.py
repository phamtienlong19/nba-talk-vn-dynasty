#!/usr/bin/env python3
"""Roto standings for any PUBLICLY VIEWABLE Yahoo fantasy league, from its league id. Standard library only, read-only, no sign-in.

    python3 yahoo_roto.py 85092                      # season roto: every week with data, categories read from the league's settings
    python3 yahoo_roto.py 85092 --week 3             # one week only
    python3 yahoo_roto.py 85092 --through 3 --json   # weeks 1-3, machine-readable
    python3 yahoo_roto.py 85092 --cache .cache       # keep fetched pages: finished weeks are never fetched twice

How it works: the league's public settings page gives the scoring type and the categories; the standings page gives the teams; each team's
weekly matchup page ("totals" view) gives that week's category totals for it and its opponent. Season roto adds the weekly totals and ranks
the teams in every category (worst = 1 point, best = number of teams; level teams share the average place; fewer is better for TO / PF).
Percentage categories are computed from the summed makes and attempts, never by averaging percentages.

Limits, stated plainly: a league has to be viewable without a login (Yahoo's "Make League Publicly Viewable"). Counting categories and made/attempted
percentages are supported (points, rebounds, FG%, FT% ...); ratio categories such as ERA/WHIP are reported and skipped. The league is read as
head-to-head weekly pages, so a pure-roto league (no weekly matchups) is detected and refused rather than guessed. Roto here is derived and
display-only: it is not a Yahoo number. Be polite: one request per 1.5 s by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from fractions import Fraction
from html.parser import HTMLParser

BASE = "https://basketball.fantasysports.yahoo.com/nba/{league}"
SPORTS = {"nba": "basketball.fantasysports.yahoo.com/nba", "nfl": "football.fantasysports.yahoo.com/f1", "mlb": "baseball.fantasysports.yahoo.com/b1",
          "nhl": "hockey.fantasysports.yahoo.com/hockey"}
LOWER_IS_BETTER = {"TO", "PF", "DQ", "GA", "GAA", "ERA", "WHIP", "BB"}
UA = "yahoo-roto/1.0 (read-only; public pages)"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class RotoError(RuntimeError):
    pass


# ------------------------------------------------------------------ fetching
class Fetcher:
    def __init__(self, delay=1.5, cache=None, out=print):
        self.delay, self.cache, self.out, self.last = delay, cache, out, 0.0
        if cache:
            os.makedirs(cache, exist_ok=True)

    def get(self, url, keep=False):
        path = os.path.join(self.cache, hashlib.sha1(url.encode()).hexdigest() + ".html") if self.cache and keep else None
        if path and os.path.exists(path):
            return open(path, encoding="utf-8").read()
        wait = self.delay - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body, final = r.read().decode("utf-8", "replace"), r.geturl()
        except urllib.error.HTTPError as e:
            raise RotoError("%s answered HTTP %s" % (url, e.code))
        except urllib.error.URLError as e:
            raise RotoError("could not reach %s (%s)" % (url, e.reason))
        finally:
            self.last = time.time()
        if "login.yahoo.com" in final or "/login" in final.split("?")[0]:
            raise RotoError("this league is not publicly viewable (Yahoo asked for a sign-in). Only public leagues can be read; "
                            "a commissioner can turn on 'Make League Publicly Viewable' in the league settings.")
        if path and keep:
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
        return body


# ------------------------------------------------------------------ a tiny element tree
class El:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.parent = tag, dict(attrs), [], parent

    def text(self):
        out = []

        def walk(e):
            for k in e.kids:
                out.append(k) if isinstance(k, str) else walk(k)
        walk(self)
        return re.sub(r"\s+", " ", "".join(out)).strip()

    def find_all(self, pred):
        res = []

        def walk(e):
            for k in e.kids:
                if isinstance(k, El):
                    if pred(k):
                        res.append(k)
                    walk(k)
        walk(self)
        return res


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = El("root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        el = El(tag, [(k, v or "") for k, v in attrs], self.cur)
        self.cur.kids.append(el)
        if tag not in VOID:
            self.cur = el

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(El(tag, [(k, v or "") for k, v in attrs], self.cur))

    def handle_endtag(self, tag):
        e = self.cur
        while e is not None and e.tag != tag:
            e = e.parent
        if e is not None and e.parent is not None:
            self.cur = e.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def parse_tree(html):
    t = _Tree()
    t.feed(html)
    t.close()
    return t.root


def page_text(html):
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&nbsp;", " ")


# ------------------------------------------------------------------ settings, teams, weekly totals
def parse_settings(html):
    """-> {"scoring": "Head-to-Head - Categories" | ..., "categories": ["FG%", ...], "public": bool|None}"""
    t = page_text(html)
    m = re.search(r"Scoring Type:\s*(.+?)\s+(?:Max Acquisitions|Max Trades|Trade End|Allow|Waiver|Roster)", t)
    c = re.search(r"Stat Categories:\s*(.+?)\s+(?:Stat Modifiers|Roster Positions|Max |Minimum|Games|Lineup|League|Waiver|Trade)", t)
    cats = re.findall(r"\(([A-Z0-9%/+\-]+)\)", c.group(1)) if c else []
    pub = re.search(r"Make League Publicly Viewable:\s*(Yes|No)", t)
    return {"scoring": m.group(1).strip() if m else None, "categories": cats, "public": (pub.group(1) == "Yes") if pub else None}


def parse_teams(html, league):
    """-> {teamId: name} from the standings page (the rows of any table that has a Team column)."""
    out = {}
    for tb in parse_tree(html).find_all(lambda e: e.tag == "table"):
        heads = [th.text() for th in tb.find_all(lambda e: e.tag == "th")]
        if "Team" not in heads:
            continue
        for a in tb.find_all(lambda e: e.tag == "a" and re.search(r"/%s/(\d+)/?$" % re.escape(str(league)), e.attrs.get("href", "")) and e.text()):
            out.setdefault(int(re.search(r"/(\d+)/?$", a.attrs["href"]).group(1)), a.text())
    return out


def _num(s):
    s = (s or "").strip().replace(",", "")
    if s in ("", "-", "--"):
        return None
    try:
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None


def _made_att(s):
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_week(html, league):
    """One matchup page (totals view) -> {"week": n, "weeks": [...], "teams": {teamId: {"name", "cols": {header: value}}}}.
    A made/attempted column ("FGM/A*") is kept as a (made, att) pair; every other column as an exact number, None when Yahoo shows '-'."""
    root = parse_tree(html)
    week, weeks = None, []
    for o in root.find_all(lambda e: e.tag == "option"):
        m = re.search(r"[?&]week=(\d+)", o.attrs.get("value", ""))
        if m and "module=matchup" in o.attrs.get("value", ""):
            weeks.append(int(m.group(1)))
            if "selected" in o.attrs:
                week = int(m.group(1))
    for tb in root.find_all(lambda e: e.tag == "table"):
        heads = [th.text() for th in tb.find_all(lambda e: e.tag == "th")]
        if "Team" not in heads or not any(h.endswith("M/A*") for h in heads):
            continue
        teams = {}
        for tr in tb.find_all(lambda e: e.tag == "tr"):
            tds = [c for c in tr.kids if isinstance(c, El) and c.tag == "td"]
            if not tds:
                continue
            link = [a for a in tds[0].find_all(lambda e: e.tag == "a") if re.search(r"/%s/(\d+)" % re.escape(str(league)), e_href(a))]
            if not link:
                continue
            tid = int(re.search(r"/%s/(\d+)" % re.escape(str(league)), e_href(link[0])).group(1))
            name = next((a.text() for a in link if a.text()), "")
            cols = {}
            for h, td in zip(heads[1:], tds[1:]):
                if h:
                    cols[h] = _made_att(td.text()) if h.endswith("M/A*") else _num(td.text())
            teams[tid] = {"name": name, "cols": cols}
        if teams:
            return {"week": week, "weeks": sorted(set(weeks)), "teams": teams}
    raise RotoError("no matchup table found on the page (is this a head-to-head league with matchups?)")


def e_href(a):
    return a.attrs.get("href", "")


# ------------------------------------------------------------------ categories and roto math
def plan(categories, headers):
    """Decide, for each scoring category, how to compute it from the matchup columns.
    -> ([{"cat", "kind": "count"|"pct", "col", "num"/"den" cols, "lower"}], [skipped categories])"""
    out, skipped = [], []
    hs = [h for h in headers if h]
    for cat in categories:
        if cat in hs and not cat.endswith("M/A*"):
            if cat.endswith("%"):
                i = hs.index(cat)
                if i > 0 and hs[i - 1].endswith("M/A*"):
                    out.append({"cat": cat, "kind": "pct", "col": hs[i - 1], "lower": cat in LOWER_IS_BETTER})
                else:
                    skipped.append(cat)
            elif cat in ("ERA", "WHIP", "AVG", "OBP", "SLG", "OPS", "K/9", "SV+H"):
                skipped.append(cat)
            else:
                out.append({"cat": cat, "kind": "count", "col": cat, "lower": cat in LOWER_IS_BETTER})
        else:
            skipped.append(cat)
    return out, skipped


def add(a, b):
    if a is None or b is None:
        return None
    return (a[0] + b[0], a[1] + b[1]) if isinstance(a, tuple) else a + b


def totals(weeks_data, teams):
    """Sum the weekly columns per team over the weeks given: {teamId: {col: value}}. A week where a team has no value for a column adds nothing."""
    tot = {t: {} for t in teams}
    for wk in weeks_data:
        for tid, rec in wk["teams"].items():
            for h, v in rec["cols"].items():
                if v is None:
                    continue
                cur = tot.setdefault(tid, {}).get(h)
                tot[tid][h] = v if cur is None else add(cur, v)
    return tot


def cat_value(stats, spec):
    v = stats.get(spec["col"])
    if v is None:
        return None
    if spec["kind"] == "pct":
        return Fraction(v[0], v[1]) if v[1] else None
    return v


def places(values, lower):
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=lower)
    out, i = {}, 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in order[i:j + 1]:
            out[k] = (i + 1 + j + 1) / 2
        i = j + 1
    return out


def roto(stats_by_team, specs):
    ids = sorted(stats_by_team)
    res = {t: {"points": {}, "total": 0.0} for t in ids}
    for sp in specs:
        vals = [cat_value(stats_by_team[t], sp) for t in ids]
        if any(v is None for v in vals):
            for t in ids:
                res[t]["points"][sp["cat"]] = None
            continue
        for k, p in places(vals, sp["lower"]).items():
            res[ids[k]]["points"][sp["cat"]] = p
            res[ids[k]]["total"] += p
    ranked = sorted(ids, key=lambda t: -res[t]["total"])
    for t in ids:
        res[t]["rank"] = 1 + sum(1 for o in ids if res[o]["total"] > res[t]["total"])
    return res, ranked


# ------------------------------------------------------------------ the run
def collect_week(fx, league, week, team_ids, base):
    """All teams' totals for one week, walking only as many matchup pages as needed (each page covers two teams)."""
    got, parsed = {}, None
    for tid in team_ids:
        if tid in got:
            continue
        html = fx.get("%s/matchup?date=totals&week=%d&mid1=%d" % (base, week, tid), keep=True)
        parsed = parse_week(html, league)
        if parsed["week"] not in (None, week):
            raise RotoError("asked for week %d but Yahoo showed week %s" % (week, parsed["week"]))
        got.update(parsed["teams"])
    return {"week": week, "teams": got}


def has_data(wk):
    return any(v is not None for rec in wk["teams"].values() for v in rec["cols"].values())


def run(league, week=None, through=None, cache=None, delay=1.5, sport="nba", out=print):
    base = "https://%s/%s" % (SPORTS[sport], league)
    fx = Fetcher(delay=delay, cache=cache)
    page = fx.get(base + "/settings")
    st = parse_settings(page)
    if st["scoring"] is None and not st["categories"]:
        raise RotoError("could not read league %s's public settings: it does not exist or it is not publicly viewable (Yahoo shows a generic "
                        "error page). Only public leagues can be read; a commissioner can turn on 'Make League Publicly Viewable' in the settings." % league)
    if st["scoring"] and "Head-to-Head" not in st["scoring"]:
        raise RotoError("this league's scoring type is %r; only head-to-head leagues (weekly matchup pages) are supported" % st["scoring"])
    teams = parse_teams(fx.get(base + "?lhst=stand"), league)
    if len(teams) < 2:
        raise RotoError("could not read the teams from the standings page")
    first = parse_week(fx.get("%s/matchup?date=totals&week=1&mid1=%d" % (base, sorted(teams)[0]), keep=True), league)
    all_weeks = first["weeks"] or [1]
    last = through or max(all_weeks)
    wanted = [week] if week else [w for w in all_weeks if w <= last]
    weeks_data = []
    for w in wanted:
        wk = collect_week(fx, league, w, sorted(teams), base)
        if has_data(wk):
            weeks_data.append(wk)
        elif week:
            raise RotoError("week %d has no stats yet" % week)
    if not weeks_data:
        raise RotoError("no week with stats yet")
    headers = list(next(iter(weeks_data[0]["teams"].values()))["cols"])
    cats = st["categories"] or [h for h in headers if h and not h.endswith("M/A*")]
    specs, skipped = plan(cats, headers)
    if not specs:
        raise RotoError("none of the league's categories (%s) can be computed from the matchup pages" % ", ".join(cats))
    tot = totals(weeks_data, teams)
    res, ranked = roto(tot, specs)
    names = {t: teams.get(t) or next((wk["teams"][t]["name"] for wk in weeks_data if t in wk["teams"]), str(t)) for t in tot}
    return {"league": str(league), "scoring": st["scoring"], "weeks": [w["week"] for w in weeks_data], "categories": [s["cat"] for s in specs],
            "skipped": skipped, "teams": [{"teamId": t, "name": names[t], "rank": res[t]["rank"], "total": res[t]["total"], "points": res[t]["points"],
                                           "values": {s["cat"]: _plain(cat_value(tot[t], s)) for s in specs}} for t in ranked]}


def _plain(v):
    return None if v is None else (float(v) if v.denominator != 1 else int(v))


def render(doc):
    cats = doc["categories"]
    wk = doc["weeks"]
    lines = ["League %s · %s · weeks %s" % (doc["league"], doc["scoring"] or "?", ("%d-%d" % (wk[0], wk[-1])) if len(wk) > 1 else wk[0])]
    if doc["skipped"]:
        lines.append("skipped (not computable from matchup pages): " + ", ".join(doc["skipped"]))
    w = max(len(t["name"]) for t in doc["teams"])
    lines.append("%3s  %-*s  %6s  " % ("#", w, "Team", "ROTO") + " ".join("%6s" % c for c in cats))
    for t in doc["teams"]:
        lines.append("%3d  %-*s  %6.1f  " % (t["rank"], w, t["name"], t["total"]) + " ".join("%6s" % (("%g" % t["points"][c]) if t["points"][c] is not None else "-") for c in cats))
    lines.append("")
    lines.append("category totals")
    lines.append("%-*s  " % (w, "Team") + " ".join("%8s" % c for c in cats))
    for t in doc["teams"]:
        lines.append("%-*s  " % (w, t["name"]) + " ".join("%8s" % (_fmt(c, t["values"][c])) for c in cats))
    return "\n".join(lines)


def _fmt(cat, v):
    if v is None:
        return "-"
    return ("%.3f" % v).lstrip("0") if cat.endswith("%") else ("%g" % v)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("league", help="the Yahoo league id (the number in the league's URL)")
    ap.add_argument("--week", type=int, help="one week only")
    ap.add_argument("--through", type=int, help="season roto through this week")
    ap.add_argument("--sport", default="nba", choices=sorted(SPORTS), help="default nba (categories and pages are verified for NBA only)")
    ap.add_argument("--cache", help="directory to keep fetched pages in")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests (default 1.5)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        doc = run(a.league, a.week, a.through, a.cache, a.delay, a.sport)
    except RotoError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(doc, indent=1, ensure_ascii=False) if a.json else render(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
