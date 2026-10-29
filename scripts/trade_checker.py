#!/usr/bin/env python3
"""Trade checker: for a proposed set of player moves, which league rules the trade breaks and why.

Governance, not advice (docs/GOVERNANCE_ROADMAP.md): every row is a rule verdict with its source and a plain reason.
There is no value judgement, no fairness score and no recommendation. Levels: ok / info / review / blocked.
Overall: BLOCKED if any rule blocks, COMMISSIONER REVIEW if any asks for review, else LEGAL (= the automated rules
pass; approval itself stays with the group chat / commissioner). Read-only: nothing here writes official state.

Python is the source of truth; index.html carries a thin port that tests/ run against `golden_cases()`."""
import copy
import datetime
import json
import math
import os

import league_state as ls
import season_state as ss

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "trade_rules.json")
LEVELS = ("ok", "info", "review", "blocked")
SRC_CAP = "League rules · Salary cap application"
SRC_COOL = "League rules · Trades (cooldown)"
SRC_TANK = "League rules · Roster / anti-tank governance"
SRC_PEND = "League rules · 2-day pending period"
SRC_SIZE = "League rules · 15 roster spots (Yahoo enforces it when a trade is processed)"
SRC_DROP = "League rules · Dropping players"
SRC_PICK = "League rules · Draft picks"
SRC_SLOTS = "Yahoo roster slots (trade processing)"
SRC_IL = "League rules · Injured list"
SRC_DEAD = "Yahoo · Trade End Date"


def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def top_ranked(si, rules=None) -> set:
    """playerKeys in the preseason top N by Yahoo O-Rank."""
    n = (rules or load_rules())["cooldown"]["topRankedCutoff"]
    ranked = [(m["oRank"], k) for k, m in si["registry"].items() if m.get("oRank")]
    return {k for _, k in sorted(ranked)[:n]}


def preseason_ranks(si, top_n) -> dict:
    """playerKey -> preseason Yahoo O-Rank, for the top `top_n` (drop-protected players)."""
    return {k: m["oRank"] for k, m in si["registry"].items() if m.get("oRank") and m["oRank"] <= top_n}


def future_picks(si, rules=None) -> dict:
    """The picks that exist for trading: next season's draft only (league rules: no picks further ahead), every team's own R1-R3.
    The ledger has no record of any 2027 pick changing hands, so each team still owns its own."""
    p = (rules or load_rules())["picks"]
    out = {}
    for year in range(p["nextDraftYear"], p["nextDraftYear"] + p["maxYearsAhead"]):
        for rnd in (1, 2, 3):
            for fid in sorted(si["franchises"]):
                out[f"{year}-R{rnd}-{fid}"] = {"year": year, "round": rnd, "original": fid, "owner": fid}
    return out


def pick_label(si, pk) -> str:
    return f"{pk['year']} R{pk['round']}" + ("" if pk["original"] == pk["owner"] else f" ({si['shorts'][pk['original']]})")


def acquisitions(si) -> dict:
    """(playerKey, team) -> effectiveAt of the latest completed trade that brought the player to that team."""
    out = {}
    for t in sorted((t for t in si["seasonTxns"] if t["status"] == "COMPLETED"), key=lambda t: ss.ts(t["effectiveAt"])):  # staged trades have no effectiveAt
        for a in ls.trade_assets(t):
            if a["type"] == "player":
                out[(a["playerKey"], a["to"])] = ss.ts(t["effectiveAt"])
    return out


def _parse(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def cooldown_end(effective_at, key, top, rules) -> str:
    days = rules["cooldown"]["daysTopRanked" if key in top else "days"]
    return (_parse(effective_at) + datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(rule, level, source, reason, team=None, **extra):
    r = {"rule": rule, "team": team, "level": level, "source": source, "reason": reason}
    r.update(extra)
    return r


def _moved_state(state, moves, drops=(), ils=()):
    hyp = copy.copy(state)
    hyp["playerOwner"] = dict(state["playerOwner"])
    hyp["slots"] = dict(state.get("slots", {}))
    for m in moves:
        hyp["playerOwner"][m["key"]] = m["to"]
        hyp["slots"][m["key"]] = None                # an incoming player lands outside IL (Yahoo never places him on IL)
    for d in drops:
        hyp["playerOwner"][d["key"]] = None          # dropped: a free agent, on no roster
    for i in ils:
        hyp["slots"][i["key"]] = "IL"                # moved to IL before the trade
    return hyp


def _worse(kind, before, after) -> bool:
    if kind == "coverage":
        return any(after["byPosition"][p] < before["byPosition"][p] for p in before["short"]) or \
            any(after["byCombo"][c] < before["byCombo"][c] for c in before["shortCombo"])
    if kind == "lineup":
        return len(after["empty"]) > len(before["empty"])
    return after["count"] > before["count"]


def check_proposal(si, state, moves, now, rules=None, drops=(), ils=()) -> dict:
    """moves: [{"key": playerKey, "from": fid, "to": fid}]; drops: [{"key": playerKey, "team": fid}] (players a team releases to get back
    under the roster limit); ils: [{"key": playerKey, "team": fid}] (injured players a team puts on IL before the trade). `now`: ISO timestamp the cooldown is measured against."""
    rules = rules or load_rules()
    short = si["shorts"]
    rows = []
    picks = future_picks(si, rules)
    all_moves = moves
    pmoves = [m for m in all_moves if m.get("type") == "pick"]
    moves = [m for m in all_moves if m.get("type") != "pick"]
    teams = sorted({m["from"] for m in all_moves} | {m["to"] for m in all_moves} | {d["team"] for d in drops} | {i["team"] for i in ils})
    gone = {m["key"] for m in moves}
    bad = [m for m in moves if m["from"] == m["to"] or state["playerOwner"].get(m["key"]) != m["from"]]
    bad += [m for m in pmoves if m["from"] == m["to"] or picks.get(m["key"], {}).get("owner") != m["from"]]
    dropped = {d["key"] for d in drops}
    bad += [{"key": d["key"]} for d in drops if state["playerOwner"].get(d["key"]) != d["team"] or d["key"] in gone]
    bad += [{"key": i["key"]} for i in ils if state["playerOwner"].get(i["key"]) != i["team"] or i["key"] in gone or i["key"] in dropped]
    if len(teams) < 2 or not all_moves or bad:
        far = [m for m in bad if str(m["key"])[:4].isdigit() and m["key"] not in picks]
        if not all_moves or len(teams) < 2:
            reason = "Add at least two teams and one player or pick."
        elif far:
            reason = "Picks beyond next season's draft can't be traded."
        else:
            reason = "Not on the team he / it is being traded from: " + ", ".join(
                (pick_label(si, picks[m["key"]]) if m["key"] in picks else ls.player_name(si, m["key"])) for m in bad) + "."
        rows.append(_row("valid", "blocked", "Proposal", reason))
        return {"status": "BLOCKED", "rules": rows, "moves": all_moves}
    hyp = _moved_state(state, moves, drops, ils)
    floor, ceiling = ls.cap_band(si)
    top_n = si.get("capCountTop")
    for f in teams:
        cb, ca = ls.team_cap(si, state, f), ls.team_cap(si, hyp, f)
        pay = f"Payroll {cb:g} → {ca:g}"
        w = ls.in_season_cap_checks(si, f, cb, ca)
        if not w:
            rows.append(_row("cap", "ok", SRC_CAP, f"{pay}, inside {floor}–{ceiling}.", short[f], before=cb, after=ca))
        elif w[0]["code"] == "CAP_STILL_OUTSIDE_BAND":
            d = w[0]["detail"]
            where = f"over the {ceiling} ceiling" if d["side"] == "OVER_CEILING" else f"under the {floor} floor"
            rows.append(_row("cap", "info", SRC_CAP, f"{pay}, still {d['by']:g} {where} but moving toward the band.", short[f], before=cb, after=ca))
        else:
            d = w[0]["detail"]
            where = f"over the {ceiling} ceiling" if d["side"] == "OVER_CEILING" else f"under the {floor} floor"
            rows.append(_row("cap", "blocked", SRC_CAP, f"{pay}: {d['by']:g} {where}. Trades must keep a team in the band or move it toward it.",
                             short[f], before=cb, after=ca))
            lad = rules["capLadder"]
            key = {"UNDER_5": "under", "OVER_5": "over", "EXACTLY_5": "exactly"}[d["ladder"]]
            rows.append(_row("ladder", "review" if key == "exactly" else "info", SRC_CAP, "If it went through: " + lad[key], short[f]))
    spots = rules["roster"]["spots"]
    for f in teams:
        nb, na = len(ls.team_players(si, state, f)), len(ls.team_players(si, hyp, f))
        if na > spots:
            rows.append(_row("size", "blocked", SRC_SIZE, f"Roster {nb} → {na} of {spots} spots: drop {na - spots} more player{'s' if na - spots > 1 else ''} "
                             "(Yahoo asks for the drops when the trade is sent).", short[f]))
        else:
            rows.append(_row("size", "ok", SRC_SIZE, f"Roster {nb} → {na} of {spots} spots.", short[f]))
    yh = rules["yahoo"]
    elig = set(yh["ilEligibleStatuses"])
    status = state.get("status", {})
    inc = {m["key"] for m in moves}
    moved_il = {i["key"] for i in ils}
    for i in ils:
        st = status.get(i["key"])
        name = ls.player_name(si, i["key"])
        if st in elig:
            rows.append(_row("il", "info", SRC_IL, f"{short[i['team']]} moves {name} to IL first.", short[i["team"]]))
        else:
            rows.append(_row("il", "blocked", SRC_IL, f"{name} can't go on IL: Yahoo lists him as {st or 'healthy'}, and only injured players can be moved to IL.", short[i["team"]]))
    for f in teams:
        kept = ls.team_players(si, hyp, f)
        slot_of = lambda k: hyp["slots"].get(k)  # noqa: E731
        on_il = [k for k in kept if slot_of(k) in ss.SLOTS_IL]
        non_il = len(kept) - len(on_il)
        cap = yh["activeSlots"] + yh["benchSlots"]
        open_il = yh["ilSlots"] - len(on_il)
        movable = [ls.player_name(si, k) for k in kept if k not in inc and slot_of(k) not in ss.SLOTS_IL and status.get(k) in elig]
        if non_il > cap:
            hint = (f" Injured players who could go on IL first: {', '.join(movable)} ({open_il} IL slot{'s' if open_il != 1 else ''} open)."
                    if movable and open_il > 0 else " No injured player can move to IL, so a drop is needed.")
            rows.append(_row("slots", "blocked", SRC_SLOTS, f"{non_il} players outside IL, but only {cap} lineup + bench spots ({yh['activeSlots']} + {yh['benchSlots']}). "
                             "Incoming players land on the bench, never straight on IL." + hint, short[f]))
        else:
            rows.append(_row("slots", "ok", SRC_SLOTS, f"Lineup + bench {non_il}/{cap}, IL {len(on_il)}/{yh['ilSlots']}.", short[f]))
        if len(on_il) > yh["ilSlots"]:
            rows.append(_row("slots", "blocked", SRC_SLOTS, f"{len(on_il)} players on IL, but only {yh['ilSlots']} IL slots.", short[f]))
        for k in kept:
            if slot_of(k) in ss.SLOTS_IL and k not in moved_il and k not in inc and status.get(k) not in elig:
                rows.append(_row("il", "info", SRC_IL, f"{ls.player_name(si, k)} sits on IL but Yahoo lists him as {status.get(k) or 'healthy'}: he has to return to the lineup, and Yahoo may not process the trade until the roster is legal.", short[f]))
    dr = rules["drops"]
    pre_rank = preseason_ranks(si, dr["neverTopRanked"])
    for d in drops:
        cap = ls.player_cap(si, d["key"])
        name = ls.player_name(si, d["key"])
        rank = pre_rank.get(d["key"])
        why = ([f"paid {cap:g} (limit {dr['neverAtOrAbove']})"] if cap >= dr["neverAtOrAbove"] else []) + \
              ([f"preseason O-Rank {rank} (top {dr['neverTopRanked']})"] if rank else [])
        if why:
            rows.append(_row("drop", "blocked", SRC_DROP, f"{name} can't be dropped: {' and '.join(why)}. These players are protected.", short[d["team"]]))
        elif cap >= dr["reviewFrom"]:
            rows.append(_row("drop", "review", SRC_DROP, f"{name} ({cap:g}) is a restricted drop (paid {dr['reviewFrom']}–{dr['neverAtOrAbove'] - 1}): the commissioner decides, "
                             "by his current ranking (inside the top 100 or not).", short[d["team"]]))
        else:
            rows.append(_row("drop", "info", SRC_DROP, f"{short[d['team']]} drops {name} ({cap:g}).", short[d["team"]]))
    # cooldown: the acquired player cannot be traded again until it ends
    acq, top = acquisitions(si), top_ranked(si, rules)
    held = False
    for m in moves:
        at = acq.get((m["key"], m["from"]))
        if not at:
            continue
        end = cooldown_end(at, m["key"], top, rules)
        if now < end:
            held = True
            days = rules["cooldown"]["daysTopRanked" if m["key"] in top else "days"]
            left = math.ceil((_parse(end) - _parse(now)).total_seconds() / 86400)
            rows.append(_row("cooldown", "blocked", SRC_COOL, f"{ls.player_name(si, m['key'])} can't be traded for {left} more day{'s' if left != 1 else ''} (until {end[:10]}): "
                             f"{short[m['from']]} got him on {at[:10]} (held {days} days{', preseason top ' + str(rules['cooldown']['topRankedCutoff']) if m['key'] in top else ''}).", short[m["from"]]))
    if not held:
        rows.append(_row("cooldown", "ok", SRC_COOL, "No player in this trade is inside a cooldown.", None))
    # anti-tank: a trade may not worsen a concentration that is already over
    for f in teams:
        before, after = ss.roster_checks(si, state, f), ss.roster_checks(si, hyp, f)
        hits = []
        for kind in ("injured", "singlePosition", "coverage", "lineup"):
            b, a = before[kind], after[kind]
            if b["level"] == "over" and _worse(kind, b, a):
                rows.append(_row("antitank", "blocked", SRC_TANK, "Already over, and the trade makes it worse.", short[f], check=kind))
                hits.append(kind)
            elif b["level"] != "over" and a["level"] == "over":
                rows.append(_row("antitank", "review", SRC_TANK, "The trade pushes the team over.", short[f], check=kind))
                hits.append(kind)
            elif a["level"] == "watch" and _worse(kind, b, a):
                rows.append(_row("antitank", "info", SRC_TANK, "Exactly at the limit afterwards.", short[f], check=kind))
                hits.append(kind)
        if not hits:
            rows.append(_row("antitank", "ok", SRC_TANK, "Injured, single-position, coverage and lineup limits: none worsened.", short[f]))
    pr = rules["picks"]
    end = rules["yahoo"]["tradeEndDate"]
    tank_cutoff = (datetime.date.fromisoformat(end) - datetime.timedelta(days=rules["yahoo"]["tankCutoffDays"])).isoformat()
    if now[:10] > end:
        rows.append(_row("deadline", "blocked", SRC_DEAD, f"The trade deadline passed on {end}: no trades after that date.", None))
    else:
        rows.append(_row("deadline", "ok", SRC_DEAD, f"Before the trade deadline ({end}).", None))
    for m in pmoves:
        pk = picks[m["key"]]
        who = short[m["from"]]
        if pk["round"] in pr["lockedRounds"]:
            rows.append(_row("pick", "blocked", SRC_PICK, f"{pick_label(si, pk)} is a 1st-round pick: it can't be traded in-season. 1st-round picks only move in the pre-draft window "
                             "(after keepers, before the draft), and only the current year's.", who))
        elif now[:10] > tank_cutoff:
            rows.append(_row("pick", "blocked", SRC_PICK, f"{pick_label(si, pk)} is next season's pick: it can only move in a Trade Tank trade, which must be at least 2 weeks "
                             f"before the deadline. The last day was {tank_cutoff}.", who))
        else:
            rows.append(_row("pick", "review", SRC_PICK, f"{pick_label(si, pk)} is next season's pick: it can only be traded inside a Trade Tank trade "
                             "(team out of playoff contention, at least 2 weeks before the deadline, one per team). Eligibility isn't checked here.", who))
    rows.append(_row("pending", "info", SRC_PEND, f"{rules['pendingDays']}-day pending period; Yahoo trade review is the commissioner (2 days to reject) and a veto needs 7 of 16 team votes. Whether the trade is acceptable is the commissioner's call.", None))
    rows.append(_row("tank", "info", SRC_TANK, "Not checked here: Trade Tank eligibility (needs the standings) and trade bans from earlier cap violations.", None))
    level = max((r["level"] for r in rows), key=LEVELS.index)
    return {"status": {"blocked": "BLOCKED", "review": "COMMISSIONER REVIEW"}.get(level, "LEGAL"), "rules": rows, "moves": moves}


def signature(result) -> dict:
    """What the page port must reproduce exactly: the overall status and every (rule, team, level)."""
    return {"status": result["status"], "rules": sorted([r["rule"], r["team"] or "", r["level"]] for r in result["rules"])}


def golden_cases(si, state, now, rules=None) -> list:
    """Deterministic proposals over the live state (every 2-team, 1-for-1 swap between the first teams' top salaries,
    plus a few multi-player ones) with their Python verdicts: tests run the page port over the same cases."""
    rules = rules or load_rules()
    fids = sorted(si["franchises"])
    rows = {f: ss.ranked_roster(si, state, f) for f in fids}
    cases = []
    for i in range(0, len(fids) - 1, 2):
        a, b = fids[i], fids[i + 1]
        for ra, rb in ((rows[a][0], rows[b][0]), (rows[a][0], rows[b][-1]), (rows[a][-1], rows[b][0])):
            cases.append([{"key": ra["k"], "from": a, "to": b}, {"key": rb["k"], "from": b, "to": a}])
        cases.append([{"key": rows[a][0]["k"], "from": a, "to": b}, {"key": rows[a][1]["k"], "from": a, "to": b}, {"key": rows[b][0]["k"], "from": b, "to": a}])
    return [{"moves": m, "expect": signature(check_proposal(si, state, m, now, rules))} for m in cases]
