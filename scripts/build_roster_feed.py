#!/usr/bin/env python3
"""Yahoo's CURRENT rosters as one small JSON file (the roster feed). Read-only, display only.

    python3 scripts/build_roster_feed.py --out rosters.json [--previous rosters.json]

The 16 team pages (anonymous GETs, no cookies, 1.5 s apart: the same parser and fetcher as the audited roster import in
scripts/update_yahoo_rosters.py) become one document the page fetches every few minutes and overlays on its roster views:

  {"schema": "roster-feed/1", "asOf": ..., "digest": ..., "complete": true|false,
   "teams": {"franchise-01": {"teamId": 8, "name": ..., "asOf": ..., "players": [{"k": "478.p.5352", "n": name, "s": slot, "st": injury?, "t": nba team?}]}}}

It is evidence for the eye, never for the record: it writes nothing under data/, never decides ownership, cap or keepers, and the audited PR
path (update-yahoo-rosters.yml) stays the only way a roster change becomes official. A team whose page failed keeps its previous entry (with its
own, older asOf) so one bad fetch does not blank a roster; the page reports the OLDEST team's time as the feed's age.
Standard library only."""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import yahoo_rosters as yr  # noqa: E402

TEAM_MAP = os.path.join(HERE, "..", "data", "2026-27", "rosters", "team_map.json")
MIN_PLAYERS = 5          # a roster page with fewer rows than this is a parse problem, not a roster


def _player(cfg, p):
    pid = str(p.get("playerId") or "").strip()
    if not pid.isdigit():
        return None
    q = {"k": f"{cfg['gameKey']}.p.{pid}", "n": p.get("name"), "s": p.get("slot")}
    if p.get("injury"):
        q["st"] = str(p["injury"]).strip().upper()
    if p.get("nbaTeam"):
        q["t"] = p["nbaTeam"]
    return q


def build(cfg, team_map, fetcher, now, previous=None, delay=None, sleep=None):
    kwargs = {} if sleep is None else {"sleep": sleep}
    fetched, errors = yr.fetch_teams(cfg, cfg["teamIds"], fetcher, delay=delay, **kwargs)
    teams = {}
    prev = (previous or {}).get("teams", {}) if (previous or {}).get("schema") == "roster-feed/1" else {}
    for t in fetched:
        fid = yr.franchise_for(cfg, team_map, t["teamId"])
        players = [q for q in (_player(cfg, p) for p in t["players"]) if q]
        if not fid or len(players) < MIN_PLAYERS:
            errors.append({"teamId": t["teamId"], "code": "UNUSABLE", "detail": f"{len(players)} players, franchise {fid}"})
            continue
        teams[fid] = {"teamId": int(t["teamId"]), "name": t.get("teamName"), "asOf": now, "players": players}
    for tid in cfg["teamIds"]:
        fid = yr.franchise_for(cfg, team_map, tid)
        if fid and fid not in teams and fid in prev:
            teams[fid] = prev[fid]                         # keep the last good page, with its own older time
    if not teams:
        raise yr.FetchError("EMPTY", "no team page could be read; the previous feed stays up")
    body = {k: [[p["k"], p["s"], p.get("st")] for p in v["players"]] for k, v in sorted(teams.items())}
    return {"schema": "roster-feed/1", "asOf": now, "complete": len(teams) == len(cfg["teamIds"]) and not errors,
            "digest": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16],
            "teams": dict(sorted(teams.items())), "errors": errors}


def main(argv=None, fetcher=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--previous")
    a = ap.parse_args(argv)
    cfg = yr.load_config()
    with open(TEAM_MAP, encoding="utf-8") as f:
        team_map = json.load(f)
    previous = None
    if a.previous and os.path.exists(a.previous):
        try:
            with open(a.previous, encoding="utf-8") as f:
                previous = json.load(f)
        except (OSError, ValueError):
            previous = None
    try:
        doc = build(cfg, team_map, fetcher or yr.HttpFetcher(), yr.now_utc(), previous)
    except yr.FetchError as e:
        print(f"FAILED: {e.code}: {e.detail}")
        return 1
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, a.out)
    print(f"roster feed: {len(doc['teams'])} teams, {sum(len(t['players']) for t in doc['teams'].values())} players, complete={doc['complete']}, digest {doc['digest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
