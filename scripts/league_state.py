#!/usr/bin/env python3
"""Pre-draft league state engine: keeper freeze + trade ledger + draft ledger.

    CURRENT OFFICIAL STATE = KEEPER FREEZE + OFFICIAL TRADES + DRAFT EVENTS
    SCENARIO STATE         = CURRENT OFFICIAL STATE + SELECTED PROPOSED/AGREED TRADES

Pure, deterministic, standard-library only. Ownership of players and picks is
DERIVED by replaying transactions over the baseline -- nothing here stores a
resulting cap or owner. Cap comes from the Yahoo player registry
(projectedAuctionValue) and the official band in config/cap_policy.json.

Inputs (data/2026-27/):
    keeper_freeze.json  status "projected" | "locked"; per-team keeper playerKeys
    picks.json          stable pick ids + ORIGINAL owner (never overwritten)
    trades.json         atomic transactions (PROPOSED | AGREED | OFFICIAL | VOID)
    draft_state.json    ordered DRAFT_PICK events (empty before the draft)
Player metadata lives only in data/yahoo/player_registry.json.

Validation never "fixes" a trade: an invalid trade is NOT applied, and its
errors (NOT_OWNED, BROKEN_DEPENDENCY, ...) are surfaced. Warnings (unbalanced
asset counts, cap direction, ...) do not stop a trade being applied/visualised.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_DIR = os.path.join(REPO_ROOT, "data", "2026-27")
REGISTRY_PATH = os.path.join(REPO_ROOT, "data", "yahoo", "player_registry.json")
POLICY_PATH = os.path.join(REPO_ROOT, "config", "cap_policy.json")

FREEZE_STATUSES = ("projected", "locked")
TRADE_STATUSES = ("PROPOSED", "AGREED", "OFFICIAL", "VOID")
SELECTABLE_STATUSES = ("PROPOSED", "AGREED")
SNAPSHOT_KINDS = ("KEEPER_FREEZE", "PRE_DRAFT_LOCK", "POST_DRAFT")
MAX_KEEPERS = 9
# Same convention as the board's existing "near ceiling" colouring (refresh_team_cap_summary.NEAR_THRESHOLD).
NEAR_CEILING_ROOM = 4


class StateError(ValueError):
    """Structurally invalid canonical input (not a mere invalid trade)."""


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_inputs(data_dir: str = DATA_DIR, registry_path: str = REGISTRY_PATH, policy_path: str = POLICY_PATH) -> dict:
    registry = _load(registry_path)
    inputs = {
        "franchises": {f["franchiseId"]: f for f in _load(os.path.join(data_dir, "franchises.json"))["franchises"]},
        "freeze": _load(os.path.join(data_dir, "keeper_freeze.json")),
        "picks": _load(os.path.join(data_dir, "picks.json")),
        "trades": _load(os.path.join(data_dir, "trades.json")),
        "draft": _load(os.path.join(data_dir, "draft_state.json")),
        "registry": {p["playerKey"]: p for p in registry["players"]},
        "policy": _load(policy_path),
    }
    inputs["shorts"] = {t["franchiseId"]: t["short"] for t in inputs["freeze"]["teams"]}
    inputs["pickIndex"] = {p["pickId"]: p for p in inputs["picks"]["picks"]}
    inputs["tradeIndex"] = {t["tradeId"]: t for t in inputs["trades"]["trades"]}
    # playerKey -> {name, nbaTeam, displayPosition, cap} for drafted players Yahoo does not list yet (provisional, cap 0)
    prov = os.path.join(data_dir, "provisional_players.json")
    inputs["extraPlayers"] = {p["playerKey"]: p for p in _load(prov)["players"]} if os.path.exists(prov) else {}
    validate_inputs(inputs)
    return inputs


def validate_inputs(inputs: dict) -> None:
    """Canonical-state integrity: raises StateError. No duplicate player or pick ownership."""
    freeze = inputs["freeze"]
    if freeze.get("status") not in FREEZE_STATUSES:
        raise StateError(f"keeper_freeze.status must be one of {FREEZE_STATUSES}")
    seen = {}
    for team in freeze["teams"]:
        if team["franchiseId"] not in inputs["franchises"]:
            raise StateError(f"unknown franchise {team['franchiseId']}")
        if len(team["keepers"]) > MAX_KEEPERS:
            raise StateError(f"{team['franchiseId']} has more than {MAX_KEEPERS} keepers")
        for k in team["keepers"]:
            key = k["playerKey"]
            if key not in inputs["registry"]:
                raise StateError(f"keeper {k.get('name')} ({key}) is not in the Yahoo player registry")
            if key in seen:
                raise StateError(f"duplicate player ownership: {k.get('name')} on {seen[key]} and {team['franchiseId']}")
            seen[key] = team["franchiseId"]
    pids = [p["pickId"] for p in inputs["picks"]["picks"]]
    if len(pids) != len(set(pids)):
        raise StateError("duplicate pick ids in picks.json")
    for p in inputs["picks"]["picks"]:
        if p["originalOwner"] not in inputs["franchises"]:
            raise StateError(f"pick {p['pickId']} has unknown original owner")
    apply_historical_transfers(inputs, {p["pickId"]: p["originalOwner"] for p in inputs["picks"]["picks"]}, {})
    ids = [t["tradeId"] for t in inputs["trades"]["trades"]]
    if len(ids) != len(set(ids)):
        raise StateError("duplicate tradeId in trades.json")
    for t in inputs["trades"]["trades"]:
        if t["status"] not in TRADE_STATUSES:
            raise StateError(f"{t['tradeId']}: status must be one of {TRADE_STATUSES}")


# ---------------------------------------------------------------- assets
def asset_id(asset: dict) -> str:
    return f"pick:{asset['pickId']}" if asset["type"] == "pick" else f"player:{asset['playerKey']}"


def player_cap(inputs: dict, player_key: str) -> float:
    p = inputs["registry"].get(player_key)
    if p is not None:
        return float(p["projectedAuctionValue"])
    extra = inputs["extraPlayers"].get(player_key)
    if extra is not None:
        return float(extra.get("cap", 0))
    raise StateError(f"unknown player {player_key}")


def player_name(inputs: dict, player_key: str) -> str:
    p = inputs["registry"].get(player_key) or inputs["extraPlayers"].get(player_key)
    return p["name"] if p else player_key


def pick_label(pick: dict) -> str:
    return f"{pick['round']}.{int(pick['slot']):02d}"


def describe_asset(inputs: dict, asset: dict) -> dict:
    if asset["type"] == "pick":
        return {"t": "k", "k": asset["pickId"], "n": pick_label(inputs["pickIndex"][asset["pickId"]])}
    return {"t": "p", "k": asset["playerKey"], "n": player_name(inputs, asset["playerKey"]),
            "c": player_cap(inputs, asset["playerKey"])}


# ----------------------------------------------------------------- state
def apply_historical_transfers(inputs: dict, pick_owner: dict, history: dict) -> None:
    """Replay already-completed (pre-draft, last-season) pick swaps recorded in picks.json over the original
    owners. Each swap must move a pick FROM its then-current owner; the original owner is never overwritten.
    Entries are tagged historical so scenario views do not present them as simulated moves."""
    for tr in inputs["picks"].get("historicalTransfers", []):
        for a in tr["assets"]:
            pid = a["pickId"]
            if pid not in pick_owner:
                raise StateError(f"{tr['transferId']}: unknown pick {pid}")
            if pick_owner[pid] != a["from"]:
                raise StateError(f"{tr['transferId']}: {pid} is owned by {pick_owner[pid]}, not {a['from']}")
            if a["to"] not in inputs["franchises"]:
                raise StateError(f"{tr['transferId']}: unknown franchise {a['to']}")
            pick_owner[pid] = a["to"]
            history.setdefault(f"pick:{pid}", []).append(
                {"tradeId": tr["transferId"], "from": a["from"], "to": a["to"], "historical": True})


def initial_state(inputs: dict) -> dict:
    player_owner = {k["playerKey"]: t["franchiseId"] for t in inputs["freeze"]["teams"] for k in t["keepers"]}
    pick_owner = {p["pickId"]: p["originalOwner"] for p in inputs["picks"]["picks"]}
    history: dict = {}
    apply_historical_transfers(inputs, pick_owner, history)
    return {"playerOwner": player_owner, "pickOwner": pick_owner, "history": history, "completedPicks": {},
            "draftedPlayers": {}, "tradeResults": [], "activeTradeIds": [], "applied": set()}


def team_players(inputs, state, fid):
    return sorted(k for k, o in state["playerOwner"].items() if o == fid)


def team_cap(inputs, state, fid) -> float:
    return sum(player_cap(inputs, k) for k in team_players(inputs, state, fid))


def team_picks(state, fid):
    return sorted(k for k, o in state["pickOwner"].items() if o == fid)


def cap_band(inputs):
    return inputs["policy"]["officialFloor"], inputs["policy"]["officialCeiling"]


def floor_status(inputs, cap):
    floor, ceiling = cap_band(inputs)
    if cap < floor:
        return "UNDER_FLOOR"
    if cap > ceiling:
        return "OVER_CEILING"
    return "IN_BAND"


def cap_status(inputs, cap):
    """Constraint state of a cap total against the OFFICIAL band (not trade quality)."""
    floor, ceiling = cap_band(inputs)
    if cap > ceiling:
        return "OVER_CEILING"
    if cap == ceiling:
        return "AT_CEILING"
    if cap < floor:
        return "UNDER_FLOOR"
    if cap == floor:
        return "AT_FLOOR"
    if ceiling - cap <= NEAR_CEILING_ROOM:
        return "NEAR_CEILING"
    return "IN_RANGE"


def team_roster(inputs, state, fid):
    """Derived roster rows (cap desc, then name) -- the single source for roster, cap and count."""
    rows = [{"k": k, "n": player_name(inputs, k), "c": player_cap(inputs, k)} for k in team_players(inputs, state, fid)]
    return sorted(rows, key=lambda r: (-r["c"], r["n"]))


def _owner(state, asset):
    return state["pickOwner"].get(asset["pickId"]) if asset["type"] == "pick" else state["playerOwner"].get(asset["playerKey"])


def trade_assets(trade):
    """Flat list of {from, to, type, ...} transfers."""
    return list(trade["assets"])


def receives_by_team(trade):
    out = {}
    for a in trade_assets(trade):
        out.setdefault(a["to"], []).append(a)
    return out


# ------------------------------------------------------------ validation
def validate_trade(inputs, state, trade, active_ids):
    """Return (errors, warnings) against the CURRENT running state. Errors block application."""
    errors, warnings = [], []
    parts = set(trade["participants"])
    seen = {}
    deps = trade.get("dependsOn", [])
    broken_deps = [d for d in deps if d not in state["applied"]]
    ordering = [d for d in deps if d in inputs["tradeIndex"] and inputs["tradeIndex"][d]["order"] >= trade["order"]]
    if ordering:
        errors.append({"code": "DEPENDENCY_ORDER", "detail": f"depends on later/equal-order trades {ordering}"})
    if broken_deps:
        errors.append({"code": "BROKEN_DEPENDENCY", "detail": {
            "requires": deps, "missingOrNotApplied": broken_deps,
            "reason": ["inactive" if d not in active_ids else "not applied (invalid)" for d in broken_deps]}})
    for a in trade_assets(trade):
        aid = asset_id(a)
        if a["from"] not in parts or a["to"] not in parts or a["from"] == a["to"]:
            errors.append({"code": "BAD_PARTICIPANT", "detail": aid})
            continue
        if aid in seen:
            errors.append({"code": "DUPLICATE_ASSET", "detail": aid})
            continue
        seen[aid] = a["to"]
        if a["type"] == "pick":
            if a["pickId"] not in inputs["pickIndex"]:
                errors.append({"code": "UNKNOWN_PICK", "detail": a["pickId"]})
                continue
            if a["pickId"] in state["completedPicks"]:
                errors.append({"code": "PICK_ALREADY_USED", "detail": a["pickId"]})
                continue
        elif a["playerKey"] not in inputs["registry"] and a["playerKey"] not in inputs["extraPlayers"]:
            errors.append({"code": "UNKNOWN_PLAYER", "detail": a["playerKey"]})
            continue
        owner = _owner(state, a)
        if owner != a["from"] and not broken_deps:  # a missing upstream trade is already reported once
            errors.append({"code": "NOT_OWNED", "detail": {
                "asset": aid, "sender": a["from"], "actualOwner": owner}})
    counts = {fid: len(v) for fid, v in receives_by_team(trade).items()}
    if len(set(counts.get(f, 0) for f in parts)) > 1:
        warnings.append({"code": "ASSET_COUNT_UNBALANCED", "detail": {inputs["shorts"][f]: counts.get(f, 0) for f in sorted(parts)}})
    return errors, warnings


# -------------------------------------------------------------- resolve
def _apply_trade(inputs, state, trade, active_ids):
    errors, warnings = validate_trade(inputs, state, trade, active_ids)
    floor, ceiling = cap_band(inputs)
    parts = sorted(trade["participants"])
    before = {f: (team_cap(inputs, state, f), len(team_players(inputs, state, f))) for f in parts}
    result = {"tradeId": trade["tradeId"], "label": trade.get("label"), "status": trade["status"],
              "valid": not errors, "applied": False, "errors": errors, "warnings": warnings, "teams": {}}
    if not errors:
        for a in trade_assets(trade):
            aid = asset_id(a)
            if a["type"] == "pick":
                state["pickOwner"][a["pickId"]] = a["to"]
            else:
                state["playerOwner"][a["playerKey"]] = a["to"]
            state["history"].setdefault(aid, []).append({"tradeId": trade["tradeId"], "from": a["from"], "to": a["to"]})
        state["applied"].add(trade["tradeId"])
        result["applied"] = True
    for f in parts:
        cap_b, n_b = before[f]
        cap_a, n_a = team_cap(inputs, state, f), len(team_players(inputs, state, f))
        result["teams"][f] = {"capBefore": cap_b, "playerCapDelta": cap_a - cap_b, "capAfter": cap_a,
                              "roomToCeiling": ceiling - cap_a, "floorStatus": floor_status(inputs, cap_a),
                              "status": cap_status(inputs, cap_a), "toFloor": max(0, floor - cap_a),
                              "countBefore": n_b, "countAfter": n_a}
        if result["applied"]:
            if cap_a > ceiling:
                result["warnings"].append({"code": "CAP_OVER_CEILING", "detail": {"team": inputs["shorts"][f], "cap": cap_a, "ceiling": ceiling}})
            elif (cap_b > ceiling and cap_a > cap_b) or (cap_b < floor and cap_a < cap_b):
                result["warnings"].append({"code": "CAP_MOVES_AWAY_FROM_BAND", "detail": {"team": inputs["shorts"][f], "before": cap_b, "after": cap_a}})
            if n_a > MAX_KEEPERS:
                result["warnings"].append({"code": "ROSTER_COUNT_ABOVE_9", "detail": {
                    "team": inputs["shorts"][f], "count": n_a, "note": "confirm the final roster-size rule"}})
    state["tradeResults"].append(result)
    return result


def apply_draft_events(inputs, state):
    """Append-only DRAFT_PICK events: roster, availability, cap, pick completion, cursor. A trade that
    later moves an already-used pick (e.g. the 2.07 amendment) updates the pick's recorded owner only: the selection
    stays with whoever made it and the difference is listed in state["draftConflicts"] -- history is never undone."""
    held = {h["pickId"]: h for h in active_holds(inputs)}
    for ev in inputs["draft"].get("events", []):
        if ev["type"] != "DRAFT_PICK":
            raise StateError(f"unsupported draft event type {ev['type']}")
        pid, fid, key = ev["pickId"], ev["franchiseId"], ev["playerKey"]
        if pid in held:
            raise StateError(f"{pid}: on commissioner hold ({held[pid]['reason']}); resolve before recording its selection")
        if pid not in inputs["pickIndex"]:
            raise StateError(f"{pid}: unknown pick")
        if state["pickOwner"].get(pid) != fid:
            past = {inputs["pickIndex"][pid]["originalOwner"]}
            for tid in state["activeTradeIds"]:
                for x in inputs["tradeIndex"][tid]["assets"]:
                    if x.get("pickId") == pid:
                        past |= {x["from"], x["to"]}
            if fid not in past:
                raise StateError(f"{pid}: {fid} does not currently own this pick")
            state.setdefault("draftConflicts", []).append({"pickId": pid, "selector": fid, "scenarioOwner": state["pickOwner"].get(pid)})
        if pid in state["completedPicks"]:
            raise StateError(f"{pid}: pick already used")
        if key in state["playerOwner"]:
            raise StateError(f"{key}: player already owned")
        state["playerOwner"][key] = fid
        state["completedPicks"][pid] = {"franchiseId": fid, "playerKey": key, "eventId": ev.get("eventId")}
        state["draftedPlayers"][key] = pid


def active_holds(inputs: dict) -> list:
    """Commissioner holds on picks whose ownership is unresolved. A hold lifts once the transaction it waits on is
    decided (OFFICIAL or VOID) or the commissioner releases it (`released`); until then the pick cannot be recorded."""
    out = []
    for h in inputs["draft"].get("holds", []):
        if h.get("released"):  # commissioner released the pick for its CURRENT owner; the transaction stays pending
            continue
        t = inputs["tradeIndex"].get(h.get("waitingOn"))
        if t is None or t["status"] not in ("OFFICIAL", "VOID"):
            out.append(h)
    return out


def draft_summary(inputs: dict, state: dict) -> dict:
    """Everything the draft room shows, derived from the events + the post-trade pick ledger.

    Each completed pick carries the selecting team's RUNNING cap: capBefore -> capAfter, where the starting point is the
    team's post-trade cap before any draftee and each draftee adds his frozen Yahoo salary in pick order."""
    order = sorted(inputs["picks"]["picks"], key=lambda p: (p["round"], p["slot"]))
    floor, ceiling = cap_band(inputs)
    drafted_caps = {}
    for c in state["completedPicks"].values():
        drafted_caps[c["franchiseId"]] = drafted_caps.get(c["franchiseId"], 0) + player_cap(inputs, c["playerKey"])
    running = {f: team_cap(inputs, state, f) - drafted_caps.get(f, 0) for f in inputs["franchises"]}
    done = []
    for p in order:
        c = state["completedPicks"].get(p["pickId"])
        if c:
            ev = next(e for e in inputs["draft"]["events"] if e["pickId"] == p["pickId"])
            f, cap = c["franchiseId"], player_cap(inputs, c["playerKey"])
            before = running[f]
            running[f] = before + cap
            done.append({"pickId": p["pickId"], "label": pick_label(p), "franchiseId": f, "playerKey": c["playerKey"],
                         "name": player_name(inputs, c["playerKey"]), "cap": cap, "capBefore": before, "capAfter": running[f],
                         "room": ceiling - running[f], "status": cap_status(inputs, running[f]),
                         "rookie": bool(ev.get("rookie")),
                         "pos": ((inputs["registry"].get(c["playerKey"]) or inputs["extraPlayers"].get(c["playerKey"]) or {}).get("displayPosition") or "").replace(",", "/"),
                         "nba": (inputs["registry"].get(c["playerKey"]) or inputs["extraPlayers"].get(c["playerKey"]) or {}).get("nbaTeam", "")})
    holds_raw = active_holds(inputs)
    held_ids = {h["pickId"] for h in holds_raw}
    holds = [{"pickId": h["pickId"], "label": pick_label(inputs["pickIndex"][h["pickId"]]), "reason": h["reason"],
              "waitingOn": h.get("waitingOn"), "owner": state["pickOwner"][h["pickId"]]} for h in holds_raw]
    left = {}
    pending = [p for p in order if p["pickId"] not in state["completedPicks"]]
    for p in pending:
        left[state["pickOwner"][p["pickId"]]] = left.get(state["pickOwner"][p["pickId"]], 0) + 1

    def slot(p):
        o = state["pickOwner"][p["pickId"]]
        return {"pickId": p["pickId"], "label": pick_label(p), "owner": o, "held": p["pickId"] in held_ids,
                "cap": running[o], "room": ceiling - running[o], "picksLeft": left.get(o, 0)}
    cur = pending[0] if pending else None
    return {"status": inputs["draft"].get("status"), "completed": done, "total": len(order), "remaining": len(pending),
            "rookies": sum(1 for d in done if d["rookie"]), "cap": {"floor": floor, "ceiling": ceiling},
            "cursor": slot(cur) if cur else None, "upNext": [slot(p) for p in pending[1:6]],
            "latest": done[-1] if done else None, "holds": holds}


def draft_cursor(inputs, state):
    for p in sorted(inputs["picks"]["picks"], key=lambda p: (p["round"], p["slot"])):
        if p["pickId"] not in state["completedPicks"]:
            return p["pickId"]
    return None


def resolve(inputs: dict, selected=(), mode: str = "OFFICIAL") -> dict:
    """Replay official trades (+ selected scenario trades in SCENARIO mode), then draft events."""
    official = sorted((t for t in inputs["trades"]["trades"] if t["status"] == "OFFICIAL"), key=lambda t: t["order"])
    chosen = []
    if mode == "SCENARIO":
        for tid in selected:
            t = inputs["tradeIndex"].get(tid)
            if t is None:
                raise StateError(f"unknown trade {tid}")
            if t["status"] not in SELECTABLE_STATUSES:
                raise StateError(f"{tid} has status {t['status']} and is not selectable as a scenario trade")
            chosen.append(t)
        chosen.sort(key=lambda t: t["order"])
    active = official + chosen
    active_ids = {t["tradeId"] for t in active}
    state = initial_state(inputs)
    state["activeTradeIds"] = [t["tradeId"] for t in active]
    for t in active:
        res = _apply_trade(inputs, state, t, active_ids)
        if t["status"] == "OFFICIAL" and not res["applied"]:
            # An official transaction must never be silently dropped: surface the exact blocker.
            raise StateError(f"official trade {t['tradeId']} failed validation: {res['errors']}")
    apply_draft_events(inputs, state)

    # Global governance note: pre-draft window allows 1 trade per team (a trade may involve 2+ teams).
    counts = {}
    for t in active:
        if t.get("amends"):  # a correction to an earlier trade is not a new pre-draft trade
            continue
        for f in t["participants"]:
            counts[f] = counts.get(f, 0) + 1
    state["windowWarnings"] = [
        {"code": "PRE_DRAFT_TRADE_LIMIT", "detail": {"team": inputs["shorts"][f], "trades": n,
                                                      "rule": "up to 1 trade per team in the pre-draft window; confirm these fold into one multi-team transaction"}}
        for f, n in sorted(counts.items()) if n > 1]
    state["mode"] = mode
    state["selected"] = [t["tradeId"] for t in chosen]
    return state


# --------------------------------------------------------------- reports
def team_report(inputs, state, fid, baseline=None):
    baseline = baseline or initial_state(inputs)
    floor, ceiling = cap_band(inputs)
    roster = team_roster(inputs, state, fid)
    cap = sum(r["c"] for r in roster)  # cap, count and roster all come from this one derived roster
    base_keys = set(team_players(inputs, baseline, fid))
    return {"franchiseId": fid, "short": inputs["shorts"][fid], "cap": cap, "room": ceiling - cap,
            "toFloor": max(0, floor - cap), "status": cap_status(inputs, cap),
            "floorStatus": floor_status(inputs, cap), "count": len(roster),
            "roster": roster, "inKeys": [r["k"] for r in roster if r["k"] not in base_keys],
            "baselineCap": team_cap(inputs, baseline, fid), "baselineCount": len(base_keys),
            "picks": [pick_label(inputs["pickIndex"][p]) for p in team_picks(state, fid)],
            "pickIds": team_picks(state, fid)}


def fold_team(inputs, state, fid):
    """Net team-level roll-up of the applied chain, keeping governance-relevant pass-through assets."""
    ins, outs = {}, {}
    order = []
    for tid in state["activeTradeIds"]:
        if tid not in state["applied"]:
            continue
        t = inputs["tradeIndex"][tid]
        if fid not in t["participants"]:
            continue
        for a in trade_assets(t):
            aid = asset_id(a)
            if a["to"] == fid:
                ins[aid] = a
                order.append(aid)
            if a["from"] == fid:
                outs[aid] = a
                order.append(aid)
    pass_ids = [aid for aid in dict.fromkeys(order) if aid in ins and aid in outs]
    def chain(aid):
        owners = [state["history"][aid][0]["from"]] + [h["to"] for h in state["history"][aid]]
        return [inputs["shorts"][o] for o in owners]
    def show(aid, a):
        return describe_asset(inputs, a)
    in_only = [show(a, ins[a]) for a in dict.fromkeys(order) if a in ins and a not in outs]
    out_only = [show(a, outs[a]) for a in dict.fromkeys(order) if a in outs and a not in ins]
    passes = [{"asset": describe_asset(inputs, ins[a]), "chain": chain(a)} for a in pass_ids]
    cap_in = sum(x.get("c", 0) for x in in_only if x["t"] == "p")
    cap_out = sum(x.get("c", 0) for x in out_only if x["t"] == "p")
    return {"in": in_only, "out": out_only, "pass": passes, "playerCapIn": cap_in, "playerCapOut": cap_out,
            "playerCapDelta": cap_in - cap_out,
            "tradeIds": [t for t in state["activeTradeIds"] if t in state["applied"] and fid in inputs["tradeIndex"][t]["participants"]]}


def pick_table(inputs, state):
    rows = []
    for p in sorted(inputs["picks"]["picks"], key=lambda p: (p["round"], p["slot"])):
        aid = f"pick:{p['pickId']}"
        hist = state["history"].get(aid, [])
        rows.append({"pickId": p["pickId"], "label": pick_label(p), "original": p["originalOwner"],
                     "current": state["pickOwner"][p["pickId"]], "moved": bool(hist),
                     "history": [{"tradeId": h["tradeId"], "from": h["from"], "to": h["to"], "historical": bool(h.get("historical"))} for h in hist],
                     "completed": p["pickId"] in state["completedPicks"]})
    return rows


# -------------------------------------------------------------- scenarios
def selectable_trades(inputs):
    return sorted((t for t in inputs["trades"]["trades"] if t["status"] in SELECTABLE_STATUSES), key=lambda t: t["order"])


def scenario_key(ids):
    return ",".join(sorted(ids))


def scenario_view(inputs, selected):
    """Compact, JSON-serialisable result of one scenario (what the page renders)."""
    state = resolve(inputs, selected, "SCENARIO" if selected else "OFFICIAL")
    base = initial_state(inputs)
    moved_teams = sorted({f for r in state["tradeResults"] if r["applied"] for f in r["teams"]}
                         | {c["franchiseId"] for c in state["completedPicks"].values()})
    teams = {}
    for fid in moved_teams:
        rep = team_report(inputs, state, fid, base)
        fold = fold_team(inputs, state, fid)
        rep["fold"] = fold
        teams[fid] = rep
    return {
        "key": scenario_key(selected),
        "selected": sorted(selected),
        "trades": {r["tradeId"]: {k: r[k] for k in ("valid", "applied", "errors", "warnings", "teams")} for r in state["tradeResults"]},
        "teams": teams,
        "picks": [r for r in pick_table(inputs, state) if any(not h["historical"] for h in r["history"])],
        "windowWarnings": state["windowWarnings"],
    }


def enumerate_scenarios(inputs):
    ids = [t["tradeId"] for t in selectable_trades(inputs)]
    views = {}
    for n in range(len(ids) + 1):
        for combo in itertools.combinations(ids, n):
            v = scenario_view(inputs, list(combo))
            views[v["key"]] = v
    return views


# ------------------------------------------------------------------ audit
def audit_official(inputs: dict) -> dict:
    """Reconcile the OFFICIAL state (freeze + historical swaps + official trades): hard integrity checks that must
    all hold, plus rule violations REPORTED (never silently corrected)."""
    state = resolve(inputs, (), "OFFICIAL")
    base = initial_state(inputs)
    all_picks = sorted(p["pickId"] for p in inputs["picks"]["picks"])
    listed_picks = sorted(k for f in inputs["franchises"] for k in team_picks(state, f))
    listed_players = sorted(k for f in inputs["franchises"] for k in team_players(inputs, state, f))
    teams = {}
    for f in sorted(inputs["franchises"]):
        roster = team_roster(inputs, state, f)
        teams[f] = {"short": inputs["shorts"][f], "cap": team_cap(inputs, state, f), "sumOfPlayers": sum(r["c"] for r in roster),
                    "count": len(roster), "picks": [pick_label(inputs["pickIndex"][p]) for p in team_picks(state, f)]}
    floor, ceiling = cap_band(inputs)
    checks = {
        "everyPlayerHasOneOwner": len(listed_players) == len(set(listed_players)) == len(state["playerOwner"])
                                  == len(base["playerOwner"]) + len(state["draftedPlayers"]),
        "everyDraftSelectionOnceAndKeptBySelector": len(state["completedPicks"]) == len(state["draftedPlayers"]) == len(inputs["draft"].get("events", []))
                                  and all(state["playerOwner"][c["playerKey"]] == c["franchiseId"]
                                          and (c["franchiseId"] == state["pickOwner"][pid]
                                               or pid in {x["pickId"] for x in state.get("draftConflicts", [])})  # a later trade moved the used pick: owner label only
                                          for pid, c in state["completedPicks"].items()),
        "everyPickHasOneOwner": listed_picks == all_picks and len(all_picks) == 48,
        "everyOfficialTradeApplied": all(r["applied"] and not r["errors"] for r in state["tradeResults"])
                                     and [r["tradeId"] for r in state["tradeResults"]] == state["activeTradeIds"],
        "dependenciesBeforeDependents": all(inputs["tradeIndex"][d]["order"] < inputs["tradeIndex"][t]["order"]
                                            for t in state["activeTradeIds"] for d in inputs["tradeIndex"][t].get("dependsOn", [])),
        "capEqualsSumOfPlayers": all(v["cap"] == v["sumOfPlayers"] for v in teams.values()),
        "playerPoolUnchanged": set(state["playerOwner"]) - set(state["draftedPlayers"]) == set(base["playerOwner"]),
        "tradesBalanced": not [w for r in state["tradeResults"] for w in r["warnings"] if w["code"] == "ASSET_COUNT_UNBALANCED"],
    }
    violations = []
    for r in state["tradeResults"]:
        for w in r["warnings"]:
            if w["code"] != "ASSET_COUNT_UNBALANCED":
                violations.append({"tradeId": r["tradeId"], **w})
    violations += [{"tradeId": None, **w} for w in state["windowWarnings"]]
    for f, v in teams.items():
        if v["cap"] > ceiling:
            violations.append({"code": "CAP_OVER_CEILING", "detail": {"team": v["short"], "cap": v["cap"], "ceiling": ceiling}})
        if v["cap"] < floor:
            violations.append({"code": "CAP_UNDER_FLOOR", "detail": {"team": v["short"], "cap": v["cap"], "floor": floor}})
        held_players = v["count"] - sum(1 for k in team_players(inputs, state, f) if k in state["draftedPlayers"])
        if held_players > MAX_KEEPERS:  # the 9-keeper limit counts kept/traded players, not draftees
            violations.append({"code": "FINAL_ROSTER_ABOVE_9", "detail": {"team": v["short"], "count": held_players}})
    return {"checks": checks, "violations": violations, "teams": teams, "tradeOrder": state["activeTradeIds"]}


# -------------------------------------------------------------- snapshots
def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def make_snapshot(inputs, kind: str) -> dict:
    """Immutable checkpoint: input digests + the derived OFFICIAL ownership/cap it reproduces."""
    if kind not in SNAPSHOT_KINDS:
        raise StateError(f"snapshot kind must be one of {SNAPSHOT_KINDS}")
    state = initial_state(inputs) if kind == "KEEPER_FREEZE" else resolve(inputs, (), "OFFICIAL")
    return {
        "kind": kind,
        "season": inputs["freeze"]["season"],
        "keeperStatus": inputs["freeze"]["status"],
        "inputDigests": {"keeperFreeze": _digest(inputs["freeze"]), "picks": _digest(inputs["picks"]),
                         "officialTrades": _digest([t for t in inputs["trades"]["trades"] if t["status"] == "OFFICIAL"]),
                         "draftEvents": _digest(inputs["draft"].get("events", []))},
        "playerOwner": dict(sorted(state["playerOwner"].items())),
        "pickOwner": dict(sorted(state["pickOwner"].items())),
        "teamCaps": {f: team_cap(inputs, state, f) for f in sorted(inputs["franchises"])},
        "capBand": {"floor": cap_band(inputs)[0], "ceiling": cap_band(inputs)[1]},
        "teams": {f: checkpoint_team(inputs, state, f) for f in sorted(inputs["franchises"])},
    }


def checkpoint_team(inputs, state, fid) -> dict:
    floor, ceiling = cap_band(inputs)
    cap = team_cap(inputs, state, fid)
    return {"short": inputs["shorts"][fid], "keeperCount": len(team_players(inputs, state, fid)), "keeperCap": cap,
            "toFloor": max(0, floor - cap), "roomToCeiling": ceiling - cap, "status": cap_status(inputs, cap)}


def lock_keepers(freeze: dict, locked_at: str, checkpoint: dict | None = None) -> dict:
    """Return a LOCKED copy of a keeper freeze with its immutability digest. Refuses to re-lock.
    `checkpoint` (official band, per-team keeper caps, provenance) is recorded as-is."""
    if freeze.get("status") == "locked":
        raise StateError("keeper freeze is already locked (immutable)")
    out = json.loads(json.dumps(freeze))
    out["status"] = "locked"
    out["statusNote"] = "OFFICIAL KEEPER FREEZE. Final keeper declarations; immutable. Later changes are official trades / draft events."
    out["source"] = "final keeper declarations"
    if checkpoint:
        out["checkpoint"] = checkpoint
    out["lockedAt"] = locked_at
    out["lockDigest"] = _digest({"teams": out["teams"], "season": out["season"]})
    return out


def verify_lock(freeze: dict) -> bool:
    return freeze.get("status") == "locked" and freeze.get("lockDigest") == _digest({"teams": freeze["teams"], "season": freeze["season"]})
