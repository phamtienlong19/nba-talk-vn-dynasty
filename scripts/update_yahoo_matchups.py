#!/usr/bin/env python3
"""Capture finished weekly matchup results from Yahoo's public matchup pages (no sign-in, no cookies, read-only GETs).

    python3 scripts/update_yahoo_matchups.py                 # dry run: every finished week not yet stored, report only
    python3 scripts/update_yahoo_matchups.py --apply         # write data/2026-27/matchups/week-NN.json for READY weeks
    python3 scripts/update_yahoo_matchups.py --weeks 1 2     # only these weeks
    python3 scripts/update_yahoo_matchups.py --schedule [--apply]   # the pairings of every regular-season week (data/2026-27/schedule.json, no stats)

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
import yahoo_schedule as sched  # noqa: E402


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
    try:
        return ym.parse_matchup_html(body, cfg)
    except ym.MatchupError as e:
        import re
        title = re.search(r"<title[^>]*>(.*?)</title>", body or "", re.S | re.I)
        raise ym.MatchupError(e.code, "%s [GET %s -> %s, %s bytes, title %r]" % (
            e, url, _final, len(body or ""), (title.group(1).strip()[:80] if title else None)))


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def current_week(cfg, fetcher=None) -> int:
    """The league week now, counted from the season's first Monday (Pacific). Yahoo's no-week matchup page needs a sign-in
    (anonymous it serves a page without the stats table), so the week is derived, then read back from a real week page."""
    from zoneinfo import ZoneInfo
    start = datetime.date.fromisoformat(cfg["seasonStartMonday"])
    today = _now().astimezone(ZoneInfo("America/Los_Angeles")).date()
    return max(1, min(20, (today - start).days // 7 + 1))


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


def run_schedule(cfg, fetcher, apply=False, matchup_dir=ym.MATCHUP_DIR, path=sched.SCHEDULE_PATH, sleep=time.sleep, out=print) -> int:
    """Pairings for the regular-season weeks (the playoff weeks are seeded from the standings, so Yahoo lists no opponent): finished weeks from the stored results, the rest from the kept schedule or, if missing, one page walk
    per week (8 requests). A kept pairing that a fresh walk would contradict is not touched here (only weeks never captured are walked)."""
    stored, kept = ym.load_weeks(matchup_dir), sched.load(path)
    by_week, walked = {}, 0
    for w in range(1, sched.regular_weeks(cfg) + 1):
        if w in stored:
            by_week[w] = sched.pairs(stored[w])
        elif w in kept:
            by_week[w] = kept[w]
        else:
            try:
                by_week[w] = sched.pairs(walk_week(cfg, w, fetcher, sleep=sleep))
            except ym.MatchupError as e:
                out("week %s FAILED: %s" % (w, e))
                return 1
            walked += 1
            out("week %s walked" % w)
    bad = sched.check(by_week, cfg)
    if bad:
        out("schedule NOT written: " + "; ".join(bad))
        return 1
    same = {w: by_week[w] for w in kept} == kept and len(kept) == len(by_week)
    out("schedule %s (%d weeks, %d walked)" % ("NO_CHANGE" if same else "READY", len(by_week), walked))
    if apply and not same:
        out("  wrote " + os.path.relpath(sched.commit(sched.build(by_week, cfg, _utc()), path), ym.ROOT))
    return 0


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weeks", type=int, nargs="*")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--schedule", action="store_true", help="capture the pairings of the regular-season weeks instead of finished results")
    args = ap.parse_args(argv)
    cfg = yr.load_config()
    if args.schedule:
        return run_schedule(cfg, fetcher or yr.HttpFetcher(), args.apply)
    return run(cfg, fetcher or yr.HttpFetcher(), args.weeks, args.apply)


if __name__ == "__main__":
    sys.exit(main())
