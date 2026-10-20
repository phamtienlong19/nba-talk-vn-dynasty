#!/usr/bin/env python3
"""Refresh player DISPLAY metadata -- NBA team, position eligibility, injury status -- from Yahoo's public draft-analysis
endpoint (config/yahoo_source.json registryUrl), read-only, no credentials.

    python3 scripts/refresh_player_metadata.py                 # dry run: report what would change
    python3 scripts/refresh_player_metadata.py --write         # update data/yahoo/player_registry.json + player_status.json
    python3 scripts/refresh_player_metadata.py --raw FILE.json # use a saved raw response

What changes: nbaTeam, displayPosition, eligiblePositions of players already in the registry, and the league-wide status
table data/yahoo/player_status.json. What never changes: the player universe (no player is added or removed), identity,
oRank and projectedAuctionValue. The registry's O-Rank stays the preseason reference (cooldown rule: top-32 preseason) and
payroll uses salary_freeze.json, so neither a changed rank nor a changed price can move a cap total. Rostered players that
Yahoo's team pages describe differently (league eligibility) are reconciled by yahoo_rosters.py, not here.
Standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_yahoo_draft_analysis import fetch_raw, load_config, validate_shape  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "data", "yahoo", "player_registry.json")
STATUS = os.path.join(ROOT, "data", "yahoo", "player_status.json")
CONFIG = os.path.join(ROOT, "config", "yahoo_source.json")
FIELDS = ("nbaTeam", "displayPosition", "eligiblePositions")


def live_fields(raw: dict) -> dict:
    out = {}
    for entry in validate_shape(raw):
        p = entry.get("player", entry)
        out[p["player_key"]] = {
            "nbaTeam": p.get("editorial_team_abbr"),
            "displayPosition": p.get("display_position"),
            "eligiblePositions": [e.get("position") for e in p.get("eligible_positions", []) or [] if e.get("position")],
            "status": (p.get("status") or "").strip().upper() or None,
            "name": (p.get("name") or {}).get("full"),
        }
    return out


def plan(registry: dict, live: dict) -> dict:
    changes, missing = [], []
    for p in registry["players"]:
        new = live.get(p["playerKey"])
        if new is None:
            missing.append(p["name"])  # Yahoo no longer lists him in this response: keep the last known values
            continue
        diff = {f: (p.get(f), new[f]) for f in FIELDS if new[f] not in (None, [], "") and p.get(f) != new[f]}
        if diff:
            changes.append({"playerKey": p["playerKey"], "name": p["name"], "diff": diff})
    known = {p["playerKey"] for p in registry["players"]}
    return {"changes": changes, "missing": missing, "newOnYahoo": sorted(live[k]["name"] for k in live if k not in known)}


def apply(registry: dict, live: dict, fetched_at: str) -> None:
    for p in registry["players"]:
        new = live.get(p["playerKey"])
        if new is None:
            continue
        for f in FIELDS:
            if new[f] not in (None, [], ""):
                p[f] = new[f]
    registry["metadataRefreshedAt"] = fetched_at


def status_doc(live: dict, fetched_at: str) -> dict:
    return {"capturedAt": fetched_at, "source": "Yahoo public draft-analysis endpoint (config/yahoo_source.json registryUrl)",
            "note": "Yahoo player status as observed for the 600-player registry (O, Q, P, D, DTD, INJ, OFS, NA ...); healthy players have no entry. "
                    "Display / evidence only. Rostered players' status on the cards comes from the verified roster snapshot.",
            "statuses": {k: v["status"] for k, v in sorted(live.items()) if v["status"]}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--raw", help="saved raw response instead of a live fetch")
    args = ap.parse_args(argv)
    if args.raw:
        with open(args.raw, encoding="utf-8") as f:
            raw = json.load(f)
        fetched_at = datetime.datetime.fromtimestamp(os.path.getmtime(args.raw), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        raw = json.loads(fetch_raw(load_config(CONFIG)["registryUrl"], timeout=90))
        fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(REGISTRY, encoding="utf-8") as f:
        registry = json.load(f)
    live = live_fields(raw)
    p = plan(registry, live)
    team = [c for c in p["changes"] if "nbaTeam" in c["diff"]]
    pos = [c for c in p["changes"] if "displayPosition" in c["diff"] or "eligiblePositions" in c["diff"]]
    print(f"live {len(live)} players at {fetched_at}; registry {len(registry['players'])}")
    print(f"NBA team changes: {len(team)}  position-eligibility changes: {len(pos)}  "
          f"not in this response: {len(p['missing'])}  on Yahoo but not in the registry: {len(p['newOnYahoo'])}")
    for c in team:
        print(f"  TEAM  {c['name']}: {c['diff']['nbaTeam'][0]} -> {c['diff']['nbaTeam'][1]}")
    for c in pos:
        d = c["diff"]
        print(f"  POS   {c['name']}: {d.get('displayPosition', ('', ''))[0]} -> {d.get('displayPosition', ('', ''))[1]}"
              if "displayPosition" in d else f"  ELIG  {c['name']}: {d['eligiblePositions'][0]} -> {d['eligiblePositions'][1]}")
    st = status_doc(live, fetched_at)
    from collections import Counter
    print("statuses:", dict(Counter(st["statuses"].values())))
    if not args.write:
        print("dry run: nothing written (use --write)")
        return 0
    apply(registry, live, fetched_at)
    with open(REGISTRY, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"wrote {os.path.relpath(REGISTRY, ROOT)} and {os.path.relpath(STATUS, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
