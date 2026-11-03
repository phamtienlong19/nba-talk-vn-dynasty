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
import update_yahoo_matchups as um  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
import yahoo_standings as ys  # noqa: E402

SCHEMA = "live-feed/1"
STARTING = ("PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util")
LINE_KEYS = ("fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to")         # the order managers know


def _utc(dt=None):
    return (dt or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _roster(rows, day=None):
    """`l` = the player's week line (starters only: Yahoo counts only starters); `d` = the line of the one day fetched, which is
    the only stat a benched or IL player has."""
    day = day or {}
    out = []
    for r in rows:
        if r["name"] is None:
            out.append({"s": r["slot"], "n": None})
            continue
        d = day.get(r.get("playerId") or r["name"])
        out.append({"s": r["slot"], "n": r["name"], "p": r.get("playerId"), "t": r.get("nba"), "pos": r.get("positions"),
                    "st": r.get("status") or "", "g": r.get("game"), "gs": ym.game_state(r.get("game")),
                    "l": [r["line"].get(k) for k in LINE_KEYS],
                    "d": [d["line"].get(k) for k in LINE_KEYS] if d else None, "ds": d["slot"] if d else None})
    return out


def _day_pages(cfg, cur, pages, fetcher, now_dt, sleep):
    """The roster view of one Yahoo day (US Pacific), for the bench and IL lines that the week totals leave out. The latest day with a
    game started: today, else yesterday if today has none yet. -> (date or None, {teamId: {key: row}}). Never fatal."""
    import zoneinfo
    start = datetime.date.fromisoformat(cfg["seasonStartMonday"]) + datetime.timedelta(days=7 * (cur - 1))
    today = now_dt.astimezone(zoneinfo.ZoneInfo("America/Los_Angeles")).date()
    for day in (today, today - datetime.timedelta(days=1)):
        if not start <= day <= start + datetime.timedelta(days=6):
            continue
        got, any_game = {}, False
        try:
            for p in pages:
                sleep(cfg.get("requestDelaySeconds", 1.5))
                tid = min(t["teamId"] for t in p["teams"])
                dp = um.fetch_page(cfg, fetcher, um.url_for(cfg, cur, tid).replace("date=totals", "date=" + day.isoformat()))
                for tm, rows in (dp.get("rosters") or {}).items():
                    got[tm] = {(r.get("playerId") or r["name"]): r for r in rows if r["name"] is not None}
                    any_game = any_game or any(ym.game_state(r.get("game")) in ("live", "final") for r in rows if r["name"] is not None)
        except (ym.MatchupError, yr.FetchError):
            return None, {}
        if any_game:
            return day.isoformat(), got
    return None, {}


def _to_play(rows):
    """Players in a starting slot whose game has not started or is in progress: what can still change today."""
    n = {"upcoming": 0, "live": 0}
    for r in rows:
        if r["name"] is not None and r["slot"] in STARTING and ym.game_state(r.get("game")) in n:
            n[ym.game_state(r["game"])] += 1
    return n


def _dt_of(iso):
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def build(cfg, fetcher, data_dir=ss.DATA_DIR, matchup_dir=ym.MATCHUP_DIR, now=None, sleep=time.sleep) -> dict:
    now = now or _utc()
    cur = um.current_week(cfg, fetcher)
    pages = um.walk_week(cfg, cur, fetcher, sleep=sleep)
    day_date, day = _day_pages(cfg, cur, pages, fetcher, _dt_of(now), sleep)
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
                          "toPlay": _to_play(rs), "roster": _roster(rs, day.get(t["teamId"]))})
        matchups.append({"teams": sides, "cats": res["cats"], "score": [res["a"], res["b"], res["t"]], "decided": res["decided"]})
    return {"schema": SCHEMA, "label": lst.LABEL, "asOf": now, "leagueId": str(cfg["leagueId"]), "week": cur, "dayDate": day_date,
            "weekStatus": "LIVE" if started else "NOT_STARTED", "finishedWeeks": sorted(finished), "notStoredYet": transient,
            "table": table, "playoff": {"spots": pic["spots"], "divisionTie": pic["divisionTie"], "linePct": pic["linePct"]},
            "projectedReverse": [{"team": fid(t["teamId"]), "tied": t["tied"]} for t in reversed(proj["teams"])],
            "tiedRanks": proj["tiedRanks"], "matchups": matchups}


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cfg = yr.load_config()
    try:
        doc = build(cfg, fetcher or yr.HttpFetcher())
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
