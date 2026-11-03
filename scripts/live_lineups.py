#!/usr/bin/env python3
"""Lineup-integrity EVIDENCE from closed Yahoo days (docs/LIVE_DATA.md, docs/LEAGUE_RULES_MODEL.md "AFK / lineup-integrity").

For each closed day of the week, each team's lineup is read from the `date=` roster page and checked for what the league rules count as a
misset. This is evidence for review, never a verdict:

  out_starter   a starting slot held by a player who is out, with no stats that day, while a healthy bench player eligible for the slot had a game
  empty_slot    a starting slot left empty while a healthy eligible bench player had a game
  star_benched  a star (top 50 by Yahoo's preseason O-Rank) on the bench, healthy, with a game

A status is what Yahoo showed when the day was captured (shortly after it closed); a late scratch can look like an out starter.
A closed day never changes, so each is captured once and carried in the feed for later runs (`previous`).
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_schedule as lsch  # noqa: E402
import update_yahoo_matchups as um  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

STARTING = ("PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util")
FITS = {"G": ("PG", "SG"), "F": ("SF", "PF"), "FC": ("SF", "PF", "C")}
STAR_RANK = 50
RULE = {"days": 2, "players": 3, "stars": 2}                 # AFK count: 2+ days or 3+ players misset in a week; 2 stars is enough


def eligible(slot, positions) -> bool:
    if slot == "Util":
        return True
    pos = set(positions or [])
    return slot in pos or bool(pos & set(FITS.get(slot, ())))


def _quiet(row) -> bool:
    return all(not v for v in (row.get("line") or {}).values())


def _healthy(row) -> bool:
    return row.get("status") not in lsch.OUT


def misses(rows, ranks) -> list:
    """The issues of one team on one closed day. rows = the roster rows of that day's page; ranks = {playerId: O-Rank}."""
    bench = [r for r in rows if r["slot"] == "BN" and r["name"] is not None and r.get("game") and _healthy(r)]
    used, out = set(), []
    for r in rows:
        if r["slot"] not in STARTING:
            continue
        gap = (r["name"] is None) or (r.get("status") in lsch.OUT and r.get("game") and _quiet(r))
        if not gap:
            continue
        rep = next((b for b in bench if id(b) not in used and eligible(r["slot"], b.get("positions"))), None)
        if rep is None:
            continue
        used.add(id(rep))
        out.append({"k": "empty_slot" if r["name"] is None else "out_starter", "p": r.get("name"), "id": r.get("playerId"), "s": r["slot"], "r": rep["name"]})
    for b in bench:
        rk = ranks.get(b.get("playerId"))
        if rk is not None and rk <= STAR_RANK:
            out.append({"k": "star_benched", "p": b["name"], "id": b.get("playerId"), "s": "BN", "r": None, "rank": rk})
    return out


def closed_dates(cfg, cur, now_dt) -> list:
    start = datetime.date.fromisoformat(cfg["seasonStartMonday"]) + datetime.timedelta(days=7 * (cur - 1))
    today = lsch.pacific_today(now_dt)
    return [d for d in (start + datetime.timedelta(days=i) for i in range(7)) if d < today]


def capture_day(cfg, cur, date, pages, fetcher, ranks, sleep=time.sleep) -> dict:
    """{teamId: [issues]} for one closed day (one request per pairing)."""
    out = {}
    for p in pages:
        sleep(cfg.get("requestDelaySeconds", 1.5))
        tid = min(t["teamId"] for t in p["teams"])
        dp = um.fetch_page(cfg, fetcher, um.url_for(cfg, cur, tid).replace("date=totals", "date=" + date.isoformat()))
        for team, rows in (dp.get("rosters") or {}).items():
            out[str(team)] = misses(rows, ranks)
    return out


def summarize(by_date, week) -> list:
    """Per team: the days with issues and the counts the league rule looks at."""
    teams = {}
    for date in sorted(by_date):
        for tid, issues in by_date[date].items():
            t = teams.setdefault(tid, {"yahooId": int(tid), "days": [], "_players": set(), "_stars": set()})
            if issues:
                t["days"].append({"date": date, "issues": issues})
                for i in issues:
                    key = i.get("id") or i.get("p")
                    t["_players"].add(key)
                    if i["k"] == "star_benched":
                        t["_stars"].add(key)
    rows = []
    for t in teams.values():
        players, stars = len(t.pop("_players")), len(t.pop("_stars"))
        t.update({"missetDays": len(t["days"]), "players": players, "stars": stars,
                  "meetsCount": len(t["days"]) >= RULE["days"] or players >= RULE["players"] or stars >= RULE["stars"]})
        rows.append(t)
    return rows


def checks(cfg, cur, pages, fetcher, now_dt, ranks, previous=None, sleep=time.sleep) -> dict:
    """The feed's `lineupChecks`. Days already in `previous` (the last published feed, same week) are reused, not fetched again."""
    prev = (previous or {}).get("lineupChecks") or {}
    by_date = dict(prev.get("byDate") or {}) if prev.get("week") == cur else {}
    missing = []
    for d in closed_dates(cfg, cur, now_dt):
        key = d.isoformat()
        if key in by_date:
            continue
        try:
            by_date[key] = capture_day(cfg, cur, d, pages, fetcher, ranks, sleep)
        except (ym.MatchupError, yr.FetchError):
            missing.append(key)
    return {"week": cur, "rule": RULE, "byDate": by_date, "missing": missing, "teams": summarize(by_date, cur)}


def load_ranks(path=None) -> dict:
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "yahoo", "player_registry.json")
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        players = doc.get("players", []) if isinstance(doc, dict) else doc
        return {str(p["playerId"]): p["oRank"] for p in players if isinstance(p, dict) and p.get("oRank") is not None}
    except (OSError, ValueError, KeyError, TypeError):
        return {}
