#!/usr/bin/env python3
"""Capture finished weekly matchup results from Yahoo's public matchup pages (no sign-in, no cookies, read-only GETs).

    python3 scripts/update_yahoo_matchups.py                 # dry run: every finished week not yet stored, report only
    python3 scripts/update_yahoo_matchups.py --apply         # write data/2026-27/matchups/week-NN.json for READY weeks
    python3 scripts/update_yahoo_matchups.py --weeks 1 2     # only these weeks

Pairings are not listed on any page, so a week is learned by walking team ids: fetch the lowest unseen team's matchup, read both
teams from it, mark both seen (8 requests per week). Only weeks before the current week are official; the current week is the live
feed's business (docs/LIVE_DATA.md). A stored week is never overwritten: a capture that differs is a CONFLICT (stat corrections need
a human). Display data only: nothing here touches rosters, salaries, the Trade Lab, the draft or the ledger.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402


def url_for(cfg, week=None, team_id=None):
    base = cfg["matchupUrl"].format(leagueId=cfg["leagueId"], week="{week}", teamId="{teamId}")
    if week is None:
        return base.split("?")[0]                                                  # the default page: the current week
    return base.format(week=week, teamId=team_id)


def fetch_page(cfg, fetcher, url, retries=2, sleep=time.sleep):
    """One GET; a non-200 is retried (Yahoo answers an occasional stray 404/5xx that is fine a moment later)."""
    status, _final, body = fetcher.get(url)
    for n in range(retries):
        if status == 200:
            break
        sleep(2 * (n + 1))
        status, _final, body = fetcher.get(url)
    if status != 200:
        raise ym.MatchupError("HTTP_%s" % status, "%s answered %s" % (url, status))
    return ym.parse_matchup_html(body, cfg)


def current_week(cfg, fetcher) -> int:
    return fetch_page(cfg, fetcher, url_for(cfg))["week"]


def walk_week(cfg, week, fetcher, delay=None, sleep=time.sleep) -> list:
    """The matchup pages of one week, one per pairing. Stops with an error if a team is missing or the pairing is inconsistent."""
    delay = cfg.get("requestDelaySeconds", 1.5) if delay is None else delay
    seen, pages = set(), []
    for tid in cfg["teamIds"]:
        if tid in seen:
            continue
        if pages:
            sleep(delay)
        p = fetch_page(cfg, fetcher, url_for(cfg, week, tid))
        got = {t["teamId"] for t in p["teams"]}
        if tid not in got or got & seen:
            raise ym.MatchupError("PAIRING", "week %s: the page for team %s shows teams %s" % (week, tid, sorted(got)))
        seen |= got
        pages.append(p)
    return pages


def _utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cfg, fetcher, weeks=None, apply=False, matchup_dir=ym.MATCHUP_DIR, sleep=time.sleep, out=print) -> int:
    cur = current_week(cfg, fetcher)
    stored = ym.load_weeks(matchup_dir)
    todo = weeks or [w for w in range(1, cur) if w not in stored]
    out("current week %s; stored %s; to capture %s" % (cur, sorted(stored) or "none", todo or "nothing"))
    bad = 0
    for w in todo:
        try:
            pages = walk_week(cfg, w, fetcher, sleep=sleep)
            doc = ym.build_week(pages, w, cfg, _utc(), "Yahoo public matchup pages, league %s" % cfg["leagueId"], cur)
        except ym.MatchupError as e:
            out("week %s FAILED: %s" % (w, e))
            bad += 1
            continue
        outcome = ym.classify(doc, stored.get(w))
        out("week %s %s (%d matchups)" % (w, outcome, len(doc["matchups"])))
        if outcome == "CONFLICT":
            bad += 1
        elif outcome == "READY" and apply:
            out("  wrote " + os.path.relpath(ym.commit_week(doc, matchup_dir), ym.ROOT))
    return 1 if bad else 0


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weeks", type=int, nargs="*")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    cfg = yr.load_config()
    return run(cfg, fetcher or yr.HttpFetcher(), args.weeks, args.apply)


if __name__ == "__main__":
    sys.exit(main())
