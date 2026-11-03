#!/usr/bin/env python3
"""Build the live feed (live.json): this week's matchups with 9-category scores and rosters, the standings if the week ended now,
the playoff picture and the projected reverse order. Provisional by construction; read-only against Yahoo's public pages.

    python3 scripts/build_live_feed.py --out live.json          # ~9 requests (current week) + 8 per finished week not yet stored

The feed never touches data/: finished weeks that are not stored yet are captured in memory only (the official copy goes through
scripts/update_yahoo_matchups.py and a PR). Anything inconsistent (a pairing that does not cover every team, a page that fails
validation) exits non-zero and writes nothing, so the previous feed stays up. Provisional numbers are labelled as such everywhere.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_rosters as ir  # noqa: E402
import live_standings as lst  # noqa: E402
import season_state as ss  # noqa: E402
import live_days as ldy  # noqa: E402
import live_lineups as lln  # noqa: E402
import live_schedule as lsch  # noqa: E402
import update_yahoo_matchups as um  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
import yahoo_standings as ys  # noqa: E402

SCHEMA = "live-feed/1"
STARTING = ("PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util")
LINE_KEYS = ("fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to")         # the order managers know


def _utc(dt=None):
    return (dt or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fix(pair):
    return [pair[0], pair[1]] if pair else None


def _roster(rows, day=None, sched=None, week=None, today_counts=False):
    """`l` = the player's week line from the matchup totals (starters only: Yahoo counts only starters); `wfg`/`wft` = his week made/attempted
    (starting days only); `d` = the line of the latest day with a started game, with its minutes and made/attempted (`dm`, `dfg`, `dft`) and the
    slot he held that day (`ds`): the only stat a benched or IL player has."""
    day, week = day or {}, week or {}
    out = []
    for r in rows:
        if r["name"] is None:
            out.append({"s": r["slot"], "n": None})
            continue
        pid = r.get("playerId")
        d = day.get(pid or r["name"])
        w = list(week.get(pid, [0, 0, 0, 0])) if pid else [0, 0, 0, 0]
        if d and today_counts and d["slot"] in ldy.STARTING:
            fg, ft = d.get("fg") or [0, 0], d.get("ft") or [0, 0]
            w = [w[0] + fg[0], w[1] + fg[1], w[2] + ft[0], w[3] + ft[1]]
        out.append({"s": r["slot"], "n": r["name"], "p": pid, "t": r.get("nba"), "pos": r.get("positions"),
                    "st": r.get("status") or "", "g": r.get("game"), "gs": ym.game_state(r.get("game")),
                    "l": [r["line"].get(k) for k in LINE_KEYS],
                    "wfg": [w[0], w[1]] if w[1] else None, "wft": [w[2], w[3]] if w[3] else None,
                    "d": [d["line"].get(k) for k in LINE_KEYS] if d else None, "ds": d["slot"] if d else None,
                    "dm": d.get("min") if d else None, "dfg": _fix(d.get("fg")) if d else None, "dft": _fix(d.get("ft")) if d else None,
                    "gl": lsch.games_left(r.get("nba"), ym.game_state(r.get("game")), sched) if sched and r.get("nba") else None})
    return out


def _day_choice(cfg, cur, pages, now_dt):
    """The Yahoo day (US Pacific) the day view shows: today once a game has started, else yesterday (inside the week), else none."""
    start = datetime.date.fromisoformat(cfg["seasonStartMonday"]) + datetime.timedelta(days=7 * (cur - 1))
    today = lsch.pacific_today(now_dt)
    started = any(ym.game_state(r.get("game")) in ("live", "final") for p in pages for rows in (p.get("rosters") or {}).values()
                  for r in rows if r["name"] is not None)
    for day, closed in ((today, False), (today - datetime.timedelta(days=1), True)):
        if day == today and not started:
            continue
        if start <= day <= start + datetime.timedelta(days=6):
            return day, today, closed
    return None, today, False


def _to_play(rows):
    """Players in a starting slot whose game has not started or is in progress: what can still change today."""
    n = {"upcoming": 0, "live": 0}
    for r in rows:
        if r["name"] is not None and r["slot"] in STARTING and ym.game_state(r.get("game")) in n:
            n[ym.game_state(r["game"])] += 1
    return n


def _games_left(rows, sched):
    """Games the starting lineup still has this week (players who are out are not counted); None when the schedule is unknown."""
    if not sched:
        return None
    return sum(lsch.games_left(r.get("nba"), ym.game_state(r.get("game")), sched) for r in rows
               if r["name"] is not None and r["slot"] in STARTING and r.get("status") not in lsch.OUT and r.get("nba"))


def _day_result(p, day_rows, day_date):
    """The matchup as played on the one day shown: category inputs and winners from the starters' lines (not Yahoo's number: Yahoo scores the week)."""
    if not day_date:
        return None
    a, b = (ldy.team_stats(day_rows.get(t["teamId"], [])) for t in p["teams"])
    res = ym.category_results(a, b)
    return {"date": day_date.isoformat(), "stats": [a, b], "cats": res["cats"], "score": [res["a"], res["b"], res["t"]]}


def _lineup_out(lineup, fid):
    if not lineup:
        return None
    return dict(lineup, teams=[dict(t, team=fid(t["yahooId"])) for t in lineup["teams"]])


def _dt_of(iso):
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def build(cfg, fetcher, data_dir=ss.DATA_DIR, matchup_dir=ym.MATCHUP_DIR, now=None, sleep=time.sleep, schedule_cache=None, previous=None, day_cache=None) -> dict:
    now = now or _utc()
    cur = um.current_week(cfg, fetcher)
    pages = um.walk_week(cfg, cur, fetcher, sleep=sleep)
    day_date, today, day_closed = _day_choice(cfg, cur, pages, _dt_of(now))
    days = ldy.Days(cfg, fetcher, sleep, day_cache)
    try:
        lineup, week_agg = ldy.closed_days(cfg, cur, _dt_of(now), lln.load_ranks(), days, previous)
    except OSError:
        lineup, week_agg = None, {"p": {}}                                          # evidence is a nicety: never fail the feed over it
    day_rows = {}
    if day_date:
        try:
            day_rows = days.rows(day_date, day_closed)
        except (ym.MatchupError, yr.FetchError, OSError):
            day_date, day_rows = None, {}
    try:
        sched = lsch.schedule(cfg, cur, pages, fetcher, _dt_of(now), schedule_cache, sleep)
    except OSError:
        sched = None                                                                # games left is a nicety: never fail the feed over it
    stored = ym.load_weeks(matchup_dir)
    finished, transient = {}, []
    for w in range(1, cur):
        if w in stored:
            finished[w] = stored[w]
        else:                                                                       # finished but not merged yet: in memory only
            sleep(cfg.get("requestDelaySeconds", 1.5))
            finished[w] = ym.build_week(um.walk_week(cfg, w, fetcher, sleep=sleep), w, cfg, now, "live feed (not stored)", cur)
            transient.append(w)
    team_map, _ = ir.load_maps(data_dir)
    fid = lambda tid: yr.franchise_for(cfg, team_map, tid)  # noqa: E731
    snap = ys.current_snapshot(os.path.join(data_dir, "standings"))
    divisions = {t["teamId"]: t["division"] for t in (snap or {}).get("teams", [])}
    official_order = [t["teamId"] for t in sorted((snap or {}).get("teams", []), key=lambda t: t["rank"])]
    official = lst.tally(finished)
    started = any(v is not None for p in pages for t in p["teams"] for v in t["stats"].values())
    live = lst.live_results(pages) if started else None
    rows = lst.table(official, live, divisions)
    pic = lst.playoff_picture(rows, cfg.get("playoffs"))
    proj = lst.projected_snapshot(rows, official_order)
    names = {t["teamId"]: t["name"] for p in pages for t in p["teams"]}
    table = []
    for r in rows:
        table.append({"team": fid(r["teamId"]), "yahooId": r["teamId"], "name": names.get(r["teamId"]), "w": r["w"], "l": r["l"], "t": r["t"],
                      "pct": r["pct"], "rank": r["rank"], "tied": r["tied"], "gb": r["gb"], "gbDivision": r["gbDivision"], "gbLine": pic["gbLine"].get(r["teamId"]), "division": r["division"],
                      "officialRank": r["officialRank"], "officialRecord": r["officialRecord"], "moved": r["moved"],
                      "playoff": pic["status"].get(r["teamId"]), "seed": pic["seeds"].get(r["teamId"])})
    matchups = []
    for p in sorted(pages, key=lambda p: min(t["teamId"] for t in p["teams"])):
        res = ym.matchup_result(p)
        sides = []
        for i, t in enumerate(p["teams"]):
            rs = p["rosters"][t["teamId"]] if p.get("rosters") else []
            sides.append({"team": fid(t["teamId"]), "yahooId": t["teamId"], "name": t["name"], "stats": t["stats"], "printed": t["printedWins"],
                          "toPlay": _to_play(rs), "gamesLeft": _games_left(rs, sched),
                          "roster": _roster(rs, {(r.get("playerId") or r["name"]): r for r in day_rows.get(t["teamId"], [])}, sched, week_agg.get("p"),
                                            bool(day_date) and not day_closed)})
        matchups.append({"teams": sides, "cats": res["cats"], "score": [res["a"], res["b"], res["t"]], "decided": res["decided"],
                         "day": _day_result(p, day_rows, day_date)})
    return {"schema": SCHEMA, "label": lst.LABEL, "asOf": now, "leagueId": str(cfg["leagueId"]), "week": cur, "dayDate": day_date.isoformat() if day_date else None, "playerWeek": {k: v for k, v in week_agg.items()} if week_agg.get("through") is not None else None, "lineupChecks": _lineup_out(lineup, fid), "gamesLeftComplete": bool(sched) and not sched["missing"], "lineKeys": list(LINE_KEYS),
            "weekStatus": "LIVE" if started else "NOT_STARTED", "finishedWeeks": sorted(finished), "notStoredYet": transient,
            "table": table, "playoff": {"spots": pic["spots"], "divisionTie": pic["divisionTie"], "linePct": pic["linePct"]},
            "projectedReverse": [{"team": fid(t["teamId"]), "tied": t["tied"]} for t in reversed(proj["teams"])],
            "tiedRanks": proj["tiedRanks"], "matchups": matchups}


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--previous", help="the last published feed: its closed-day lineup evidence is reused, not captured again")
    ap.add_argument("--day-cache", help="JSON file that keeps closed days' team pages between runs of a loop")
    ap.add_argument("--schedule-cache", help="JSON file that keeps the week's schedule between runs of a loop")
    args = ap.parse_args(argv)
    cfg = yr.load_config()
    try:
        previous = None
        if args.previous and os.path.exists(args.previous):
            try:
                with open(args.previous, encoding="utf-8") as f:
                    previous = json.load(f)
            except (OSError, ValueError):
                previous = None
        doc = build(cfg, fetcher or yr.HttpFetcher(), schedule_cache=args.schedule_cache, previous=previous, day_cache=args.day_cache)
    except (ym.MatchupError, yr.FetchError, OSError) as e:
        print("FAILED: %s (the previous feed stays up)" % e)
        return 1
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, args.out)
    print("live feed: week %s %s, %d matchups, %d bytes" % (doc["week"], doc["weekStatus"], len(doc["matchups"]), os.path.getsize(args.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
