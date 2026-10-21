#!/usr/bin/env python3
"""Regular-season state: three separate layers.

    A. HISTORICAL OFFICIAL  = keeper freeze + pre-draft trades + 48-pick draft ledger      (league_state.resolve)
                              checkpointed once in data/2026-27/snapshots/POST_DRAFT.json (immutable)
    B. CURRENT SEASON       = latest VERIFIED roster snapshot (data/2026-27/rosters/)
                              + COMPLETED in-season transactions effective after that snapshot
    C. TRADE LAB SCENARIO   = B + selected PROPOSED/AGREED in-season proposals             (never written anywhere)

In-season transactions live in data/2026-27/season_transactions.json, NOT in trades.json: the pre-draft ledger is
replayed before the draft events, so an in-season trade of a drafted player cannot belong there. Salaries come from the
frozen 2026-27 table (salary_freeze.json); the draft-night 12-player count is not a current-season constraint.

    python3 scripts/season_state.py status                 # snapshot, transactions, payroll, checkpoint findings
    python3 scripts/season_state.py freeze-salaries        # one-time: write salary_freeze.json (refuses to overwrite)
    python3 scripts/season_state.py post-draft-snapshot    # one-time: write snapshots/POST_DRAFT.json (refuses to change it)
    python3 scripts/season_state.py init-rosters           # one-time: first roster snapshot = official draft-night rosters
    python3 scripts/season_state.py record-checkpoint POST_TRADE_DEADLINE --date YYYY-MM-DD   # after a verified import
Standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import league_state as ls  # noqa: E402

DATA_DIR = ls.DATA_DIR
TXN_PATH = os.path.join(DATA_DIR, "season_transactions.json")
CHECKPOINTS_PATH = os.path.join(DATA_DIR, "cap_checkpoints.json")
SALARY_PATH = os.path.join(DATA_DIR, "salary_freeze.json")
POST_DRAFT_PATH = os.path.join(DATA_DIR, "snapshots", "POST_DRAFT.json")
ROSTER_DIR = os.path.join(DATA_DIR, "rosters")
ROSTER_INDEX = os.path.join(ROSTER_DIR, "index.json")

TXN_STATUSES = ("PROPOSED", "AGREED", "COMPLETED", "VOID")
SELECTABLE = ("PROPOSED", "AGREED")
SLOTS_IL = ("IL", "IL+")
TXN_ORDER_BASE = 1000  # in-season transactions always order after every pre-draft trade


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ts(value: str) -> str:
    """Normalise a date or date-time to a comparable UTC ISO timestamp."""
    if value is None:
        return None
    return value if "T" in value else value + "T00:00:00Z"


# ------------------------------------------------------------------ inputs
def load_season(inputs: dict, data_dir: str = DATA_DIR) -> dict:
    """Attach the season layer to `inputs` (returns a shallow copy; the pre-draft inputs are untouched)."""
    si = dict(inputs)
    si["dataDir"] = data_dir
    pc = inputs["policy"].get("payrollCounting") or {}
    si["capCountTop"] = pc.get("n") if pc.get("rule") == "TOP_N_SALARIES" else None
    txn_doc = _load(os.path.join(data_dir, "season_transactions.json"))
    txns = []
    for i, t in enumerate(txn_doc["transactions"]):
        if t["status"] not in TXN_STATUSES:
            raise ls.StateError(f"{t['txnId']}: status must be one of {TXN_STATUSES}")
        txns.append({**t, "tradeId": t["txnId"], "order": TXN_ORDER_BASE + i, "phase": "IN_SEASON",
                     "dependsOn": t.get("dependsOn", [])})
    ids = [t["txnId"] for t in txns]
    if len(ids) != len(set(ids)) or set(ids) & set(inputs["tradeIndex"]):
        raise ls.StateError("duplicate or colliding in-season transaction id")
    si["tradeIndex"] = {**inputs["tradeIndex"], **{t["txnId"]: t for t in txns}}
    si["seasonTxns"] = txns
    idx = _load(os.path.join(data_dir, "rosters", "index.json"))
    si["rosterIndex"] = idx
    si["rosterSnapshot"] = _load(os.path.join(data_dir, "rosters", idx["current"])) if idx.get("current") else None
    si["checkpoints"] = _load(os.path.join(data_dir, "cap_checkpoints.json"))
    pd = os.path.join(data_dir, "snapshots", "POST_DRAFT.json")
    si["postDraft"] = _load(pd) if os.path.exists(pd) else None
    return si


def snapshot_owner(snapshot: dict) -> dict:
    out = {}
    for fid, rows in snapshot["teams"].items():
        for r in rows:
            if r["playerKey"] in out:
                raise ls.StateError(f"roster snapshot {snapshot['snapshotId']}: {r['playerKey']} on two teams")
            out[r["playerKey"]] = fid
    return out


def snapshot_slots(snapshot: dict) -> dict:
    return {r["playerKey"]: r.get("slot") for rows in snapshot["teams"].values() for r in rows}


def snapshot_status(snapshot: dict) -> dict:
    return {r["playerKey"]: r["status"] for rows in snapshot["teams"].values() for r in rows if r.get("status")}


RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "roster_rules.json")


def _positions(si, key, base):
    raw = (ls.player_meta(si, key).get("displayPosition") or "").replace("/", ",")
    return {p.strip() for p in raw.split(",")} & set(base)


def _fillable(players: dict, slots: dict) -> list:
    """Maximum assignment of players to lineup slots (augmenting paths); -> the slots that stay empty."""
    match = {}

    def place(slot, seen):
        for p, pos in players.items():
            if p in seen or not (pos & set(slots[slot])):
                continue
            seen.add(p)
            if p not in match or place(match[p], seen):
                match[p] = slot
                return True
        return False
    return [s for s in slots if not place(s, set())]


def roster_checks(si, state, fid, rules=None) -> dict:
    """The countable anti-tank roster limits (docs/LEAGUE_RULES_MODEL.md, roster / anti-tank governance), as evidence
    for review. Levels: ok / watch (at a limit, or inside a commissioner exception) / over. Never a tanking verdict."""
    rules = rules or _load(RULES_PATH)
    base = rules["positions"]
    keys = ls.team_players(si, state, fid)
    slots, status = state.get("slots", {}), state.get("status", {})
    nm = lambda k: ls.player_name(si, k)  # noqa: E731
    on_il = [k for k in keys if slots.get(k) in SLOTS_IL]
    out = [k for k in keys if k not in on_il and status.get(k) in rules["longTermInjured"]["outStatuses"]]
    injured = on_il + out
    lim = rules["longTermInjured"]["max"]
    healthy = {k: _positions(si, k, base) for k in keys if k not in injured}
    single = [k for k, v in healthy.items() if len(v) == 1]  # injured players cannot contribute: not counted (owner, 2026-10-19)
    sp = rules["singlePosition"]
    cover = {p: sum(1 for v in healthy.values() if p in v) for p in base}
    short = [p for p in base if cover[p] < rules["minPerPosition"]]
    combos = rules.get("combos", {})
    combo_cover = {c: sum(1 for v in healthy.values() if v & set(ps)) for c, ps in combos.items()}
    short_combo = [c for c in combos if combo_cover[c] < rules.get("minPerCombo", 0)]
    empty = _fillable(healthy, rules["lineupSlots"])
    cap_il = sum(r["c"] for r in ranked_roster(si, state, fid) if r["k"] in injured and not r["x"])
    return {
        "injured": {"count": len(injured), "il": len(on_il), "out": len(out), "max": lim,
                    "level": "over" if len(injured) > lim else "watch" if len(injured) == lim else "ok",
                    "players": [nm(k) for k in injured], "countedCap": cap_il},
        "singlePosition": {"count": len(single), "max": sp["max"], "maxWithCombo": sp["maxWithComboTags"],
                           "level": "over" if len(single) > sp["maxWithComboTags"] else "watch" if len(single) > sp["max"] else "ok",
                           "players": [nm(k) for k in single]},
        "coverage": {"byPosition": cover, "min": rules["minPerPosition"], "short": short,
                     "byCombo": combo_cover, "comboMin": rules.get("minPerCombo"), "comboOf": combos, "shortCombo": short_combo,
                     "level": "over" if short or short_combo else "ok"},
        "lineup": {"slots": len(rules["lineupSlots"]), "filled": len(rules["lineupSlots"]) - len(empty), "empty": empty,
                   "level": "over" if empty else "ok"},
    }


# ------------------------------------------------------------------- state
def pending_completed(si: dict) -> list:
    """COMPLETED transactions not yet reflected in the current verified snapshot (applied on top of it)."""
    since = ts(si["rosterSnapshot"]["verifiedAt"])
    return [t for t in si["seasonTxns"] if t["status"] == "COMPLETED" and ts(t["effectiveAt"]) > since]


def reflected_completed(si: dict) -> list:
    since = ts(si["rosterSnapshot"]["verifiedAt"])
    return [t for t in si["seasonTxns"] if t["status"] == "COMPLETED" and ts(t["effectiveAt"]) <= since]


def _replay_reflected(si: dict, official: dict) -> dict:
    """Completed trades a verified snapshot already contains, replayed from the post-draft rosters in ledger order --
    for their history only (who moved, payroll before/after at the time). Ownership still comes from the snapshot."""
    replay = {"playerOwner": dict(official["playerOwner"]), "pickOwner": dict(official["pickOwner"]), "history": {},
              "completedPicks": official["completedPicks"], "draftedPlayers": official["draftedPlayers"],
              "tradeResults": [], "activeTradeIds": [], "applied": set()}
    done = reflected_completed(si)
    ids = {t["tradeId"] for t in done}
    for t in done:
        res = ls._apply_trade(si, replay, t, ids)
        res["reflected"] = True
    replay["activeTradeIds"] = [t["tradeId"] for t in done]
    return replay


def season_state(si: dict, selected=()) -> dict:
    """Layer B (no selection) or C (selected proposals). Reads, never writes."""
    official = ls.resolve(si, (), "OFFICIAL")  # layer A: draft archive, pick ledger, draft tags
    snap = si["rosterSnapshot"]
    past = _replay_reflected(si, official)  # completed trades already inside the snapshot: history, never re-applied
    state = {"playerOwner": snapshot_owner(snap), "pickOwner": dict(official["pickOwner"]), "history": past["history"],
             "completedPicks": official["completedPicks"], "draftedPlayers": official["draftedPlayers"],
             "tradeResults": past["tradeResults"], "activeTradeIds": [], "applied": set(past["applied"]),
             "slots": snapshot_slots(snap), "status": snapshot_status(snap)}
    chosen = []
    for tid in selected:
        t = si["tradeIndex"].get(tid)
        if t is None or t.get("phase") != "IN_SEASON":
            raise ls.StateError(f"unknown in-season proposal {tid}")
        if t["status"] not in SELECTABLE:
            raise ls.StateError(f"{tid} has status {t['status']} and is not selectable as a scenario trade")
        chosen.append(t)
    done = pending_completed(si)
    active = done + sorted(chosen, key=lambda t: t["order"])
    active_ids = {t["tradeId"] for t in active}
    state["activeTradeIds"] = past["activeTradeIds"] + [t["tradeId"] for t in active]
    for t in active:
        res = ls._apply_trade(si, state, t, active_ids)
        if t["status"] == "COMPLETED" and not res["applied"]:
            raise ls.StateError(f"completed transaction {t['tradeId']} does not apply to the verified roster: {res['errors']}")
    state["windowWarnings"] = []
    state["mode"] = "SCENARIO" if chosen else "CURRENT"
    state["selected"] = [t["tradeId"] for t in chosen]
    return state


def post_draft_state(si: dict) -> dict:
    """Layer A as a baseline for current-season deltas (same ownership as snapshots/POST_DRAFT.json)."""
    return ls.resolve(si, (), "OFFICIAL")


def injured_keys(state, keys) -> set:
    """Players who cannot contribute right now: in an IL / IL+ slot, or Yahoo lists them Out / injured / out for the season."""
    out_status = set(_load(RULES_PATH)["longTermInjured"]["outStatuses"])
    slots, status = state.get("slots", {}), state.get("status", {})
    return {k for k in keys if slots.get(k) in SLOTS_IL or status.get(k) in out_status}


def rank_roster(si, rows, inj) -> list:
    """Salary order (desc), healthy before injured on equal salary, then name; `x` marks rows beyond the counted nine."""
    n = si.get("capCountTop")
    rows = sorted(rows, key=lambda r: (-r["c"], r["k"] in inj, r["n"]))
    for i, r in enumerate(rows):
        r["x"] = bool(n) and i >= n
    return rows


def ranked_roster(si, state, fid) -> list:
    """One team's rows as the cards rank them (see rank_roster) -- for checks and reports that need the same counted set."""
    rows = ls.team_roster(si, state, fid)
    return rank_roster(si, rows, injured_keys(state, [r["k"] for r in rows]))


def team_view(si, state, fid, base) -> dict:
    rep = ls.team_report(si, state, fid, base)
    rep["fold"] = ls.fold_team(si, state, fid)
    slots = state.get("slots", {})
    status = state.get("status", {})
    for r in rep["roster"]:
        r["s"] = slots.get(r["k"])
        if status.get(r["k"]):
            r["st"] = status[r["k"]]  # Yahoo player status as observed (P, Q, D, O, INJ, OFS, ...)
        meta = ls.player_meta(si, r["k"])  # display data for players the original board does not list (in-season adds)
        r["pos"], r["nba"] = (meta.get("displayPosition") or "").replace(",", "/"), meta.get("nbaTeam") or ""
    rep["il"] = sum(1 for r in rep["roster"] if r["s"] in SLOTS_IL)
    # Injured = an IL slot OR a long-term Yahoo status (Out / INJ / OFS) even if the manager has not moved him to IL.
    # Everyone competes for the counted nine on salary alone; when salaries tie at the boundary a healthy player is shown
    # as the counted one (the payroll number is identical), so an injured $0 player never "uses up" a counted spot by name order.
    inj = injured_keys(state, [r["k"] for r in rep["roster"]])
    rep["roster"] = rank_roster(si, rep["roster"], inj)
    rep["cap"] = sum(r["c"] for r in rep["roster"] if not r["x"])           # unchanged: only ties were reordered
    # "healthy" is the counted payroll without the injured; ilCap is the IL slots' share (the IL group's "N counted")
    rep["ilCap"] = sum(r["c"] for r in rep["roster"] if r["s"] in SLOTS_IL and not r["x"])
    rep["injuredCap"] = sum(r["c"] for r in rep["roster"] if r["k"] in inj and not r["x"])
    rep["healthyCap"] = rep["cap"] - rep["injuredCap"]
    rep["checks"] = roster_checks(si, state, fid)
    rep["outKeys"] = sorted(set(ls.team_players(si, base, fid)) - {r["k"] for r in rep["roster"]})
    # a trade acquisition (⇄) is not a free-agent add: only players received in a trade count as traded in
    traded_in = {a["k"] for a in rep["fold"]["in"] if a["t"] == "p"}
    traded_out = {a["k"] for a in rep["fold"]["out"] if a["t"] == "p"}
    added = [k for k in rep["inKeys"] if k not in traded_in]
    rep["inKeys"] = [k for k in rep["inKeys"] if k in traded_in]
    rep["added"] = [ls.describe_asset(si, {"type": "player", "playerKey": k}) for k in added]
    rep["dropped"] = [ls.describe_asset(si, {"type": "player", "playerKey": k}) for k in rep["outKeys"] if k not in traded_out]
    return rep


def season_view(si, selected=()) -> dict:
    """JSON-serialisable view of layer B/C in the shape the page already renders (all 16 teams)."""
    state = season_state(si, selected)
    base = post_draft_state(si)
    return {
        "key": ls.scenario_key(selected),
        "selected": sorted(selected),
        "trades": {r["tradeId"]: {k: r[k] for k in ("valid", "applied", "errors", "warnings", "teams")} for r in state["tradeResults"]},
        "teams": {fid: team_view(si, state, fid, base) for fid in sorted(si["franchises"])},
        "picks": [],  # in-season trades move players only; the pick ledger is draft history (layer A)
        "windowWarnings": [],
    }


def selectable(si) -> list:
    return [t for t in si["seasonTxns"] if t["status"] in SELECTABLE]


def enumerate_views(si) -> dict:
    ids = [t["txnId"] for t in selectable(si)]
    views = {}
    for n in range(len(ids) + 1):
        for combo in itertools.combinations(ids, n):
            v = season_view(si, list(combo))
            views[v["key"]] = v
    return views


# ------------------------------------------------------------- checkpoints
def checkpoint_findings(si, current_state=None) -> list:
    """Undercap checkpoints (Dynasty-Rule-Oct-2025 'Salary Cap Violator'): payroll is checked after the draft and after
    the trade deadline. Under the floor at BOTH (without demonstrable improvement: payroll up from season start to end
    via trade or claim) carries a +5W final-record penalty -- decided by the commissioner, never applied here.

    A finding is DERIVED from the immutable checkpoint snapshot, so it survives later payroll changes."""
    floor, ceiling = ls.cap_band(si)
    cur = current_state or season_state(si)
    out = []
    decisions = {(d["checkpoint"], d["franchiseId"]): d for d in si["checkpoints"].get("commissionerDecisions", [])}
    defs = {c["id"]: c for c in si["checkpoints"]["checkpoints"]}
    recorded = {}
    for c in si["checkpoints"]["checkpoints"]:
        if c.get("snapshot"):
            snap = _load(os.path.join(si.get("dataDir", DATA_DIR), c["snapshot"]))
            # payroll re-derived from the checkpoint's frozen OWNERSHIP under the season counting rule (top N salaries)
            owned = {}
            for k, f in snap["playerOwner"].items():
                owned.setdefault(f, []).append(k)
            recorded[c["id"]] = {"floor": snap["capBand"]["floor"],
                                 "caps": {f: ls.counted_cap(si, owned.get(f, [])) for f in si["franchises"]}}
    pd = recorded.get("POST_DRAFT")
    if not pd:
        return out
    for fid in sorted(si["franchises"]):
        at = pd["caps"][fid]
        if at >= pd["floor"]:
            continue
        now = ls.team_cap(si, cur, fid)
        dl = recorded.get("POST_TRADE_DEADLINE")
        deadline_cap = dl["caps"][fid] if dl else None
        repeat = deadline_cap is not None and deadline_cap < dl["floor"]
        improved = (deadline_cap if deadline_cap is not None else now) > at
        if repeat:
            status = "REPEAT_UNDER_FLOOR_REVIEW"  # potential +5W: commissioner decides (improvement exemption)
        else:
            status = "FINDING_RECORDED"
        d = decisions.get(("POST_DRAFT", fid)) or decisions.get(("POST_TRADE_DEADLINE", fid))
        out.append({
            "franchiseId": fid, "short": si["shorts"][fid], "checkpoint": "POST_DRAFT",
            "checkpointDate": defs["POST_DRAFT"]["date"], "floor": pd["floor"], "capAtCheckpoint": at,
            "shortfall": pd["floor"] - at, "currentCap": now, "currentGap": max(0, floor - now),
            "changeSinceCheckpoint": now - at,
            "direction": "IMPROVING" if now > at else ("WORSENING" if now < at else "UNCHANGED"),
            "deadlineCheckpoint": {"date": defs["POST_TRADE_DEADLINE"].get("date"), "recorded": dl is not None,
                                   "cap": deadline_cap, "underFloor": repeat if dl else None},
            "improvedSinceCheckpoint": improved, "status": status,
            "penalty": d["decision"] if d else None,  # only a recorded commissioner decision, never derived
        })
    return out


def trade_toward_band(si, state, fid, delta) -> dict:
    """Would a trade changing `fid`'s payroll by `delta` satisfy the trade-time direction rule? (negotiation aid)"""
    cap_b = ls.team_cap(si, state, fid)
    w = ls.in_season_cap_checks(si, fid, cap_b, cap_b + delta)
    return {"before": cap_b, "after": cap_b + delta, "ok": not any(x["code"] == "CAP_TRADE_LEAVES_BAND" for x in w), "warnings": w}


# --------------------------------------------------------------- one-time
def make_salary_freeze(inputs, frozen_at: str) -> dict:
    sal = {k: float(p["projectedAuctionValue"]) for k, p in inputs["registry"].items()}
    for k, p in inputs["extraPlayers"].items():
        sal[k] = float(p.get("cap", 0))
    doc = {"season": inputs["freeze"]["season"], "frozenAt": frozen_at,
           "note": "2026-27 salaries, frozen when the draft completed. player_cap() reads this before the Yahoo registry, "
                   "so a later Yahoo refresh never changes payroll. Provisional (not-yet-Yahoo) players keep their draft "
                   "salary even after they are linked to a Yahoo id.",
           "source": {"registry": "data/yahoo/player_registry.json", "provisional": "data/2026-27/provisional_players.json"},
           "salaries": dict(sorted(sal.items()))}
    doc["digest"] = ls._digest(doc["salaries"])
    return doc


def make_post_draft_snapshot(inputs, date: str) -> dict:
    snap = ls.make_snapshot(inputs, "POST_DRAFT")
    snap["checkpoint"] = {"id": "POST_DRAFT", "date": date,
                          "note": "Official draft-night state: keeper freeze + pre-draft trades + all 48 selections. Immutable."}
    snap["draftSelections"] = len(inputs["draft"]["events"])
    snap["rookies"] = sum(1 for e in inputs["draft"]["events"] if e.get("rookie"))
    return snap


def make_initial_roster_snapshot(inputs, verified_at: str) -> dict:
    official = ls.resolve(inputs, (), "OFFICIAL")
    teams = {fid: [{"playerKey": k, "name": ls.player_name(inputs, k), "slot": None}
                   for k in ls.team_players(inputs, official, fid)] for fid in sorted(inputs["franchises"])}
    snap = {"snapshotId": "RS-2026-10-14-DRAFT-NIGHT", "season": inputs["freeze"]["season"], "verifiedAt": verified_at,
            "source": "Official draft-night rosters (keeper freeze + pre-draft trades + 48-pick draft); derived, not a Yahoo export",
            "kind": "DERIVED_POST_DRAFT", "importedAt": verified_at, "teams": teams}
    snap["ownershipDigest"] = ls._digest({f: sorted(r["playerKey"] for r in rows) for f, rows in teams.items()})
    snap["digest"] = ls._digest(teams)
    return snap


# --------------------------------------------------------------------- cli
def cmd_freeze_salaries(args):
    if os.path.exists(SALARY_PATH):
        raise SystemExit("salary_freeze.json already exists (frozen; never regenerated)")
    _write(SALARY_PATH, make_salary_freeze(ls.load_inputs(), args.at))
    print("salaries frozen")


def cmd_post_draft(args):
    inputs = ls.load_inputs()
    snap = make_post_draft_snapshot(inputs, args.date)
    if os.path.exists(POST_DRAFT_PATH):
        old = _load(POST_DRAFT_PATH)
        if {k: v for k, v in old.items()} != snap:
            raise SystemExit("POST_DRAFT.json exists and differs from a fresh derivation: refusing to rewrite a checkpoint")
        print("POST_DRAFT checkpoint unchanged")
        return
    _write(POST_DRAFT_PATH, snap)
    print("POST_DRAFT checkpoint written")


def cmd_init_rosters(args):
    if os.path.exists(ROSTER_INDEX):
        raise SystemExit("rosters/index.json exists: use scripts/import_rosters.py to add snapshots")
    snap = make_initial_roster_snapshot(ls.load_inputs(), args.at)
    rel = f"snapshots/{snap['snapshotId']}.json"
    _write(os.path.join(ROSTER_DIR, rel), snap)
    _write(ROSTER_INDEX, {"season": "2026-27", "current": rel,
                          "history": [{"snapshotId": snap["snapshotId"], "file": rel, "verifiedAt": snap["verifiedAt"],
                                       "source": snap["source"], "digest": snap["digest"], "action": "INIT"}]})
    print(f"initial roster snapshot {snap['snapshotId']}")


def make_checkpoint_snapshot(si, checkpoint_id: str, date: str) -> dict:
    """Freeze the CURRENT-SEASON payroll of every team as a cap checkpoint (same shape as POST_DRAFT)."""
    cur = season_state(si)
    floor, ceiling = ls.cap_band(si)
    return {"kind": checkpoint_id, "season": si["freeze"]["season"],
            "checkpoint": {"id": checkpoint_id, "date": date, "rosterSnapshot": si["rosterSnapshot"]["snapshotId"],
                           "rosterVerifiedAt": si["rosterSnapshot"]["verifiedAt"],
                           "completedTransactions": [t["txnId"] for t in si["seasonTxns"] if t["status"] == "COMPLETED"]},
            "playerOwner": dict(sorted(cur["playerOwner"].items())),
            "teamCaps": {f: ls.team_cap(si, cur, f) for f in sorted(si["franchises"])},
            "countingRule": {"rule": "TOP_N_SALARIES", "n": si["capCountTop"]} if si.get("capCountTop") else {"rule": "ALL"},
            "capBand": {"floor": floor, "ceiling": ceiling}}


def cmd_record_checkpoint(args):
    si = load_season(ls.load_inputs())
    cp = _load(CHECKPOINTS_PATH)
    c = next(x for x in cp["checkpoints"] if x["id"] == args.id)
    if c.get("status") == "RECORDED":
        raise SystemExit(f"{args.id} is already recorded (checkpoints are immutable)")
    rel = f"snapshots/{args.id}.json"
    _write(os.path.join(DATA_DIR, rel), make_checkpoint_snapshot(si, args.id, args.date))
    c.update({"date": args.date, "snapshot": rel, "status": "RECORDED"})
    _write(CHECKPOINTS_PATH, cp)
    print(f"{args.id} recorded from roster snapshot {si['rosterSnapshot']['snapshotId']}")


def cmd_status(args):
    si = load_season(ls.load_inputs())
    snap = si["rosterSnapshot"]
    print(f"roster snapshot: {snap['snapshotId']} verified {snap['verifiedAt']} ({snap['source']})")
    for t in si["seasonTxns"]:
        print(f"  {t['txnId']:14} {t['status']:9} {t.get('label')}")
    st = season_state(si)
    floor, ceiling = ls.cap_band(si)
    for fid in sorted(si["franchises"]):
        cap = ls.team_cap(si, st, fid)
        print(f"  {si['shorts'][fid]:9} {cap:6.0f}  {ls.cap_status(si, cap)}")
    for f in checkpoint_findings(si, st):
        print(f"  FINDING {f['short']}: {f['capAtCheckpoint']:.0f} at {f['checkpoint']} ({f['checkpointDate']}), "
              f"{f['shortfall']:.0f} below floor {f['floor']}; now {f['currentCap']:.0f} ({f['direction']}); {f['status']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = sub.add_parser("freeze-salaries"); p.add_argument("--at", default=now); p.set_defaults(fn=cmd_freeze_salaries)
    p = sub.add_parser("post-draft-snapshot"); p.add_argument("--date", required=True); p.set_defaults(fn=cmd_post_draft)
    p = sub.add_parser("init-rosters"); p.add_argument("--at", required=True); p.set_defaults(fn=cmd_init_rosters)
    p = sub.add_parser("status"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("record-checkpoint"); p.add_argument("id", choices=["POST_TRADE_DEADLINE"])
    p.add_argument("--date", required=True); p.set_defaults(fn=cmd_record_checkpoint)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
