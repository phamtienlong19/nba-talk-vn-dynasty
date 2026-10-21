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


def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def top_ranked(si, rules=None) -> set:
    """playerKeys in the preseason top N by Yahoo O-Rank."""
    n = (rules or load_rules())["cooldown"]["topRankedCutoff"]
    ranked = [(m["oRank"], k) for k, m in si["registry"].items() if m.get("oRank")]
    return {k for _, k in sorted(ranked)[:n]}


def acquisitions(si) -> dict:
    """(playerKey, team) -> effectiveAt of the latest completed trade that brought the player to that team."""
    out = {}
    for t in sorted(si["seasonTxns"], key=lambda t: ss.ts(t["effectiveAt"])):
        if t["status"] != "COMPLETED":
            continue
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


def _moved_state(state, moves, drops=()):
    hyp = copy.copy(state)
    hyp["playerOwner"] = dict(state["playerOwner"])
    for m in moves:
        hyp["playerOwner"][m["key"]] = m["to"]
    for d in drops:
        hyp["playerOwner"][d["key"]] = None          # dropped: a free agent, on no roster
    return hyp


def _worse(kind, before, after) -> bool:
    if kind == "coverage":
        return any(after["byPosition"][p] < before["byPosition"][p] for p in before["short"]) or \
            any(after["byCombo"][c] < before["byCombo"][c] for c in before["shortCombo"])
    if kind == "lineup":
        return len(after["empty"]) > len(before["empty"])
    return after["count"] > before["count"]


def check_proposal(si, state, moves, now, rules=None, drops=()) -> dict:
    """moves: [{"key": playerKey, "from": fid, "to": fid}]; drops: [{"key": playerKey, "team": fid}] (players a team releases to get back
    under the roster limit). `now`: ISO timestamp the cooldown is measured against."""
    rules = rules or load_rules()
    short = si["shorts"]
    rows = []
    teams = sorted({m["from"] for m in moves} | {m["to"] for m in moves})
    gone = {m["key"] for m in moves}
    bad = [m for m in moves if m["from"] == m["to"] or state["playerOwner"].get(m["key"]) != m["from"]]
    bad += [{"key": d["key"]} for d in drops if state["playerOwner"].get(d["key"]) != d["team"] or d["key"] in gone or d["team"] not in teams]
    if len(teams) < 2 or not moves or bad:
        reason = ("Add at least two teams and one player." if not moves or len(teams) < 2 else
                  "A player is not on the team he is being traded from: " + ", ".join(ls.player_name(si, m["key"]) for m in bad) + ".")
        rows.append(_row("valid", "blocked", "Proposal", reason))
        return {"status": "BLOCKED", "rules": rows, "moves": moves}
    hyp = _moved_state(state, moves, drops)
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
    dr = rules["drops"]
    for d in drops:
        cap = ls.player_cap(si, d["key"])
        name = ls.player_name(si, d["key"])
        if cap >= dr["neverAtOrAbove"]:
            rows.append(_row("drop", "blocked", SRC_DROP, f"{name} ({cap:g}) can never be dropped: players at {dr['neverAtOrAbove']} or more are protected.", short[d["team"]]))
        elif cap >= dr["reviewFrom"]:
            rows.append(_row("drop", "review", SRC_DROP, f"{name} ({cap:g}) needs commissioner review to be dropped (players at {dr['reviewFrom']}–{dr['neverAtOrAbove'] - 1}).", short[d["team"]]))
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
            rows.append(_row("cooldown", "blocked", SRC_COOL, f"{ls.player_name(si, m['key'])} can't be traded until {end[:10]}: {short[m['from']]} got him on {at[:10]} "
                             f"(held {days} days{', preseason top ' + str(rules['cooldown']['topRankedCutoff']) if m['key'] in top else ''}).", short[m["from"]]))
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
    rows.append(_row("pending", "info", SRC_PEND, f"{rules['pendingDays']}-day pending period; approval is handled in the group chat / by the commissioner.", None))
    rows.append(_row("tank", "info", SRC_TANK, "Trade Tank eligibility is not evaluated here.", None))
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
