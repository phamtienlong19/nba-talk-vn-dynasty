#!/usr/bin/env python3
"""POST-FREEZE WHAT-IF layer (read-only analytical lens; never a league record).

    Immutable official snapshot      data/2026-27/keeper_freeze.json (locked) + the
                                     official Yahoo registry the freeze was priced from
  + Dated Yahoo snapshot             data/what_if/snapshots/<id>/  (this module's `import`)
  + Scenario assumptions             config/what_if_assumptions.json
  -> pure calculations               build_what_if()
  -> renderer                        scripts/what_if_app.js (embedded by `embed`)

Three states, never mixed:

    OFFICIAL            frozen keepers   frozen salaries   official band
    WHAT IF - REPRICE   SAME keepers     snapshot salaries recomputed band   (Scenario A)
    WHAT IF - REDO      projected keepers snapshot salaries recomputed band  (Scenario B)

Nothing here writes official data. `embed` only rewrites the WHATIF block of
index.html. Standard library only; deterministic for identical inputs.

Scenario B is a *projection*, not a reconstruction of manager intent:
  1. start from the official keepers (evidence of preference);
  2. if the snapshot prices break the ceiling, choose the FEWEST-CHANGE legal set
     (never dropping a >= $20 player, avoiding $10-19 drops that need review),
     tie-broken by Yahoo/dynasty value, then name; equally minimal sets are exposed
     as alternatives;
  3. otherwise change nothing. Optional swaps whose market order flipped since the
     freeze are only *flagged* as discretionary -- never applied.
The floor is not a keeper-declaration constraint (4 teams are officially below it).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_fa_draft_pool as pool  # noqa: E402
import cap_model as cm  # noqa: E402
import league_state as ls  # noqa: E402
import normalize_yahoo_players as ny  # noqa: E402

REPO_ROOT = ls.REPO_ROOT
WI_DIR = os.path.join(REPO_ROOT, "data", "what_if")
SNAP_DIR = os.path.join(WI_DIR, "snapshots")
ASSUMPTIONS_PATH = os.path.join(REPO_ROOT, "config", "what_if_assumptions.json")
PREKEEPER_PATH = os.path.join(ls.DATA_DIR, "prekeeper_rosters.json")
OFFICIAL_YAHOO_PATH = os.path.join(REPO_ROOT, "data", "yahoo", "players_normalized.json")
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")
APP_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "what_if_app.js")
APP_CSS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "what_if.css")
BEGIN, END = "<!--WHATIF-BEGIN-->", "<!--WHATIF-END-->"
LEAGUE_BEGIN = "<!--LEAGUE-DATA-BEGIN-->"


class WhatIfError(ValueError):
    pass


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_assumptions(path: str = ASSUMPTIONS_PATH) -> dict:
    return _load(path)


# ------------------------------------------------------------- snapshot
def _iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def import_snapshot(raw_path: str, snapshot_id: str, effective_date: str, out_root: str = SNAP_DIR,
                    acquired_at: str | None = None, label: str | None = None) -> str:
    """Normalize a raw Yahoo draft_analysis export into a dated, versioned snapshot.

    Three distinct dates are kept apart: `fileAcquiredAt` (when the file reached this
    workstation -- file mtime unless given), `yahoo.*` (what Yahoo's own payload says)
    and `effectiveDate` (the hypothetical date the user attaches). Unrelated league
    fields (current_date, start_date ...) are deliberately NOT read."""
    with open(raw_path, "rb") as f:
        blob = f.read()
    raw = json.loads(blob.decode("utf-8"))
    res = ny.normalize_snapshot(raw, snapshot_id)
    league = raw["fantasy_content"]["league"]
    notes = [p["player"].get("player_notes_last_timestamp") for p in league["players"] if isinstance(p, dict)]
    notes = [n for n in notes if isinstance(n, (int, float))]
    rows = [{"playerId": r["playerId"], "playerKey": r["playerKey"], "name": r["name"], "nbaTeam": r["nbaTeam"],
             "eligiblePositions": r["eligiblePositions"], "oRank": r["oRank"], "capDollars": r["capDollars"]}
            for r in res["players"]]
    meta = {
        "id": snapshot_id,
        "label": label or snapshot_id,
        "effectiveDate": effective_date,
        "fileAcquiredAt": acquired_at or _iso(os.stat(raw_path).st_mtime),
        "sourceFile": os.path.basename(raw_path),
        "sourceSha256": hashlib.sha256(blob).hexdigest(),
        "capField": "projected_auction_value",
        "yahoo": {"leagueKey": league.get("league_key"), "leagueEditKey": league.get("edit_key"),
                  "latestPlayerNoteAt": _iso(max(notes)) if notes else None},
        "playerCount": len(rows),
        "skippedWithoutRankOrCap": res["skipped"],
    }
    out = os.path.join(out_root, snapshot_id)
    os.makedirs(out, exist_ok=True)
    for name, obj in (("snapshot.json", meta), ("players.json", rows)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return out


def load_snapshot(snapshot_id: str, root: str = SNAP_DIR) -> dict:
    d = os.path.join(root, snapshot_id)
    return {"meta": _load(os.path.join(d, "snapshot.json")), "players": _load(os.path.join(d, "players.json"))}


def list_snapshots(root: str = SNAP_DIR) -> list:
    if not os.path.isdir(root):
        return []
    return sorted(n for n in os.listdir(root) if os.path.exists(os.path.join(root, n, "snapshot.json")))


# ------------------------------------------------------------- pure helpers
def classify(cap: float, floor: float, ceiling: float, near: int = 4) -> str:
    """Same semantics as league_state.cap_status, with an explicit band."""
    if cap > ceiling:
        return "OVER_CEILING"
    if cap == ceiling:
        return "AT_CEILING"
    if cap < floor:
        return "UNDER_FLOOR"
    if cap == floor:
        return "AT_FLOOR"
    if ceiling - cap <= near:
        return "NEAR_CEILING"
    return "IN_RANGE"


def compliance(cap: float, floor: float, ceiling: float) -> str:
    return "ABOVE_CEILING" if cap > ceiling else "BELOW_FLOOR" if cap < floor else "WITHIN"


def _num(x):
    return int(x) if float(x).is_integer() else round(float(x), 3)


def _sorted_names(keys, names):
    return sorted(names[k] for k in keys)


def compute_band(players: list) -> dict:
    r = cm.compute_cap_model(players)
    return {"floor": r["roundedFloor"], "ceiling": r["roundedCeiling"], "rawFloor": round(r["rawFloor"], 4),
            "rawCeiling": round(r["rawCeiling"], 4), "benchmark": r["benchmark"], "top144Sum": r["top144Sum"]}


# ------------------------------------------------------------- rosters
def resolve_rosters(inputs: dict, prekeeper: dict, assumptions: dict, snap_players: list) -> dict:
    """franchiseId -> [playerKey] for the ORIGINAL pre-freeze roster, matched by stable
    Yahoo identity: the registry/snapshot name index plus a small controlled alias map."""
    by_name: dict[str, set] = {}
    for p in list(inputs["registry"].values()) + list(snap_players):
        by_name.setdefault(pool.normalize_name(p["name"]), set()).add(p["playerKey"])
    clash = {n: ks for n, ks in by_name.items() if len(ks) > 1}
    if clash:
        raise WhatIfError(f"ambiguous player names (same name, different Yahoo ids): {sorted(clash)}")
    aliases = assumptions["aliases"]
    rosters: dict[str, list] = {}
    owner: dict[str, str] = {}
    for a in prekeeper["assignments"]:
        n = pool.normalize_name(a["playerName"])
        n = aliases.get(n, n)
        keys = by_name.get(n)
        if not keys:
            raise WhatIfError(f"cannot resolve pre-keeper player {a['playerName']!r} to a Yahoo id")
        key = next(iter(keys))
        if key not in inputs["registry"]:
            raise WhatIfError(f"{a['playerName']} ({key}) is not in the official registry; no frozen salary to compare")
        fid = a["franchiseId"]
        if key in owner and owner[key] != fid:
            raise WhatIfError(f"{a['playerName']} appears on {owner[key]} and {fid}")
        owner[key] = fid
        if key not in rosters.setdefault(fid, []):
            rosters[fid].append(key)
    for t in inputs["freeze"]["teams"]:
        missing = [k["name"] for k in t["keepers"] if k["playerKey"] not in rosters.get(t["franchiseId"], [])]
        if missing:
            raise WhatIfError(f"{t['franchiseId']}: official keepers missing from the pre-keeper roster: {missing}")
    return rosters


# ------------------------------------------------------------- Scenario B
def project_keepers(roster: list, k0: set, price: dict, names: dict, value: dict, ceiling: float,
                    assumptions: dict) -> dict:
    """Deterministic fewest-change legal keeper set. See module docstring."""
    never = assumptions["neverDropAtOrAbove"]
    review = assumptions["reviewDropFrom"]
    n0 = len(k0)
    total0 = sum(price[k] for k in k0)
    out = {"mechanical": False, "infeasible": False, "keep": sorted(k0), "alternatives": [], "countReduced": False}
    if total0 <= ceiling:
        return out
    out["mechanical"] = True
    protected = {k for k in k0 if price[k] >= never}
    reviewing = {k for k in k0 if review <= price[k] < never}
    for size in range(n0, -1, -1):
        scored = []
        for combo in itertools.combinations(sorted(roster), size):
            cs = set(combo)
            if sum(price[k] for k in cs) > ceiling or (protected - cs):
                continue
            swaps = len(cs - k0)
            scored.append(((len(reviewing - cs), swaps, size < n0, -round(sum(value[k] for k in cs), 9),
                            tuple(sorted(names[k] for k in cs))), combo))
        if scored:
            scored.sort(key=lambda t: t[0])
            best_key, best = scored[0]
            equal_all = [c for kk, c in scored[1:] if kk[:3] == best_key[:3]]
            equal = equal_all[: assumptions["alternativesMax"]]
            out.update(keep=sorted(best), alternatives=[sorted(c) for c in equal], countReduced=size < n0,
                       equalOptions=1 + len(equal_all))
            return out
    out["infeasible"] = True  # even an empty keeper list is not allowed (cannot happen with >= $0 prices)
    return out


def discretionary_swaps(roster: list, keep: set, k0: set, p0: dict, p1: dict, names: dict, or0: dict, or1: dict,
                        ceiling: float, assumptions: dict) -> list:
    """Optional swaps the snapshot *invites* but does not force -- flagged, never applied.

    DOMINATES  a cut player is now both cheaper-or-equal AND ranked better (Yahoo OR) than a
               kept one, and that was not true at the freeze (repricing created it).
    RANK_FLIP  a cut player has overtaken a kept one by >= discretionaryRankGap places since the
               freeze, and the swap still fits the ceiling."""
    gap_min = assumptions["discretionaryRankGap"]
    total = sum(p1[k] for k in keep)
    found = []
    for out_k in sorted(keep & k0):
        if p1[out_k] >= assumptions["neverDropAtOrAbove"]:
            continue
        for in_k in sorted(set(roster) - keep):
            if in_k in k0 or None in (or0[in_k], or0[out_k], or1[in_k], or1[out_k]):
                continue
            if total - p1[out_k] + p1[in_k] > ceiling:
                continue
            gap = or1[out_k] - or1[in_k]
            dominated_now = gap > 0 and p1[in_k] <= p1[out_k]
            dominated_then = or0[in_k] < or0[out_k] and p0[in_k] <= p0[out_k]
            if dominated_now and not dominated_then:
                kind = "DOMINATES"
                note = (f"{names[in_k]} (Y! {or1[in_k]}, {_num(p1[in_k])}) is now cheaper-or-equal and ranked {gap} places above "
                        f"{names[out_k]} (Y! {or1[out_k]}, {_num(p1[out_k])}); not true at the freeze")
            elif gap >= gap_min and or0[in_k] > or0[out_k]:
                kind = "RANK_FLIP"
                note = (f"{names[in_k]} (Y! {or1[in_k]}) now ranks {gap} places above {names[out_k]} (Y! {or1[out_k]}); "
                        f"the order was reversed at the freeze")
            else:
                continue
            found.append({"kind": kind, "out": out_k, "in": in_k, "outName": names[out_k], "inName": names[in_k],
                          "rankGap": gap, "capDelta": _num(p1[in_k] - p1[out_k]), "note": note})
    found.sort(key=lambda d: (d["kind"] != "DOMINATES", -d["rankGap"], d["outName"], d["inName"]))
    return found[: assumptions["discretionaryMaxPerTeam"]]


# ------------------------------------------------------------- FA pools
def _pool_rows(ranked: list) -> list:
    return [{"n": c.name, "pos": c.pos, "nba": c.nba, "cap": _num(c.cap),
             "or": None if c.o_rank == pool.MISSING_OR else c.o_rank,
             "src": "cut" if c.src == "cut" else ("R" if c.rookie else "FA"),
             "st": c.src_team if c.src == "cut" else "", "rk": c.rookie} for c in ranked]


def build_pool(yahoo_rows: list, kept_names: set, cuts: list, dyn, dyn_max, rookies, draft_years) -> list:
    by_norm = {pool.normalize_name(p["name"]): p for p in yahoo_rows}
    cands = pool.build_candidates(None, by_norm, dyn, dyn_max, rookie_names=rookies, draft_years=draft_years,
                                  kept=kept_names, cuts=cuts)
    return _pool_rows(pool.sort_and_truncate(cands))


def compare_pools(off: list, rep: list, redo: list, meaningful: int) -> dict:
    """Stage-separated diff. rep = new prices with OFFICIAL keepers (market effect);
    redo = new prices with projected keepers (adds the keeper effect)."""
    nk = pool.normalize_name
    pos = lambda rows: {nk(r["n"]): i for i, r in enumerate(rows, 1)}  # noqa: E731
    po, pr, pd = pos(off), pos(rep), pos(redo)
    entered, exited, moved = [], [], []
    for r in redo:
        k = nk(r["n"])
        if k not in po:
            entered.append({"n": r["n"], "rank": pd[k], "cause": "MARKET" if k in pr else "KEEPER"})
    for r in off:
        k = nk(r["n"])
        if k not in pd:
            exited.append({"n": r["n"], "rank": po[k], "cause": "KEEPER" if k in pr else "MARKET"})
    for r in redo:
        k = nk(r["n"])
        if k in po:
            d_mkt = (po[k] - pr[k]) if k in pr else 0
            d_keep = (pr[k] - pd[k]) if k in pr else 0
            d = po[k] - pd[k]
            if abs(d) >= meaningful:
                moved.append({"n": r["n"], "from": po[k], "to": pd[k], "delta": d,
                              "cause": "KEEPER" if abs(d_keep) > abs(d_mkt) else "MARKET"})
    return {"entered": entered, "exited": exited, "moved": sorted(moved, key=lambda m: (-abs(m["delta"]), m["n"]))}


# ------------------------------------------------------------- build
def build_what_if(inputs: dict, snapshot: dict, assumptions: dict | None = None, prekeeper: dict | None = None,
                  official_yahoo: list | None = None, dynasty=None, rookies=None, draft_years=None) -> dict:
    """Everything the What-If page shows, as plain JSON. Pure: reads only its arguments."""
    A = assumptions or load_assumptions()
    prekeeper = prekeeper or _load(PREKEEPER_PATH)
    official_yahoo = official_yahoo if official_yahoo is not None else _load(OFFICIAL_YAHOO_PATH)
    dyn, dyn_max = dynasty if dynasty is not None else pool.load_dynasty_rankings()
    rookies = rookies if rookies is not None else pool.load_rookie_names()
    draft_years = draft_years if draft_years is not None else pool.load_draft_years()
    snap_rows = snapshot["players"]
    reg = inputs["registry"]

    band1 = compute_band(snap_rows)
    floor0, ceil0 = ls.cap_band(inputs)
    floor1, ceil1 = band1["floor"], band1["ceiling"]
    near = A["nearCeilingRoom"]

    snap_by_key = {p["playerKey"]: p for p in snap_rows}
    rosters = resolve_rosters(inputs, prekeeper, A, snap_rows)
    names = {k: reg[k]["name"] for ks in rosters.values() for k in ks}
    p0 = {k: float(reg[k]["projectedAuctionValue"]) for k in names}
    p1 = {k: float(snap_by_key[k]["capDollars"]) if k in snap_by_key else 0.0 for k in names}
    or0 = {k: reg[k].get("oRank") for k in names}
    or1 = {k: snap_by_key[k]["oRank"] if k in snap_by_key else None for k in names}
    value = {}
    for k in names:
        c = pool.Candidate(name=names[k], pos="", nba="", cap=0.0, o_rank=or1[k] or pool.MISSING_OR,
                           dynasty_rank=(dyn.get(pool.normalize_name(names[k])) or {}).get("rank"),
                           yahoo_rank_max=max(len(snap_rows), 1), dynasty_rank_max=dyn_max)
        value[k] = 1.0 - c.relevance_score()

    shorts = {t["franchiseId"]: t for t in inputs["freeze"]["teams"]}
    teams, a_rows = [], []
    kept_off, kept_hyp = {}, {}
    for t in inputs["freeze"]["teams"]:
        fid = t["franchiseId"]
        roster = rosters[fid]
        k0 = {k["playerKey"] for k in t["keepers"]}
        cap0 = sum(p0[k] for k in k0)
        cap1 = sum(p1[k] for k in k0)
        proj = project_keepers(roster, k0, p1, names, value, ceil1, A)
        keep = set(proj["keep"])
        cap_b = sum(p1[k] for k in keep)
        newly_kept, newly_cut = sorted(keep - k0, key=lambda k: names[k]), sorted(k0 - keep, key=lambda k: names[k])
        reasons = []
        if proj["mechanical"]:
            reasons.append(f"CEILING — official keepers cost {_num(cap1)} at snapshot prices, {_num(cap1 - ceil1)} over the {ceil1} ceiling.")
            if newly_cut or newly_kept:
                reasons.append("Fewest-change fix: cut " + ", ".join(f"{names[k]} ({_num(p1[k])})" for k in newly_cut)
                               + " · keep " + ", ".join(f"{names[k]} ({_num(p1[k])})" for k in newly_kept)
                               + f" → {_num(cap_b)}.")
            if proj["countReduced"]:
                reasons.append("No legal 9-player set exists; keeper count reduced.")
            if proj["infeasible"]:
                reasons.append("No legal keeper set exists at these prices.")
        else:
            reasons.append("No change needed: official keepers stay within the recomputed ceiling.")
        if cap1 < floor1 and not proj["mechanical"]:
            reasons.append(f"Below the floor by {_num(floor1 - cap1)} — the floor is not a keeper-declaration test (see rules).")
        alts = []
        for alt in proj["alternatives"]:
            ai, ao = sorted(set(alt) - k0, key=lambda k: names[k]), sorted(k0 - set(alt), key=lambda k: names[k])
            alts.append({"keep": alt, "in": ai, "out": ao, "total": _num(sum(p1[k] for k in alt)),
                         "note": "cut " + ", ".join(names[k] for k in ao) + " · keep " + ", ".join(names[k] for k in ai)})
        disc = discretionary_swaps(roster, keep, k0, p0, p1, names, or0, or1, ceil1, A)
        players = []
        for k in sorted(roster, key=lambda k: (k not in k0, -p0[k], names[k])):
            rp = reg[k]
            sp = snap_by_key.get(k)
            players.append({"k": k, "n": names[k], "pos": pool.pos_from_eligible(rp["eligiblePositions"]),
                            "nba": (sp or rp)["nbaTeam"], "c0": _num(p0[k]), "c1": _num(p1[k]), "miss": sp is None,
                            "or0": or0[k], "or1": or1[k], "k0": k in k0, "k1": k in keep,
                            "lock": p1[k] >= A["neverDropAtOrAbove"], "rev": A["reviewDropFrom"] <= p1[k] < A["neverDropAtOrAbove"]})
        team = {
            "id": fid, "short": t["short"], "name": t.get("teamName") or inputs["franchises"][fid]["displayName"],
            "color": t["color"], "text": t["text"], "crown": t["short"] == pool.DEFENDING_CHAMPION_SHORT_NAME,
            "players": players,
            "a": {"official": _num(cap0), "whatIf": _num(cap1), "delta": _num(cap1 - cap0),
                  "toFloor": _num(max(0, floor1 - cap1)), "room": _num(ceil1 - cap1),
                  "status": classify(cap1, floor1, ceil1, near), "compliance": compliance(cap1, floor1, ceil1),
                  "officialStatus": classify(cap0, floor0, ceil0, near)},
            "b": {"total": _num(cap_b), "delta": _num(cap_b - cap0), "toFloor": _num(max(0, floor1 - cap_b)),
                  "room": _num(ceil1 - cap_b), "status": classify(cap_b, floor1, ceil1, near),
                  "compliance": compliance(cap_b, floor1, ceil1), "mechanical": proj["mechanical"], "equalOptions": proj.get("equalOptions", 1),
                  "infeasible": proj["infeasible"], "newlyKept": newly_kept, "newlyCut": newly_cut,
                  "reasons": reasons, "alternatives": alts, "discretionary": disc},
        }
        teams.append(team)
        kept_off[fid], kept_hyp[fid] = k0, keep

    # ---- FA / DRAFT 60: official, reprice-only, redo
    def cuts_for(kept_by_team, prices):
        out = []
        for fid, roster in rosters.items():
            for k in roster:
                if k not in kept_by_team[fid]:
                    out.append({"name": names[k], "cap": prices[k], "team": shorts[fid]["short"]})
        return out

    def kept_names(kept_by_team):
        return {pool.normalize_name(names[k]) for ks in kept_by_team.values() for k in ks}

    official_rows = [dict(p) for p in official_yahoo]
    pool_off = build_pool(official_rows, kept_names(kept_off), cuts_for(kept_off, p0), dyn, dyn_max, rookies, draft_years)
    pool_rep = build_pool(snap_rows, kept_names(kept_off), cuts_for(kept_off, p1), dyn, dyn_max, rookies, draft_years)
    pool_redo = build_pool(snap_rows, kept_names(kept_hyp), cuts_for(kept_hyp, p1), dyn, dyn_max, rookies, draft_years)
    diff = compare_pools(pool_off, pool_rep, pool_redo, A["meaningfulRankMove"])

    # ---- league summary
    a_all = [(t["short"], t["a"]) for t in teams]
    by_delta = sorted(a_all, key=lambda x: (-x[1]["delta"], x[0]))
    summary = {
        "within": sum(1 for _, a in a_all if a["compliance"] == "WITHIN"),
        "belowFloor": sum(1 for _, a in a_all if a["compliance"] == "BELOW_FLOOR"),
        "aboveCeiling": sum(1 for _, a in a_all if a["compliance"] == "ABOVE_CEILING"),
        "largestIncreases": [{"short": s, "delta": a["delta"]} for s, a in by_delta[:3] if a["delta"] > 0],
        "largestDecreases": [{"short": s, "delta": a["delta"]} for s, a in by_delta[::-1][:3] if a["delta"] < 0],
        "redoChanged": [t["short"] for t in teams if t["b"]["newlyKept"] or t["b"]["newlyCut"]],
        "redoWithin": sum(1 for t in teams if t["b"]["compliance"] == "WITHIN"),
        "redoBelowFloor": sum(1 for t in teams if t["b"]["compliance"] == "BELOW_FLOOR"),
        "redoAboveCeiling": sum(1 for t in teams if t["b"]["compliance"] == "ABOVE_CEILING"),
    }
    meta = snapshot["meta"]
    return {
        "id": meta["id"], "meta": meta,
        "band": {"official": {"floor": floor0, "ceiling": ceil0}, "whatIf": band1,
                 "formulaMatchesOfficial": (floor0, ceil0) == (floor1, ceil1), "near": near},
        "assumptions": {k: A[k] for k in ("keeperMax", "neverDropAtOrAbove", "reviewDropFrom", "discretionaryRankGap",
                                          "notEnforced")},
        "teams": teams, "summary": summary,
        "fa": {"official": pool_off, "reprice": pool_rep, "redo": pool_redo, "diff": diff},
    }


def build_page_payload(inputs: dict | None = None, ids: list | None = None, **kw) -> dict:
    inputs = inputs or ls.load_inputs()
    ids = ids or list_snapshots()
    if not ids:
        raise WhatIfError("no what-if snapshots found under data/what_if/snapshots/")
    snaps = {i: build_what_if(inputs, load_snapshot(i), **kw) for i in ids}
    return {"default": ids[-1], "order": ids, "snapshots": snaps}


# ------------------------------------------------------------- embedding
SECTION_HTML = (
    '<section class="page" id="what-if" hidden><div class="title">WHAT IF <span class="wi-vi">GIẢ ĐỊNH</span></div>'
    '<div id="wi-root"></div></section>'
)


def render_block(payload: dict) -> str:
    with open(APP_JS, encoding="utf-8") as f:
        js = f.read()
    with open(APP_CSS, encoding="utf-8") as f:
        css = f.read()
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (BEGIN + SECTION_HTML + "<style id=\"whatif-css\">" + css + "</style>"
            + '<script type="application/json" id="whatif-data">' + data + "</script>"
            + '<script id="whatif-app">' + js + "</script>" + END + "\n")


def _end(index_html: str) -> int:
    e = index_html.index(END) + len(END)
    return e + 1 if index_html[e:e + 1] == "\n" else e


def embed(index_html: str, payload: dict) -> str:
    block = render_block(payload)
    if BEGIN in index_html:
        return index_html[:index_html.index(BEGIN)] + block + index_html[_end(index_html):]
    if LEAGUE_BEGIN not in index_html:
        raise WhatIfError("index.html has no league-data block to anchor the what-if block before")
    return index_html.replace(LEAGUE_BEGIN, block + LEAGUE_BEGIN, 1)


def strip_block(index_html: str) -> str:
    """index.html with the what-if block removed -- the OFFICIAL page, used by immutability tests."""
    if BEGIN not in index_html:
        return index_html
    return index_html[:index_html.index(BEGIN)] + index_html[_end(index_html):]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    im = sub.add_parser("import", help="normalize a raw Yahoo draft_analysis export into a dated snapshot")
    im.add_argument("raw")
    im.add_argument("--id", required=True)
    im.add_argument("--effective", required=True)
    im.add_argument("--acquired-at", default=None)
    im.add_argument("--label", default=None)
    sub.add_parser("embed", help="rebuild and splice the WHAT-IF block into index.html")
    sub.add_parser("report", help="print the headline numbers")
    args = ap.parse_args()
    if args.cmd == "import":
        print("snapshot written:", import_snapshot(args.raw, args.id, args.effective, acquired_at=args.acquired_at, label=args.label))
        return
    payload = build_page_payload()
    if args.cmd == "embed":
        with open(INDEX_HTML, encoding="utf-8") as f:
            html = f.read()
        with open(INDEX_HTML, "w", encoding="utf-8") as f:
            f.write(embed(html, payload))
        print("what-if block embedded:", ", ".join(payload["order"]))
    else:
        s = payload["snapshots"][payload["default"]]
        print(json.dumps({"band": s["band"], "summary": s["summary"], "diff": {k: len(v) for k, v in s["fa"]["diff"].items()}}, indent=2))


if __name__ == "__main__":
    main()
