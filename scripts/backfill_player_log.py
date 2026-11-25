#!/usr/bin/env python3
"""Fill the holes of the game log: every game of every rostered player, whether or not a fantasy team held him that day.

    python3 scripts/backfill_player_log.py --days player_days.json --log player_log.json [--max-days 20]

`player_days.json` keeps every player's line for each closed day, from Yahoo's one-day player list (about 32 requests a day, 1.5 s apart, each day
fetched once). `player_log.json` then gains the missing lines of the players on a roster now (or already in the log), so a player picked up today
arrives with the whole season. Only days the team-page log already holds are taken, and each is checked against it: a day whose lines disagree is
refused (a changed page or an ignored date would otherwise publish wrong numbers). Run after scripts/update_player_log.py. A run takes at most
--max-days days; the next carries on. Display data only: nothing here touches rosters, salaries, the Trade Lab or the ledger."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import player_log as pl  # noqa: E402
import season_state as ss  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_player_days as ypd  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

MAX_DAYS = 20                # about 650 requests, under half an hour
MAX_PAGES = 45               # about 780 players are listed
MIN_PLAYERS = 500            # fewer than this and Yahoo served something else
CHECK_FROM, AGREE = 10, 0.9  # with this many lines in common, this share must be identical (Yahoo's later stat corrections explain the rest)


def walk_day(cfg, fetcher, date, sleep=time.sleep) -> list:
    rows, seen = [], set()
    for page in range(MAX_PAGES):
        sleep(cfg.get("requestDelaySeconds", 1.5))
        url = ypd.url_for(cfg, date, page * ypd.PAGE)
        status, _final, body = fetcher.get(url)
        for n in range(2):
            if status == 200:
                break
            sleep(2 * (n + 1))
            status, _final, body = fetcher.get(url)
        if status != 200:
            raise ym.MatchupError("HTTP_%s" % status, "%s answered %s" % (url, status))
        got = ypd.parse_page(body)
        if not got:
            if len(seen) < MIN_PLAYERS:
                raise ym.MatchupError("SHORT", "only %d players listed for %s" % (len(seen), date))
            return rows
        rows += [r for r in got if r["playerId"] not in seen]
        seen |= {r["playerId"] for r in got}
    raise ym.MatchupError("ENDLESS", "the list for %s did not end after %d pages" % (date, MAX_PAGES))


def rostered(data_dir=ss.DATA_DIR) -> set:
    """Yahoo ids of everyone on a roster in the current verified snapshot."""
    index = ss._load(os.path.join(data_dir, "rosters", "index.json"))
    snap = ss._load(os.path.join(data_dir, "rosters", index["current"]))
    return {r["playerKey"].split(".p.")[1] for rows in snap["teams"].values() for r in rows if ".p." in str(r.get("playerKey"))}


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        return doc if pl.valid(doc) else None
    except (OSError, ValueError):
        return None


def _write(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def run(cfg, fetcher, days_path, log_path, ids, max_days=MAX_DAYS, sleep=time.sleep, out=print, now=None) -> int:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    log = _load(log_path)
    if log is None:
        out("FAILED: no readable game log at %s (the team-page log runs first)" % log_path)
        return 1
    full = _load(days_path) or pl.empty()
    dropped = pl.prune(log)
    todo = [d for d in log["days"] if d not in full["days"]][:max(max_days, 0)]
    failed = []
    for date in todo:
        try:
            rows = walk_day(cfg, fetcher, date, sleep)
        except (ym.MatchupError, yr.FetchError) as e:
            failed.append(date)
            out("%s skipped: %s" % (date, e))
            continue
        total, same = pl.agreement(log, date, rows)
        if total >= CHECK_FROM and same < AGREE * total:
            failed.append(date)
            out("%s refused: only %d of %d lines match the team pages" % (date, same, total))
            continue
        n = pl.add_day(full, date, {0: rows})
        full["capturedAt"] = stamp
        _write(days_path, full)                                                        # kept day by day: a cut-off run loses nothing
        out("%s: %d players played (%d of %d lines checked against the team pages)" % (date, n, same, total))
    added = pl.fill(log, full, sorted(set(ids) | set(log["p"])))
    if added or dropped:
        log["capturedAt"] = stamp
        _write(log_path, log)
    left = len([d for d in log["days"] if d not in full["days"]])
    out("filled %d line(s); %d day(s) still to fetch%s" % (added, left, ", %d failed" % len(failed) if failed else ""))
    return 1 if failed else 0


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--max-days", type=int, default=MAX_DAYS)
    a = ap.parse_args(argv)
    return run(yr.load_config(), fetcher or yr.HttpFetcher(), a.days, a.log, rostered(), a.max_days)


if __name__ == "__main__":
    sys.exit(main())
