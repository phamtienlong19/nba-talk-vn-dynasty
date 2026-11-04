#!/usr/bin/env python3
"""Capture per-player averages for six windows from Yahoo's public player list (no sign-in, no cookies, read-only GETs).

    python3 scripts/update_yahoo_player_stats.py --out player_stats.json     # about 55 requests, 1.5 s apart

Taken players only (everyone on a fantasy roster): 25 a page, so about 9 pages a window. Nothing is written unless the season window is
complete enough to trust; the previous file stays in place on any failure. Display data only: nothing here touches rosters, salaries,
the Trade Lab, the draft or the ledger (docs/LIVE_DATA.md).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo_matchups as ym  # noqa: E402
import yahoo_player_stats as ps  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

MAX_PAGES = 14                  # a safety stop: 350 players is more than 16 rosters hold
MIN_PLAYERS = 150               # fewer than this in the season window means Yahoo served something else


def walk_window(cfg, fetcher, window, sleep=time.sleep) -> list:
    rows, seen = [], set()
    for page in range(MAX_PAGES):
        if page:
            sleep(cfg.get("requestDelaySeconds", 1.5))
        url = ps.url_for(cfg, window, page * ps.PAGE)
        status, _final, body = fetcher.get(url)
        for n in range(2):
            if status == 200:
                break
            sleep(2 * (n + 1))
            status, _final, body = fetcher.get(url)
        if status != 200:
            raise ym.MatchupError("HTTP_%s" % status, "%s answered %s" % (url, status))
        got = [r for r in ps.parse_page(body) if r["playerId"] not in seen]
        if not got:
            break
        seen |= {r["playerId"] for r in got}
        rows += got
    return rows


def run(cfg, fetcher, out_path, sleep=time.sleep, out=print, now=None) -> int:
    by_window = {}
    for key, window in ps.WINDOWS:
        try:
            by_window[key] = walk_window(cfg, fetcher, window, sleep)
        except (ym.MatchupError, yr.FetchError) as e:
            out("window %s FAILED: %s (the previous file stays)" % (key, e))
            return 1
        out("window %s: %d players" % (key, len(by_window[key])))
        sleep(cfg.get("requestDelaySeconds", 1.5))
    if len(by_window["season"]) < MIN_PLAYERS:
        out("FAILED: only %d players in the season window (the previous file stays)" % len(by_window["season"]))
        return 1
    at = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ps.build(by_window, at), f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_path)
    out("wrote %s (%d bytes)" % (out_path, os.path.getsize(out_path)))
    return 0


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cfg = yr.load_config()
    return run(cfg, fetcher or yr.HttpFetcher(), args.out)


if __name__ == "__main__":
    sys.exit(main())
