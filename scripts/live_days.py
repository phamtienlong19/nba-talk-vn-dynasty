#!/usr/bin/env python3
"""Day-level data for the live feed, from Yahoo team pages (`yahoo_teamday.py`): who started and what each player did on a day, with minutes and
made/attempted. One team-page request per team per day; a closed day never changes, so it is captured once (carried in the feed through the
run's `previous` document, and kept in a runner-local cache within a looping run). Display data only (docs/LIVE_DATA.md)."""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_lineups as lln  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
import yahoo_teamday as ytd  # noqa: E402

STARTING = lln.STARTING
COUNT_KEYS = ("tpm", "pts", "reb", "ast", "st", "blk", "to")


class Days:
    """Rows of each team on a day: {teamId: [rows]}. Closed days are cached (in memory and, when a path is given, on disk)."""

    def __init__(self, cfg, fetcher, sleep=time.sleep, cache_path=None):
        self.cfg, self.fetcher, self.sleep, self.path = cfg, fetcher, sleep, cache_path
        self.mem = self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError, TypeError):
            return {}

    def rows(self, date, closed) -> dict:
        key = date.isoformat()
        if closed and key in self.mem:
            return {int(t): r for t, r in self.mem[key].items()}
        out = {}
        for i, tid in enumerate(self.cfg["teamIds"]):
            self.sleep(self.cfg.get("requestDelaySeconds", 1.5))
            out[tid] = ytd.parse_team_day(self.fetcher_get(ytd.url_for(self.cfg, tid, key)))
        if closed:
            self.mem[key] = {str(t): r for t, r in out.items()}
            if self.path:
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.mem, f, separators=(",", ":"))
                os.replace(tmp, self.path)
        return out

    def fetcher_get(self, url):
        status, _final, body = self.fetcher.get(url)
        for n in range(2):
            if status == 200:
                break
            self.sleep(2 * (n + 1))
            status, _final, body = self.fetcher.get(url)
        if status != 200:
            raise ym.MatchupError("HTTP_%s" % status, "%s answered %s" % (url, status))
        return body


def starters(rows):
    return [r for r in rows if r["slot"] in STARTING]


def agg_add(agg, rows):
    """Add a day's starters to {playerId: [fgm, fga, ftm, fta]} (only starting slots count, as on Yahoo)."""
    for r in starters(rows):
        pid = r.get("playerId")
        if not pid:
            continue
        a = agg.setdefault(pid, [0, 0, 0, 0])
        fg, ft = r.get("fg") or [0, 0], r.get("ft") or [0, 0]
        a[0] += fg[0]
        a[1] += fg[1]
        a[2] += ft[0]
        a[3] += ft[1]


def team_stats(rows) -> dict:
    """The day's category inputs for one team: the starters' sums, in the shape of the matchup page's totals."""
    s = {"fg": [0, 0], "ft": [0, 0]}
    s.update({k: 0 for k in COUNT_KEYS})
    for r in starters(rows):
        for k in ("fg", "ft"):
            m = r.get(k)
            if m:
                s[k][0] += m[0]
                s[k][1] += m[1]
        for k in COUNT_KEYS:
            s[k] += (r.get("line") or {}).get(k) or 0
    return s


def roster_names(rows) -> dict:
    """{playerId: name} of everyone on a team's page that day (starters, bench and IL; empty slots have no player)."""
    return {r["playerId"]: r["name"] for r in rows if r.get("playerId") and r.get("name")}


def moves_between(before, after, date, rosters) -> list:
    """Adds and drops of each team between two days: [{date, team, add: [[id, name]], drop: [[id, name]]}], only teams that changed.
    `before` / `after` are {teamId: {playerId: name}}; a team missing from either side is skipped (no baseline, nothing to say)."""
    out = []
    for t in sorted(after):
        if t not in before:
            continue
        add = sorted(([i, n] for i, n in after[t].items() if i not in before[t]), key=lambda x: x[1])
        drop = sorted(([i, n] for i, n in before[t].items() if i not in after[t]), key=lambda x: x[1])
        if add or drop:
            out.append({"date": date, "team": int(t), "add": add, "drop": drop})
    return out


def closed_days(cfg, cur, now_dt, ranks, days, previous=None, today=None):
    """-> (lineupChecks, playerWeek). Every closed day of the week is captured once: its lineup issues (misses) and its starters' made/att.
    `playerWeek.moves` are the adds and drops between consecutive closed days (a feed built before it existed is backfilled from the day cache);
    `playerWeek.last` is the latest closed day's rosters, the baseline for the next day and for today."""
    prev_l = (previous or {}).get("lineupChecks") or {}
    prev_w = (previous or {}).get("playerWeek") or {}
    same = prev_w.get("week") == cur
    by_date = dict(prev_l.get("byDate") or {}) if prev_l.get("week") == cur else {}
    through = set(prev_w.get("through") or []) if same else set()
    p = {k: list(v) for k, v in (prev_w.get("p") or {}).items()} if same else {}
    moves = list(prev_w.get("moves") or []) if same and "moves" in prev_w else []
    last = prev_w.get("last") if same and "moves" in prev_w else None
    backfill = not (same and "moves" in prev_w)
    missing = []
    for d in lln.closed_dates(cfg, cur, now_dt):
        key = d.isoformat()
        if key in by_date and key in through and not backfill:
            continue
        try:
            rows = days.rows(d, True)
        except (ym.MatchupError, yr.FetchError):
            missing.append(key)
            continue
        if key not in by_date:
            by_date[key] = {str(t): lln.misses(r, ranks) for t, r in rows.items()}
        if key not in through:
            for r in rows.values():
                agg_add(p, r)
            through.add(key)
        names = {str(t): roster_names(r) for t, r in rows.items()}
        if last and last["date"] < key:
            moves += moves_between(last["teams"], names, key, rows)
        if not last or last["date"] < key:
            last = {"date": key, "teams": names}
    lineup = {"week": cur, "rule": lln.RULE, "byDate": by_date, "missing": missing, "teams": lln.summarize(by_date, cur)}
    return lineup, {"week": cur, "through": sorted(through), "p": p, "moves": moves, "last": last}


def today_moves(last, pages, date) -> list:
    """Adds and drops since the latest closed day, read from the matchup pages (the live rosters; players who only left are not on them)."""
    if not last or not date or last["date"] >= date:
        return []
    now = {}
    for pg in pages:
        for t, rows in (pg.get("rosters") or {}).items():
            now[str(t)] = roster_names([r for r in rows if r.get("slot") != "--"])
    return moves_between(last["teams"], now, date, None)
