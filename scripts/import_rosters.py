#!/usr/bin/env python3
"""Commissioner roster refresh: import a verified Yahoo roster export, review the diff, then commit.

    python3 scripts/import_rosters.py diff   FILE --verified-at 2026-11-02T15:00:00Z --source "Yahoo rosters page, exported by <who>"
    python3 scripts/import_rosters.py commit FILE --verified-at ... --source ... --reviewed
    python3 scripts/import_rosters.py rollback          # current snapshot -> the previous one (files are kept)
    python3 scripts/import_rosters.py status
    python3 scripts/import_rosters.py export FILE.csv     # current-season rosters as an editable import template
    python3 scripts/import_rosters.py link-provisional provisional:dailyn-swain 478.p.12345

FILE is CSV (header: team,player_key,player_id,player_name,slot -- player_key/player_id may be blank) or JSON
({"teams":[{"team":..., "players":[{"playerKey"|"playerId", "name", "slot"}]}]}). See docs/ROSTER_REFRESH.md.

Rules: teams map through data/2026-27/rosters/team_map.json (Yahoo team key, else an alias); players resolve by Yahoo player
key, then Yahoo player id, then an explicit alias, then a unique exact name (flagged). Anything unmatched BLOCKS the
commit -- a player is never silently dropped or invented. A team missing from the file blocks too. The diff separates
ownership changes (added / dropped / changed team) from IL moves and lineup-only slot changes. The same content, an
older timestamp, or a player on two teams cannot be committed. Every prior snapshot is kept; `rollback` only moves the
pointer. COMPLETED in-season transactions dated before the new snapshot must be reflected in it, or the commit blocks.
The canonical snapshot shape is what a future authenticated Yahoo API adapter would also write.
Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_fa_draft_pool as pool  # noqa: E402
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402

GAME_KEY = "478"  # Yahoo NBA 2026-27 game key (every registry playerKey is 478.p.<id>)
SLOT_ALIASES = {"BENCH": "BN", "BN": "BN", "UTIL": "Util", "IL+": "IL+", "IL": "IL", "INJ": "IL"}
SLOTS = {"PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util", "BN", "IL", "IL+"}
MAX_ROSTER = 15  # league rule: 15 roster spots (8 active + 3 bench + 2 IL + 2 IL+)


class ImportBlocked(ValueError):
    pass


# ------------------------------------------------------------------ parsing
def parse(path: str) -> list:
    """-> rows [{team, playerKey, playerId, name, slot}] in file order."""
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        rows = []
        for t in doc["teams"]:
            team = t.get("teamKey") or t.get("team")
            for p in t["players"]:
                rows.append({"team": team, "playerKey": p.get("playerKey"), "playerId": p.get("playerId"),
                             "name": p.get("name"), "slot": p.get("slot")})
        return rows
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{"team": (r.get("team") or "").strip(), "playerKey": (r.get("player_key") or "").strip() or None,
                 "playerId": (r.get("player_id") or "").strip() or None, "name": (r.get("player_name") or "").strip() or None,
                 "slot": (r.get("slot") or "").strip() or None} for r in csv.DictReader(f)]


def norm_slot(slot):
    if slot is None or slot == "":
        return None
    s = SLOT_ALIASES.get(slot.strip().upper(), slot.strip())
    return s if s in SLOTS else ("!" + slot)


# ---------------------------------------------------------------- resolving
def load_maps(data_dir):
    tm = ss._load(os.path.join(data_dir, "rosters", "team_map.json"))
    al = ss._load(os.path.join(data_dir, "rosters", "player_aliases.json"))["aliases"]
    return tm, al


def resolve_team(team_map: dict, value: str):
    v = (value or "").strip()
    for fid, t in team_map["teams"].items():
        if v and (v == t.get("yahooTeamKey") or v.lower() in {a.lower() for a in t["aliases"]} or v == fid):
            return fid
    return None


def known_players(si) -> dict:
    """Every identity the league can roster with a frozen salary: registry + provisional."""
    out = {k: p["name"] for k, p in si["registry"].items()}
    out.update({k: p["name"] for k, p in si["extraPlayers"].items()})
    return out


def resolve_player(si, aliases: dict, row: dict):
    """-> (playerKey, how, note). how is None when unmatched."""
    known = known_players(si)
    links = {p["yahooPlayerKey"]: k for k, p in si["extraPlayers"].items() if p.get("yahooPlayerKey")}
    key = row.get("playerKey") or (f"{GAME_KEY}.p.{row['playerId']}" if row.get("playerId") else None)
    if key:
        if key in links:
            return links[key], "PROVISIONAL_LINK", None
        if key in known:
            return key, "KEY", None
        if key in aliases:
            return aliases[key], "ALIAS", None
    name = row.get("name") or ""
    n = pool.normalize_name(name)
    if name in aliases or n in aliases:
        return aliases.get(name) or aliases[n], "ALIAS", None
    hits = [k for k, nm in known.items() if pool.normalize_name(nm) == n]
    if len(hits) == 1:
        k = hits[0]
        if k in si["extraPlayers"]:
            note = (f"provisional {k} appears with Yahoo key {key}: run link-provisional {k} {key} after review"
                    if key else f"provisional {k} matched by name")
            return k, "PROVISIONAL_NAME", note
        return k, "NAME", (f"Yahoo key {key} not in the frozen player table; matched '{name}' by name" if key else f"matched '{name}' by name")
    return None, None, (f"{len(hits)} players named '{name}'" if hits else f"unknown player '{name}' ({key or 'no Yahoo id'})")


# ------------------------------------------------------------------ building
def build_snapshot(si, rows, verified_at: str, source: str, data_dir: str) -> tuple:
    team_map, aliases = load_maps(data_dir)
    blocking, warnings = [], []
    teams = {fid: [] for fid in si["franchises"]}
    seen = {}
    for i, r in enumerate(rows, 2):
        fid = resolve_team(team_map, r["team"])
        if fid is None:
            blocking.append({"code": "UNMATCHED_TEAM", "line": i, "detail": r["team"]})
            continue
        key, how, note = resolve_player(si, aliases, r)
        if key is None:
            blocking.append({"code": "UNMATCHED_PLAYER", "line": i, "team": si["shorts"][fid], "detail": note})
            continue
        if how in ("NAME", "PROVISIONAL_NAME"):
            warnings.append({"code": "MATCHED_BY_NAME" if how == "NAME" else "PROVISIONAL_LINK_CANDIDATE",
                             "line": i, "team": si["shorts"][fid], "detail": note})
        if key in seen:
            blocking.append({"code": "DUPLICATE_OWNERSHIP", "line": i, "detail": f"{ls.player_name(si, key)} on "
                             f"{si['shorts'][seen[key]]} and {si['shorts'][fid]}"})
            continue
        slot = norm_slot(r.get("slot"))
        if slot and slot.startswith("!"):
            blocking.append({"code": "UNKNOWN_SLOT", "line": i, "detail": slot[1:]})
            continue
        seen[key] = fid
        teams[fid].append({"playerKey": key, "name": ls.player_name(si, key), "slot": slot})
    for fid, ps in teams.items():
        if not ps:
            blocking.append({"code": "TEAM_MISSING", "detail": f"{si['shorts'][fid]} has no rows: a whole roster is never removed silently"})
        elif len(ps) > MAX_ROSTER:
            warnings.append({"code": "ROSTER_OVER_15", "detail": f"{si['shorts'][fid]} has {len(ps)} players"})
    teams = {fid: sorted(ps, key=lambda r: r["playerKey"]) for fid, ps in sorted(teams.items())}
    digest = ls._digest(teams)
    snap = {"snapshotId": f"RS-{ss.ts(verified_at)[:10]}-{digest[:8]}", "season": "2026-27",
            "verifiedAt": ss.ts(verified_at), "source": source, "kind": "VERIFIED_IMPORT",
            "importedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "teams": teams,
            "ownershipDigest": ls._digest({f: sorted(r["playerKey"] for r in rs) for f, rs in teams.items()}),
            "digest": digest}
    return snap, {"blocking": blocking, "warnings": warnings}


def diff(si, snap) -> dict:
    """New snapshot vs the CURRENT-SEASON state (current snapshot + COMPLETED transactions not yet reflected)."""
    cur = ss.season_state(si)
    old_owner, old_slot = cur["playerOwner"], cur["slots"]
    new_owner = ss.snapshot_owner(snap)
    new_slot = ss.snapshot_slots(snap)
    out = {"added": [], "dropped": [], "changedTeam": [], "ilMoves": [], "lineupOnly": [], "unchanged": 0,
           "transactions": []}
    nm = lambda k: ls.player_name(si, k)  # noqa: E731
    sh = si["shorts"]
    for k, f in sorted(new_owner.items()):
        if k not in old_owner:
            out["added"].append({"player": nm(k), "key": k, "team": sh[f], "slot": new_slot[k]})
        elif old_owner[k] != f:
            out["changedTeam"].append({"player": nm(k), "key": k, "from": sh[old_owner[k]], "to": sh[f]})
        else:
            a, b = old_slot.get(k), new_slot.get(k)
            if a == b or a is None:
                out["unchanged"] += 1
            elif (a in ss.SLOTS_IL) != (b in ss.SLOTS_IL) or (a in ss.SLOTS_IL and b in ss.SLOTS_IL):
                out["ilMoves"].append({"player": nm(k), "team": sh[f], "from": a, "to": b})
            else:
                out["lineupOnly"].append({"player": nm(k), "team": sh[f], "from": a, "to": b})
    for k, f in sorted(old_owner.items()):
        if k not in new_owner:
            out["dropped"].append({"player": nm(k), "key": k, "team": sh[f]})
    for t in ss.pending_completed(si):
        if ss.ts(t["effectiveAt"]) <= snap["verifiedAt"]:
            ok = all(new_owner.get(a["playerKey"]) == a["to"] for a in t["assets"] if a["type"] == "player")
            out["transactions"].append({"txnId": t["txnId"], "label": t.get("label"), "reflected": ok})
    return out


# ------------------------------------------------------------------- commit
def _index_path(data_dir):
    return os.path.join(data_dir, "rosters", "index.json")


def commit(si, snap, report, d, data_dir, reviewed: bool) -> str:
    if not reviewed:
        raise ImportBlocked("review the diff first, then commit with --reviewed")
    problems = list(report["blocking"])
    problems += [{"code": "COMPLETED_TRANSACTION_NOT_REFLECTED", "detail": t["txnId"]} for t in d["transactions"] if not t["reflected"]]
    idx = ss._load(_index_path(data_dir))
    cur = si["rosterSnapshot"]
    if snap["verifiedAt"] <= cur["verifiedAt"]:
        problems.append({"code": "NOT_NEWER", "detail": f"verifiedAt {snap['verifiedAt']} is not after the current {cur['verifiedAt']}"})
    if any(h.get("digest") == snap["digest"] for h in idx["history"]):
        problems.append({"code": "DUPLICATE_IMPORT", "detail": "identical roster content was already imported"})
    if problems:
        raise ImportBlocked("; ".join(f"{p['code']}: {p.get('detail')}" for p in problems))
    rel = f"snapshots/{snap['snapshotId']}.json"
    path = os.path.join(data_dir, "rosters", rel)
    if os.path.exists(path):
        raise ImportBlocked(f"DUPLICATE_IMPORT: {snap['snapshotId']} already exists")
    ss._write(path, snap)
    idx["history"].append({"snapshotId": snap["snapshotId"], "file": rel, "verifiedAt": snap["verifiedAt"],
                           "source": snap["source"], "digest": snap["digest"], "action": "COMMIT",
                           "previous": idx["current"]})
    idx["current"] = rel
    ss._write(_index_path(data_dir), idx)
    return rel


def rollback(data_dir) -> str:
    idx = ss._load(_index_path(data_dir))
    entry = next((h for h in reversed(idx["history"]) if h.get("file") == idx["current"] and h["action"] in ("COMMIT", "INIT")), None)
    if entry is None or not entry.get("previous"):
        raise ImportBlocked("nothing to roll back to")
    idx["history"].append({"action": "ROLLBACK", "from": idx["current"], "to": entry["previous"],
                           "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    idx["current"] = entry["previous"]
    ss._write(_index_path(data_dir), idx)
    return idx["current"]


def link_provisional(data_dir, prov_key: str, yahoo_key: str, registry: dict) -> None:
    """Attach a Yahoo id to a provisional identity WITHOUT changing it: the draft event, rookie flag, frozen salary and
    every snapshot keep the provisional key; imports carrying the Yahoo key resolve to it from now on."""
    path = os.path.join(data_dir, "provisional_players.json")
    doc = ss._load(path)
    hit = [p for p in doc["players"] if p["playerKey"] == prov_key]
    if not hit:
        raise ImportBlocked(f"{prov_key} is not a provisional player")
    if any(p.get("yahooPlayerKey") == yahoo_key and p["playerKey"] != prov_key for p in doc["players"]):
        raise ImportBlocked(f"{yahoo_key} is already linked to another provisional player")
    sal = ss._load(os.path.join(data_dir, "salary_freeze.json"))["salaries"]
    if yahoo_key in sal:
        raise ImportBlocked(f"{yahoo_key} already has its own frozen identity; linking would create a second player")
    hit[0]["yahooPlayerKey"] = yahoo_key
    if yahoo_key in registry:
        hit[0]["yahooName"] = registry[yahoo_key]["name"]
    ss._write(path, doc)


def export_csv(si, path) -> int:
    """Write the CURRENT-SEASON rosters as an import-ready CSV (a template to edit, or a round-trip check)."""
    cur = ss.season_state(si)
    rows = []
    for k, f in cur["playerOwner"].items():
        rows.append((si["shorts"][f], k, k.split(".p.")[-1] if ".p." in k else "", ls.player_name(si, k), cur["slots"].get(k) or ""))
    rows.sort(key=lambda r: (list(si["shorts"].values()).index(r[0]), r[3]))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["team", "player_key", "player_id", "player_name", "slot"])
        w.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------------- cli
def _report(snap, report, d):
    lines = [f"snapshot {snap['snapshotId']} verified {snap['verifiedAt']} -- {snap['source']}"]
    for b in report["blocking"]:
        lines.append(f"  BLOCKING {b['code']}: {b.get('team', '')} {b.get('detail')} (line {b.get('line', '-')})")
    for w in report["warnings"]:
        lines.append(f"  WARNING  {w['code']}: {w.get('team', '')} {w.get('detail')}")
    if d:
        for k, title in (("added", "ADDED"), ("dropped", "DROPPED"), ("changedTeam", "CHANGED TEAM"),
                         ("ilMoves", "IL MOVE"), ("lineupOnly", "LINEUP ONLY")):
            for x in d[k]:
                lines.append(f"  {title:12} {json.dumps(x, ensure_ascii=False)}")
        for t in d["transactions"]:
            lines.append(f"  TRANSACTION  {t['txnId']} {'reflected' if t['reflected'] else 'NOT REFLECTED (blocks commit)'}")
        lines.append(f"  unchanged: {d['unchanged']}")
    return "\n".join(lines)


def _prepare(args):
    si = ss.load_season(ls.load_inputs())
    snap, report = build_snapshot(si, parse(args.file), args.verified_at, args.source, ss.DATA_DIR)
    d = diff(si, snap) if not any(b["code"] in ("UNMATCHED_TEAM", "DUPLICATE_OWNERSHIP") for b in report["blocking"]) else None
    return si, snap, report, d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("diff", "commit"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("--verified-at", required=True)
        p.add_argument("--source", required=True)
        if name == "commit":
            p.add_argument("--reviewed", action="store_true")
    sub.add_parser("rollback")
    sub.add_parser("status")
    p = sub.add_parser("export")
    p.add_argument("file")
    p = sub.add_parser("link-provisional")
    p.add_argument("provisional_key")
    p.add_argument("yahoo_key")
    args = ap.parse_args()
    try:
        if args.cmd == "diff":
            _si, snap, report, d = _prepare(args)
            print(_report(snap, report, d))
            sys.exit(1 if report["blocking"] else 0)
        if args.cmd == "commit":
            si, snap, report, d = _prepare(args)
            print(_report(snap, report, d))
            print("committed:", commit(si, snap, report, d or {"transactions": []}, ss.DATA_DIR, args.reviewed))
        elif args.cmd == "export":
            print(f"wrote {export_csv(ss.load_season(ls.load_inputs()), args.file)} rows to {args.file}")
        elif args.cmd == "rollback":
            print("current snapshot ->", rollback(ss.DATA_DIR))
        elif args.cmd == "status":
            idx = ss._load(_index_path(ss.DATA_DIR))
            cur = ss._load(os.path.join(ss.ROSTER_DIR, idx["current"]))
            print(f"current: {cur['snapshotId']} verified {cur['verifiedAt']} ({cur['source']})")
            for h in idx["history"]:
                print("  ", json.dumps(h, ensure_ascii=False))
        elif args.cmd == "link-provisional":
            link_provisional(ss.DATA_DIR, args.provisional_key, args.yahoo_key, ls.load_inputs()["registry"])
            print(f"linked {args.provisional_key} -> {args.yahoo_key}")
    except ImportBlocked as e:
        print("BLOCKED:", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
