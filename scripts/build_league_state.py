#!/usr/bin/env python3
"""Build / maintain the pre-draft league state files and the page data.

    baseline      derive keeper_freeze.json (status "projected") + picks.json
                  from the CURRENT board in index.html. Refuses to touch a
                  LOCKED keeper freeze.
    lock-keepers  freeze the keeper baseline (status "locked", digest, time).
                  After this, `baseline` will never overwrite it.
    embed         splice the derived views (official state, every scenario
                  combination of the proposed trades, pick table, available
                  player universe) into index.html as inline JSON for the
                  Trade Lab / Picks / All-Available surfaces.

The scenario table is produced by scripts/league_state.py (one source of
truth); the page only looks results up -- it never re-implements the engine.
Standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import html as html_lib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_fa_draft_pool as pool  # noqa: E402
import league_state as ls  # noqa: E402

REPO_ROOT = ls.REPO_ROOT
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")
DATA_DIR = ls.DATA_DIR
DATA_BEGIN = "<!--LEAGUE-DATA-BEGIN-->"
DATA_END = "<!--LEAGUE-DATA-END-->"
APP_MARK = '<script id="league-app">'
SEASON = "2026-27"
# Committed/public league views derive ONLY from tracked canonical state.
# data/yahoo/ = promoted canonical Yahoo snapshot; local_data/yahoo/ is
# mutable refresh working data and must never be an implicit dependency here.
CANONICAL_YAHOO_PATH = os.path.join(REPO_ROOT, "data", "yahoo", "players_normalized.json")

TEAM_CARD_RE = re.compile(r'<section class="team-card"([^>]*)>(.*?)</section>', re.S)


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_board(index_html: str):
    """Return (teams, picks): teams in board order with short/name/colors/kept names;
    picks as (round, slot, team-name-text) from the draft-order panels."""
    teams = []
    for attrs, body in TEAM_CARD_RE.findall(index_html):
        color = re.search(r"--team-color:(#[0-9a-fA-F]+)", attrs)
        text = re.search(r"--team-text:(#[0-9a-fA-F]+)", attrs)
        name = html_lib.unescape(re.search(r'<div class="team-name">(.*?)</div>', body, re.S).group(1)).replace(pool.CROWN.strip(), "").strip()
        short = html_lib.unescape(re.search(r'<span class="identity-tag">([^<]*)</span>', body).group(1))
        rows = re.findall(r'<div class="pname">(.*?)</div><div class="nba">[^<]*</div><div class="cap">([\d.]+)</div>', body, re.S)
        kept = [(html_lib.unescape(re.sub(r"<span.*?</span>", "", n)).strip(), float(c)) for n, c in rows]
        teams.append({"name": name, "short": short, "color": color.group(1) if color else "#313844",
                      "text": text.group(1) if text else "#ffffff", "kept": kept})
    panel = index_html[index_html.index('id="draft-order"'):index_html.index('id="rosters-a"')]
    picks = []
    for m in re.finditer(r'<div class="pick-slot">(\d+)\.(\d+)</div>\s*<div class="pick-team"><span class="pick-chip"[^>]*>(.*?)</span>', panel, re.S):
        picks.append((int(m.group(1)), int(m.group(2)), html_lib.unescape(m.group(3)).strip()))
    return teams, picks


def _team_for_chip(chip: str, teams):
    chip = chip.replace(pool.CROWN.strip(), "").strip()
    tail = chip.split("|", 1)[1].strip() if "|" in chip else chip
    for i, t in enumerate(teams):
        if t["name"] == tail or t["name"] == chip:
            return i
    raise ValueError(f"cannot map draft-order chip {chip!r} to a team card")


def registry_lookup(registry_players):
    by_norm = {}
    for p in registry_players:
        key = pool.normalize_name(p["name"])
        cur = by_norm.get(key)
        if cur is None or (p["oRank"] or 9999) < (cur["oRank"] or 9999):
            by_norm[key] = p
    return by_norm


def build_baseline(index_html: str, registry: dict, franchises: list) -> tuple[dict, dict]:
    teams, picks = parse_board(index_html)
    if len(teams) != len(franchises):
        raise ValueError(f"{len(teams)} team cards vs {len(franchises)} franchises")
    lookup = registry_lookup(registry["players"])
    freeze_teams = []
    for i, t in enumerate(teams):
        keepers = []
        for name, board_cap in t["kept"]:
            p = lookup.get(pool.normalize_name(name))
            if p is None:
                raise ValueError(f"kept player {name!r} ({t['short']}) is not in the Yahoo player registry")
            if float(p["projectedAuctionValue"]) != board_cap:
                raise ValueError(f"{name}: board cap {board_cap} != Yahoo registry cap {p['projectedAuctionValue']}")
            keepers.append({"playerKey": p["playerKey"], "name": p["name"]})
        freeze_teams.append({"franchiseId": franchises[i]["franchiseId"], "short": t["short"], "teamName": t["name"],
                             "color": t["color"], "text": t["text"], "keepers": keepers})
    freeze = {
        "season": SEASON,
        "status": "projected",
        "statusNote": "PROJECTED keeper baseline taken from the current keeper board. NOT officially frozen; "
                      "run `build_league_state.py lock-keepers` to create the immutable baseline.",
        "source": "index.html keeper board",
        "lockedAt": None,
        "teams": freeze_teams,
    }
    pick_rows = []
    for rnd, slot, chip in picks:
        pick_rows.append({"pickId": f"2026-R{rnd}-{slot:02d}", "round": rnd, "slot": slot,
                          "originalOwner": franchises[_team_for_chip(chip, teams)]["franchiseId"]})
    if len(pick_rows) != 48 or len({p["pickId"] for p in pick_rows}) != 48:
        raise ValueError(f"expected 48 unique picks, parsed {len(pick_rows)}")
    return freeze, {"season": SEASON, "note": "originalOwner = owner at the keeper baseline; current owner is DERIVED from the trade ledger.",
                    "picks": pick_rows}


def cmd_baseline(args):
    freeze_path = os.path.join(DATA_DIR, "keeper_freeze.json")
    if os.path.exists(freeze_path) and ls._load(freeze_path).get("status") == "locked":
        print("keeper freeze is LOCKED -- baseline not regenerated (immutable).")
        return
    with open(INDEX_HTML, encoding="utf-8") as f:
        html = f.read()
    registry = ls._load(ls.REGISTRY_PATH)
    franchises = ls._load(os.path.join(DATA_DIR, "franchises.json"))["franchises"]
    freeze, picks = build_baseline(html, registry, franchises)
    _write(freeze_path, freeze)
    _write(os.path.join(DATA_DIR, "picks.json"), picks)
    print(f"baseline: {sum(len(t['keepers']) for t in freeze['teams'])} projected keepers, {len(picks['picks'])} picks")


def cmd_lock(args):
    path = os.path.join(DATA_DIR, "keeper_freeze.json")
    inputs = ls.load_inputs()
    state = ls.initial_state(inputs)
    registry = ls._load(ls.REGISTRY_PATH)
    checkpoint = {
        "season": inputs["freeze"]["season"],
        "capBand": {"floor": ls.cap_band(inputs)[0], "ceiling": ls.cap_band(inputs)[1],
                    "policy": "config/cap_policy.json (official; formula ceiling 177)"},
        "teams": {f: ls.checkpoint_team(inputs, state, f) for f in sorted(inputs["franchises"])},
        "provenance": {"declaration": args.note or "Final keeper declarations confirmed by the league owner",
                       "capSource": "Yahoo player registry projectedAuctionValue",
                       "yahooRegistryFetchedAt": registry.get("fetchedAt")},
    }
    locked = ls.lock_keepers(ls._load(path), args.at or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), checkpoint)
    _write(path, locked)
    snap_dir = os.path.join(DATA_DIR, "snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    _write(os.path.join(snap_dir, "KEEPER_FREEZE.json"), ls.make_snapshot(ls.load_inputs(), "KEEPER_FREEZE"))
    print(f"keepers LOCKED ({locked['lockDigest'][:12]})")


# ------------------------------------------------------------- embedding
def build_page_data(inputs: dict, index_html: str, yahoo_path: str = CANONICAL_YAHOO_PATH) -> dict:
    floor, ceiling = ls.cap_band(inputs)
    fr = inputs["franchises"]
    teams = [{"id": t["franchiseId"], "short": t["short"], "name": t.get("teamName") or fr[t["franchiseId"]]["displayName"],
              "color": t["color"], "text": t["text"],
              "crown": t["short"] == pool.DEFENDING_CHAMPION_SHORT_NAME} for t in inputs["freeze"]["teams"]]
    base = ls.initial_state(inputs)
    official = ls.resolve(inputs, (), "OFFICIAL")
    # playerKey -> the name as printed on the keeper board (the page re-uses the board's own rows)
    board_teams, _ = parse_board(index_html)
    lookup = registry_lookup(list(inputs["registry"].values()))
    board_names = {}
    for bt in board_teams:
        for name, _cap in bt["kept"]:
            p = lookup.get(pool.normalize_name(name))
            if p is not None:
                board_names[p["playerKey"]] = name
    official_teams = {t["id"]: ls.team_report(inputs, official, t["id"], base) for t in teams}
    trades = []
    for t in ls.selectable_trades(inputs) + [x for x in inputs["trades"]["trades"] if x["status"] not in ls.SELECTABLE_STATUSES]:
        recv = {}
        for a in ls.trade_assets(t):
            recv.setdefault(a["to"], []).append(ls.describe_asset(inputs, a))
        trades.append({"id": t["tradeId"], "label": t.get("label"), "status": t["status"], "order": t["order"],
                       "dependsOn": t.get("dependsOn", []), "participants": t["participants"],
                       "receives": recv, "note": t.get("note")})
    # available universe: registry + curated Yahoo-missing prospects, minus kept (official state)
    yahoo = pool.load_yahoo_players(yahoo_path)
    dyn, dyn_max = pool.load_dynasty_rankings()
    cands = pool.build_candidates(index_html, yahoo, dyn, dyn_max, rookie_names=pool.load_rookie_names(),
                                  draft_years=pool.load_draft_years())
    final = pool.sort_and_truncate(cands)
    board_rank = {pool.normalize_name(c.name): i for i, c in enumerate(final, 1)}
    src_by_norm = {k: c for k, c in cands.items()}
    owned = set(official["playerOwner"])
    rows, seen_norm = [], set()
    for p in inputs["registry"].values():
        if p["playerKey"] in owned:
            continue
        key = pool.normalize_name(p["name"])
        c = src_by_norm.get(key)
        src = (c.src_team if c is not None and c.src == "cut" else ("R" if c is not None and c.rookie else "FA"))
        rows.append([p["playerKey"], p["name"], p["nbaTeam"], p["displayPosition"], p["projectedAuctionValue"],
                     p["oRank"], board_rank.get(key), src])
        seen_norm.add(key)
    extras = []
    for key, c in sorted(src_by_norm.items()):
        if key in seen_norm or key in {pool.normalize_name(inputs['registry'][k]['name']) for k in owned}:
            continue
        if key in board_rank or c.name in pool.CURATED_ROOKIE_OVERLAY:
            rows.append([f"curated:{key}", c.name, c.nba, c.pos, c.cap, None, board_rank.get(key), "R" if c.rookie else "FA"])
            extras.append(c.name)
    rows.sort(key=lambda r: (r[6] is None, r[6] or 0, r[5] is None, r[5] or 0, r[1]))
    return {
        "season": inputs["freeze"]["season"],
        "keeperStatus": inputs["freeze"]["status"],
        "cap": {"floor": floor, "ceiling": ceiling, "near": ls.NEAR_CEILING_ROOM},
        "boardNames": board_names,
        "teams": teams,
        "official": {"teams": official_teams, "picks": ls.pick_table(inputs, official),
                     "windowWarnings": official["windowWarnings"], "tradeIds": official["activeTradeIds"]},
        "trades": trades,
        "scenarios": ls.enumerate_scenarios(inputs),
        "available": {"cols": ["key", "name", "nba", "pos", "cap", "yahooOr", "board", "src"], "rows": rows,
                      "curatedYahooMissing": extras},
    }


def embed(index_html: str, data: dict) -> str:
    block = (DATA_BEGIN + '<script type="application/json" id="league-data">'
             + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
             + "</script>" + DATA_END)
    if DATA_BEGIN in index_html:
        a, b = index_html.index(DATA_BEGIN), index_html.index(DATA_END) + len(DATA_END)
        return index_html[:a] + block + index_html[b:]
    if APP_MARK not in index_html:
        raise ValueError("index.html has no league-app script to embed the data before")
    return index_html.replace(APP_MARK, block + APP_MARK, 1)


def cmd_embed(args):
    with open(INDEX_HTML, encoding="utf-8") as f:
        html = f.read()
    inputs = ls.load_inputs()
    data = build_page_data(inputs, html)
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(embed(html, data))
    print(f"embedded league data: {len(data['scenarios'])} scenarios, {len(data['available']['rows'])} available players")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("baseline").set_defaults(fn=cmd_baseline)
    lk = sub.add_parser("lock-keepers")
    lk.add_argument("--at", default=None)
    lk.add_argument("--note", default=None)
    lk.set_defaults(fn=cmd_lock)
    sub.add_parser("embed").set_defaults(fn=cmd_embed)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
