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


def closed_days(cfg, cur, now_dt, ranks, days, previous=None, today=None):
    """-> (lineupChecks, playerWeek). Every closed day of the week is captured once: its lineup issues (misses) and its starters' made/att."""
    prev_l = (previous or {}).get("lineupChecks") or {}
    prev_w = (previous or {}).get("playerWeek") or {}
    by_date = dict(prev_l.get("byDate") or {}) if prev_l.get("week") == cur else {}
    through = set(prev_w.get("through") or []) if prev_w.get("week") == cur else set()
    p = {k: list(v) for k, v in (prev_w.get("p") or {}).items()} if prev_w.get("week") == cur else {}
    missing = []
    for d in lln.closed_dates(cfg, cur, now_dt):
        key = d.isoformat()
        if key in by_date and key in through:
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
    lineup = {"week": cur, "rule": lln.RULE, "byDate": by_date, "missing": missing, "teams": lln.summarize(by_date, cur)}
    return lineup, {"week": cur, "through": sorted(through), "p": p}
