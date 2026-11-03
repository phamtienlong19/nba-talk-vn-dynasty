#!/usr/bin/env python3
"""Games left this week, from Yahoo's own roster pages (no other source).

A roster page for a future day (`date=YYYY-MM-DD`) shows a game time and opponent for every player whose NBA team plays that day, so the
set of NBA teams playing on a day is read from a few pairings' pages (stopping once all 30 teams have been seen on some roster). The
schedule is fixed for the week, so a day is fetched once and kept in a small cache file that a looping run reuses; a day Yahoo cannot
serve is left out and the feed says the count is partial. Display data only.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_yahoo_matchups as um  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

ALL_TEAMS = 30
MAX_AGE_HOURS = 12
OUT = ("O", "INJ", "SUSP", "NA", "OFS")                       # a player who is not playing: his games do not count for the team


def pacific_today(now_dt):
    import zoneinfo
    return now_dt.astimezone(zoneinfo.ZoneInfo("America/Los_Angeles")).date()


def remaining_dates(cfg, cur, now_dt) -> list:
    """The days after today (Pacific) left in league week `cur`."""
    start = datetime.date.fromisoformat(cfg["seasonStartMonday"]) + datetime.timedelta(days=7 * (cur - 1))
    today = pacific_today(now_dt)
    return [d for d in (start + datetime.timedelta(days=i) for i in range(7)) if d > today]


def _load(path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, TypeError):
        return {}


def _save(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    os.replace(tmp, path)


def fetch_day(cfg, cur, date, pages, fetcher, sleep=time.sleep) -> dict:
    """{'plays': [NBA codes with a game], 'seen': [NBA codes on any roster]} for one day, from as few pairings as it takes."""
    plays, seen = set(), set()
    for p in pages:
        sleep(cfg.get("requestDelaySeconds", 1.5))
        tid = min(t["teamId"] for t in p["teams"])
        dp = um.fetch_page(cfg, fetcher, um.url_for(cfg, cur, tid).replace("date=totals", "date=" + date.isoformat()))
        for rows in (dp.get("rosters") or {}).values():
            for r in rows:
                if r["name"] is not None and r.get("nba"):
                    seen.add(r["nba"])
                    if r.get("game"):
                        plays.add(r["nba"])
        if len(seen) >= ALL_TEAMS:
            break
    return {"plays": sorted(plays), "seen": sorted(seen)}


def schedule(cfg, cur, pages, fetcher, now_dt, cache_path=None, sleep=time.sleep, now_iso=None) -> dict:
    """-> {'dates': {iso: set(NBA codes playing)}, 'missing': [iso, ...]} for the days after today."""
    cache = _load(cache_path) if cache_path else {}
    if cache.get("week") != cur:
        cache = {"week": cur, "days": {}}
    now_iso = now_iso or now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out, missing, changed = {}, [], False
    for d in remaining_dates(cfg, cur, now_dt):
        key = d.isoformat()
        hit = cache["days"].get(key)
        if hit:
            age = (now_dt - datetime.datetime.strptime(hit["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)).total_seconds() / 3600
            if age < MAX_AGE_HOURS:
                out[key] = set(hit["plays"])
                continue
        try:
            day = fetch_day(cfg, cur, d, pages, fetcher, sleep)
        except (ym.MatchupError, yr.FetchError):
            missing.append(key)
            continue
        cache["days"][key] = dict(day, at=now_iso)
        out[key] = set(day["plays"])
        changed = True
    if cache_path and changed:
        _save(cache_path, cache)
    return {"dates": out, "missing": missing}


def games_left(nba, today_game_state, sched) -> int:
    """Today's game if it has not finished, plus every later day this week on which his NBA team plays."""
    n = 1 if today_game_state in ("upcoming", "live") else 0
    return n + sum(1 for plays in sched["dates"].values() if nba in plays)
