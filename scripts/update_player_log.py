#!/usr/bin/env python3
"""Keep a day-by-day game log per player (`player_log.json`) from Yahoo's public team pages (no sign-in, no cookies, read-only GETs).

    python3 scripts/update_player_log.py --out player_log.json      # first run: every closed day of the season; after that only new days

One team-page request per team per day (16 x 1.5 s per day). The previous file is read from --out when it exists, so a run only fetches the days
it does not have; a day that fails is skipped and retried next run (never invented). The previous file stays in place unless something new was
captured. Display data only (docs/LIVE_DATA.md).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_days as ld  # noqa: E402
import live_schedule as lsch  # noqa: E402
import player_log as pl  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

MAX_NEW_DAYS = 45          # a safety stop per run (about 11 minutes); the next run carries on


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        return doc if pl.valid(doc) else pl.empty()
    except (OSError, ValueError):
        return pl.empty()


def run(cfg, fetcher, out_path, sleep=time.sleep, out=print, now=None) -> int:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    doc = load(out_path)
    days = ld.Days(cfg, fetcher, sleep=sleep)
    todo = [d for d in pl.closed_dates(cfg, lsch.pacific_today(now)) if d.isoformat() not in doc["days"]][:MAX_NEW_DAYS]
    added, failed = 0, []
    for d in todo:
        try:
            rows = days.rows(d, False)
        except (ym.MatchupError, yr.FetchError) as e:
            failed.append(d.isoformat())
            out("%s skipped: %s" % (d, e))
            continue
        n = pl.add_day(doc, d.isoformat(), rows)
        added += 1
        out("%s: %d lines" % (d, n))
    if not added:
        out("nothing new captured (%d days kept%s)" % (len(doc["days"]), ", %d failed" % len(failed) if failed else ""))
        return 1 if failed else 0
    doc["capturedAt"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_path)
    out("wrote %s (%d bytes, %d days)" % (out_path, os.path.getsize(out_path), len(doc["days"])))
    return 0


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    return run(yr.load_config(), fetcher or yr.HttpFetcher(), args.out)


if __name__ == "__main__":
    sys.exit(main())
