#!/usr/bin/env python3
"""Execution wrapper for the `Update Yahoo Rosters` workflow: fetch -> validate -> reconcile -> report (-> apply).

    python3 scripts/update_yahoo_rosters.py --engine browser --storage-state FILE --out artifacts/yahoo-roster-update [--apply]

It adds no scraper and no ownership model: it calls the existing read-only fetcher and validator (yahoo_rosters.py), the
existing reconciliation (yahoo_rosters.reconcile, which runs import_rosters.build_snapshot / diff in memory) and, only with
--apply and an unambiguous result, the existing reviewed importer (import_rosters.commit). The draft pull request the
workflow opens is the review.

Outcomes (written to $GITHUB_OUTPUT as `outcome`):
  FAILED     authentication error, incomplete or empty roster, duplicate Yahoo player id, parse failure, unmapped team.
             Exit 1. Nothing is written except the report.
  NO_CHANGE  nothing material changed: Yahoo matches the verified snapshot, or differs only in lineup-slot moves (bench <->
             active), which do not affect ownership, payroll, IL labels or the checks. Exit 0, no PR.
  CONFLICT   the capture cannot be imported without a human decision: an ownership change that is not a recorded completed
             transaction, a completed transaction Yahoo does not reflect, or any import-blocking problem. Exit 0; the report
             is the deliverable and canonical data is NOT modified.
  READY      only adds / drops / lineup / IL / status changes remain. With --apply the snapshot is committed and the site
             regenerated, in the working tree only (the workflow puts it in a draft PR).

Payroll is the existing top-9 frozen-salary rule over ALL owned players, IL included; IL labels are kept in the output.
Frozen salaries, the keeper freeze, the ledger and historical snapshots are never written (checked by hash on --apply).
Standard library only (plus the existing Playwright dependency when --engine browser).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_rosters as ir  # noqa: E402
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG_TERM = ("O", "OUT", "INJ", "OFS")  # Yahoo statuses that mean out (config/roster_rules.json longTermInjured.outStatuses)
FAILURE_HELP = {
    "AUTH_REQUIRED": "Yahoo returned a sign-in page or the stored session is unusable. Re-run `yahoo_rosters.py login` and "
                     "`export-state` locally, then update the YAHOO_STORAGE_STATE secret (docs/YAHOO_ROSTER_WORKFLOW.md).",
    "CONSENT_REQUIRED": "Yahoo returned a consent page. Sign in once in the login browser, accept it, export the state again.",
    "NO_ROSTER_TABLE": "the page has no roster table (Yahoo layout changed, or not a team page): parse failure.",
    "WRONG_TEAM": "Yahoo returned a different team than requested.",
    "NO_PLAYWRIGHT": "Playwright is not installed on the runner.",
}


class CheckFailed(RuntimeError):
    pass


# ------------------------------------------------------------ small helpers
def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def protected_files(data_dir):
    """Canonical data a roster update must never change (hashes are compared before and after --apply)."""
    out = {}
    for rel in ("salary_freeze.json", "keeper_freeze.json", "trades.json", "draft_state.json", "picks.json",
                "season_transactions.json", "franchises.json", "provisional_players.json", os.path.join("snapshots", "POST_DRAFT.json")):
        p = os.path.join(data_dir, rel)
        if os.path.exists(p):
            out[rel] = _sha(p)
    snaps = os.path.join(data_dir, "rosters", "snapshots")
    for f in sorted(os.listdir(snaps)):
        out[os.path.join("rosters", "snapshots", f)] = _sha(os.path.join(snaps, f))
    return out


def write_outputs(path, values: dict):
    """Append `key=value` lines to $GITHUB_OUTPUT (single-line values only)."""
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for k, v in values.items():
            f.write(f"{k}={str(v).splitlines()[0] if str(v) else ''}\n")


def _fmt_cap(x):
    return f"{x:g}"


# ------------------------------------------------------------------ checks
def _canonical_key(si, aliases, team_row):
    k, _how, _note = ir.resolve_player(si, aliases, team_row)
    return k


def double_checks(si_new, aliases, obs, snap, baseline_checks, new_state) -> dict:
    """Cross-checks on the proposed state. Nothing here changes data; findings go to the report."""
    rules = ss._load(ss.RULES_PATH)
    slot_pos = rules["lineupSlots"]
    out = {"metadataDrift": [], "slotIneligible": [], "healthyOnIL": [], "injuredOffIL": [], "ilLabelsLost": [],
           "payrollMismatch": [], "antiTank": []}
    il_in_obs, il_in_snap = set(), {r["playerKey"] for rows in snap["teams"].values() for r in rows if r.get("slot") in ss.SLOTS_IL}
    for t in obs["teams"]:
        for p in t["players"]:
            row = {"team": t["teamId"], "playerKey": p.get("playerKey"), "playerId": p.get("playerId"), "name": p.get("name"), "slot": p.get("slot")}
            key = _canonical_key(si_new, aliases, row)
            slot = ir.norm_slot(p.get("slot"))
            status = (p.get("injury") or "").upper() or None
            elig = (ls.player_meta(si_new, key).get("eligiblePositions") if key else None) or []
            il_ok = "IL" in elig if elig else None  # Yahoo's own IL eligibility; None = unknown (provisional / unlisted player)
            if slot in ss.SLOTS_IL:
                il_in_obs.add(key)
                if il_ok is False and status not in LONG_TERM:
                    # IL eligibility comes from the player registry, which can lag a day: a player Yahoo now shows as Out is fine
                    out["healthyOnIL"].append(f"{p['name']} (team {t['teamId']}) is on IL but Yahoo lists him as neither IL-eligible nor Out/injured")
                elif il_ok is None and status in (None, "P"):
                    out["healthyOnIL"].append(f"{p['name']} (team {t['teamId']}) is on IL but Yahoo shows no injury status")
            elif il_ok or status in LONG_TERM:
                why = ("IL-eligible per Yahoo" + (f", status {status}" if status else "")) if il_ok else f"status {status}"
                out["injuredOffIL"].append(f"{p['name']} (team {t['teamId']}) is injured ({why}) but sits in {slot or 'no slot'}, not IL")
            meta = ls.player_meta(si_new, key) if key else {}
            if meta and (p.get("nbaTeam") or p.get("positions")):  # compare what the team page actually showed
                have = ((meta.get("nbaTeam") or ""), (meta.get("displayPosition") or "").replace(" ", ""))
                seen = ((p.get("nbaTeam") or have[0]), (p.get("positions") or have[1]).replace(" ", ""))
                if have != seen:
                    out["metadataDrift"].append(f"{p['name']}: our data {have[0]} {have[1]}, Yahoo team page {seen[0]} {seen[1]}")
            if slot in slot_pos:
                elig = {x.strip() for x in (p.get("positions") or "").split(",")}
                if elig and not (elig & set(slot_pos[slot])):
                    out["slotIneligible"].append(f"{p['name']} ({p.get('positions')}) is in the {slot} slot")
    out["ilLabelsLost"] = sorted(il_in_obs - il_in_snap)
    for fid in si_new["franchises"]:  # payroll double check: top 9 of ALL owned players, IL included, recomputed independently
        keys = ls.team_players(si_new, new_state, fid)
        caps = sorted((ls.player_cap(si_new, k) for k in keys), reverse=True)
        want = sum(caps[: si_new["capCountTop"]]) if si_new.get("capCountTop") else sum(caps)
        got = ls.team_cap(si_new, new_state, fid)
        if want != got:
            out["payrollMismatch"].append(f"{si_new['shorts'][fid]}: {got:g} != top-9 sum {want:g}")
    for fid in si_new["franchises"]:
        now = ss.roster_checks(si_new, new_state, fid)
        for key, label in (("injured", "injured"), ("singlePosition", "single-position"), ("coverage", "position coverage"), ("lineup", "full lineup")):
            lv = now[key]["level"]
            if lv != "ok":
                was = baseline_checks[fid][key]["level"]
                detail = {"injured": f"{now['injured']['count']}/{now['injured']['max']}",
                          "singlePosition": f"{now['singlePosition']['count']}/{now['singlePosition']['max']}",
                          "coverage": ", ".join([f"short {p}" for p in now["coverage"]["short"]] + [f"short {c}" for c in now["coverage"]["shortCombo"]]),
                          "lineup": f"{now['lineup']['filled']}/{now['lineup']['slots']}" + (f" (cannot fill {', '.join(now['lineup']['empty'])})" if now["lineup"]["empty"] else "")}[key]
                out["antiTank"].append({"team": si_new["shorts"][fid], "check": label, "level": lv, "detail": detail,
                                        "isNew": was != lv})
    return out


# ------------------------------------------------------------------ report
FLAG_KEYS = ("metadataDrift", "slotIneligible", "healthyOnIL", "injuredOffIL")


def flag_count(dc) -> int:
    """Compliance findings worth a human look: anti-tank limits not ok + roster/IL/metadata cross-check hits."""
    return len(dc["antiTank"]) + sum(len(dc[k]) for k in FLAG_KEYS)


def checks_section(dc) -> list:
    """The anti-tank limits and the roster / IL cross-checks, as report lines (identical for every outcome)."""
    L = ["", "## Anti-tank roster checks (evidence only)", ""]
    if dc["antiTank"]:
        L += [f"- {x['team']} — {x['check']}: **{x['level']}** {x['detail']}" + (" (new)" if x["isNew"] else "") for x in dc["antiTank"]]
    else:
        L.append("- every team is within every limit")
    L += ["", "## Double checks", ""]
    for key, title in (("metadataDrift", "Team / position eligibility differs from our data (run `refresh_player_metadata.py`)"),
                       ("slotIneligible", "Player in a lineup slot he is not eligible for"),
                       ("healthyOnIL", "Parked on IL but not IL-eligible"), ("injuredOffIL", "Injured (IL-eligible or Out) but not on IL"),
                       ("ilLabelsLost", "IL labels lost in the snapshot"), ("payrollMismatch", "Payroll mismatch")):
        items = dc[key]
        L.append(f"- {title}: " + ("none" if not items else f"**{len(items)}**"))
        L += [f"  - {x}" for x in items[:25]]
    return L


def no_change_report(obs, si, dc, why, run_info="") -> str:
    """NO_CHANGE is still a compliance check: the rosters are re-examined against the rules on every run."""
    L = ["# Update Yahoo Rosters — NO_CHANGE", "", f"Captured {obs['capturedAt']} · {obs['method']} · {len(obs['teams'])} teams · "
         f"{sum(len(t['players']) for t in obs['teams'])} players" + (f" · {run_info}" if run_info else ""), "", why,
         "", f"**Compliance flags on the current rosters: {flag_count(dc)}**" + (" — see below; they are for the commissioner, nothing was changed." if flag_count(dc) else " — none.")]
    return "\n".join(L + checks_section(dc)) + "\n"


def build_report(outcome, obs, check, rec, dc, si, baseline, new_state, conflicts, run_info="") -> str:
    L = [f"# Update Yahoo Rosters — {outcome}", ""]
    L.append(f"Captured {obs['capturedAt']} · {obs['method']} · league {obs['leagueId']} · {len(obs['teams'])} teams · "
             f"{sum(len(t['players']) for t in obs['teams'])} players" + (f" · {run_info}" if run_info else ""))
    if outcome == "FAILED":
        L += ["", "## Why the run failed", ""]
        for b in check["blocking"]:
            help_ = FAILURE_HELP.get(b["code"].replace("FETCH_", ""), "")
            L.append(f"- **{b['code']}** — {b['detail']}" + (f"\n  - {help_}" if help_ else ""))
        L += ["", "Nothing was written. Canonical data is unchanged."]
        return "\n".join(L) + "\n"
    d = rec["diff"]
    L += ["", "## Summary", "",
          f"- ownership adds (on Yahoo only): **{len(d['added'])}** · drops (ours only): **{len(d['dropped'])}** · "
          f"team changes: **{len(d['changedTeam'])}** · IL moves: {len(d['ilMoves'])} · lineup-only: {len(d['lineupOnly'])} · unchanged: {d['unchanged']}",
          "- salaries: frozen (`salary_freeze.json` is never written); payroll = top 9 of ALL owned players, **IL included**; "
          f"unlisted players are $0 by league rule ({len(rec['report'].get('unlisted', []))} new)"]
    if conflicts:
        L += ["", "## Unresolved discrepancies — needs a human decision (canonical data NOT modified)", ""]
        L += [f"- {c}" for c in conflicts]
    snap_status = {r["playerKey"]: r.get("status") for rows in rec["snapshot"]["teams"].values() for r in rows}
    snap_slot = {r["playerKey"]: r.get("slot") for rows in rec["snapshot"]["teams"].values() for r in rows}

    def tag(k):  # lineup slot (IL emphasised) and Yahoo status, as observed
        slot = snap_slot.get(k)
        out = f" **[{slot}]**" if slot in ss.SLOTS_IL else (f" [{slot}]" if slot else "")
        return out + (f" `{snap_status[k]}`" if snap_status.get(k) else "")

    for key, title in (("added", "Adds — on Yahoo, not on our roster"), ("dropped", "Removals — on our roster, not on Yahoo"),
                       ("changedTeam", "Ownership changes — a player is on a different team than ours")):
        if d[key]:
            L += ["", f"## {title}", ""]
            for x in d[key]:
                if key == "changedTeam":
                    L.append(f"- {x['player']}: ours **{x['from']}** → Yahoo **{x['to']}** — {x['note']}")
                elif key == "added":
                    L.append(f"- {x['player']} → {x['team']}{tag(x['key'])}")
                else:
                    L.append(f"- {x['player']} ({x['team']}) — {x['note']}")
    if d["ilMoves"]:
        L += ["", "## IL moves (payroll unchanged: IL players count like anyone else)", ""]
        L += [f"- {x['player']} ({x['team']}): {x['from']} → {x['to']}" for x in d["ilMoves"]]
    if d["lineupOnly"]:
        L += ["", f"{len(d['lineupOnly'])} players also moved between bench and lineup slots (not listed: no effect on ownership, payroll or the checks)."]
    old = baseline["status"]
    changes = [(k, old.get(k), s) for k, s in sorted(snap_status.items(), key=lambda kv: ls.player_name(si, kv[0])) if old.get(k) != s]
    changes += [(k, o, None) for k, o in sorted(old.items(), key=lambda kv: ls.player_name(si, kv[0])) if k not in snap_status and k in snap_slot]
    if changes:
        L += ["", "## Status changes", ""] + [f"- {ls.player_name(si, k) if ls.player_meta(si, k) else k}: {o or '—'} → {n or '—'}" for k, o, n in changes[:80]]
    L += ["", "## Salary-cap effects (top 9 frozen salaries, IL included)", "", "| Team | Players | IL | Counted before → after | Healthy | Band |", "|---|---|---|---|---|---|"]
    for p in rec["payroll"]:
        fid = next(f for f, s in si["shorts"].items() if s == p["team"])
        il_cap = sum(r["c"] for r in ls.team_roster(si, new_state, fid) if new_state["slots"].get(r["k"]) in ss.SLOTS_IL and not r["x"])
        move = f"{_fmt_cap(p['capNow'])} → {_fmt_cap(p['capIfImported'])}" + (f" ({p['capIfImported'] - p['capNow']:+g})" if p["capIfImported"] != p["capNow"] else "")
        L.append(f"| {p['team']} | {p['count']} | {p['il']} | {move} | {_fmt_cap(p['capIfImported'] - il_cap)} | {ls.cap_status(si, p['capIfImported'])} |")
    if rec["salaryEvidence"]:
        L += [""] + [f"- Yahoo keeper-salary label for {x['player']} is {x['yahooKeeperSalary']:g}; frozen salary {x['frozen']:g} (frozen wins)" for x in rec["salaryEvidence"]]
    L += checks_section(dc)
    if rec["report"]["warnings"]:
        prov = [w for w in rec["report"]["warnings"] if w["code"] == "PROVISIONAL_LINK_CANDIDATE"]
        unl = [w for w in rec["report"]["warnings"] if w["code"] == "UNLISTED_PLAYER_ZERO_SALARY"]
        L += ["", f"- provisional rookies listed under Yahoo ids (link candidates, not linked): {len(prov)}",
              f"- unlisted players priced at $0 by league rule: {len(unl)}"]
    L += ["", "## Recorded transactions", ""] + ([f"- {t['txnId']} {t.get('label') or ''}: {'reflected on Yahoo' if t['reflected'] else '**NOT reflected**'}"
                                                  for t in d["transactions"]] or ["- none pending"])
    L += ["", "Differences are observations. No transaction was created and no historical ownership was overridden."]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------- run
def run(cfg, fetcher, out_dir, data_dir=ss.DATA_DIR, apply=False, regenerate=False, delay=None, run_info="", now=None):
    """-> {outcome, report, observation, exit}. Writes report.md / observation.json (+ the data change with apply)."""
    os.makedirs(out_dir, exist_ok=True)
    started = now or yr.now_utc()
    teams, errors = yr.fetch_teams(cfg, cfg["teamIds"], fetcher, delay=delay)
    obs = yr.make_observation(cfg, teams, started, fetcher.method, errors, requested=cfg["teamIds"])
    check = yr.validate_observation(obs, cfg, True)
    result = {"outcome": "FAILED", "exit": 1, "observation": None}

    def finish(outcome, report, exit_code, obs_saved=True):
        with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
            f.write(report)
        if obs_saved and obs["teams"]:
            ss._write(os.path.join(out_dir, "observation.json"), obs)
            result["observation"] = os.path.join(out_dir, "observation.json")
        result.update(outcome=outcome, report=report, exit=exit_code)
        return result

    if check["blocking"]:
        return finish("FAILED", build_report("FAILED", obs, check, None, None, None, None, None, [], run_info), 1, obs_saved=False)
    si = ss.load_season(ls.load_inputs(data_dir=data_dir), data_dir=data_dir)
    yr.check_game_key(si, cfg)
    rec = yr.reconcile(si, obs, data_dir)
    if rec["unmappedTeams"] or rec["diff"] is None:
        bad = {"blocking": [{"code": "UNMAPPED_TEAM", "detail": f"Yahoo teams {rec['unmappedTeams']} have no yahooTeamKey in rosters/team_map.json"}
                            if rec["unmappedTeams"] else {"code": "DUPLICATE_OR_UNMATCHED", "detail": str(rec["report"]["blocking"][:3])}]}
        return finish("FAILED", build_report("FAILED", obs, bad, None, None, None, None, None, [], run_info), 1)
    snap, d = rec["snapshot"], rec["diff"]
    si_new = ir.with_unlisted(si, rec["report"])
    si2 = dict(si_new, rosterSnapshot=snap)
    new_state = ss.season_state(si2)
    base_state = ss.season_state(si)
    baseline = {"status": base_state.get("status", {}), "checks": {f: ss.roster_checks(si, base_state, f) for f in si["franchises"]}}
    _, aliases = ir.load_maps(data_dir)
    dc = double_checks(si2, aliases, obs, snap, baseline["checks"], new_state)
    result["flags"] = flag_count(dc)
    if dc["payrollMismatch"] or dc["ilLabelsLost"]:
        check = {"blocking": [{"code": "INTERNAL_CHECK", "detail": "; ".join(dc["payrollMismatch"] + [f"IL label lost: {k}" for k in dc["ilLabelsLost"]])}]}
        return finish("FAILED", build_report("FAILED", obs, check, None, None, None, None, None, [], run_info), 1)
    if snap["digest"] == si["rosterSnapshot"]["digest"]:
        return finish("NO_CHANGE", no_change_report(obs, si2, dc, f"Yahoo matches the current verified snapshot "
                                                    f"`{si['rosterSnapshot']['snapshotId']}`. Nothing to do.", run_info), 0)
    conflicts = []
    for b in rec["report"]["blocking"]:
        conflicts.append(f"import-blocking {b['code']}: {b.get('team', '')} {b.get('detail')}".replace("  ", " "))
    conflicts += [f"ownership change not in the ledger: {x['player']} ours {x['from']} → Yahoo {x['to']} ({x['note']})" for x in d["changedTeam"]]
    conflicts += [f"completed transaction {t['txnId']} is not reflected on Yahoo" for t in d["transactions"] if not t["reflected"]]
    if snap["verifiedAt"] <= si["rosterSnapshot"]["verifiedAt"]:
        conflicts.append(f"the capture ({snap['verifiedAt']}) is not newer than the current verified snapshot ({si['rosterSnapshot']['verifiedAt']})")
    if any(h.get("digest") == snap["digest"] for h in si["rosterIndex"]["history"]):
        conflicts.append("Yahoo matches an OLDER verified snapshot exactly (a reverted state): needs a human look")
    new_status = {r["playerKey"]: r["status"] for rows in snap["teams"].values() for r in rows if r.get("status")}
    status_changed = new_status != {k: v for k, v in baseline["status"].items() if k in new_state["playerOwner"]}
    material = bool(d["added"] or d["dropped"] or d["changedTeam"] or d["ilMoves"] or status_changed or rec["report"].get("unlisted"))
    if not conflicts and not material:  # lineup-slot churn only: not worth a snapshot or a PR
        return finish("NO_CHANGE", no_change_report(
            obs, si2, dc, f"Ownership, IL labels and statuses match the current verified snapshot `{si['rosterSnapshot']['snapshotId']}`; "
                          f"{len(d['lineupOnly'])} players only moved between bench and lineup slots, which does not affect ownership, "
                          "payroll or the checks. Nothing to do.", run_info), 0)
    outcome = "CONFLICT" if conflicts else "READY"
    report = build_report(outcome, obs, check, rec, dc, si2, baseline, new_state, conflicts, run_info)
    if outcome == "READY" and apply:
        before = protected_files(data_dir)
        rel = ir.commit(si, snap, rec["report"], d, data_dir, reviewed=True)  # the draft PR is the human review
        after = protected_files(data_dir)
        changed = [k for k in before if before[k] != after.get(k)]
        if changed or set(after) - set(before) != {os.path.join("rosters", rel)}:
            raise CheckFailed(f"protected canonical data changed: {changed}")
        if regenerate:
            for cmd in (["build_league_state.py", "sync-ledger"], ["build_league_state.py", "embed"], ["what_if.py", "embed"]):
                subprocess.run([sys.executable, os.path.join(ROOT, "scripts", cmd[0])] + cmd[1:], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
        report += f"\nApplied: `data/2026-27/rosters/{rel}` ({snap['snapshotId']}); site regenerated: {bool(regenerate)}.\n"
        result["snapshot"] = snap["snapshotId"]
    return finish(outcome, report, 0)


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", choices=("http", "browser"), default="browser")
    ap.add_argument("--storage-state", default=os.environ.get(yr.STATE_ENV))
    ap.add_argument("--out", default=os.path.join(ROOT, "artifacts", "yahoo-roster-update"))
    ap.add_argument("--apply", action="store_true", help="commit the snapshot and regenerate the site when the result is READY")
    args = ap.parse_args(argv)
    cfg = yr.load_config()
    info = f"GitHub run {os.environ['GITHUB_RUN_ID']}" if os.environ.get("GITHUB_RUN_ID") else ""
    try:
        if fetcher is None:
            fetcher = yr.HttpFetcher() if args.engine == "http" else yr.BrowserFetcher(storage_state=args.storage_state)
    except yr.FetchError as e:
        os.makedirs(args.out, exist_ok=True)
        rep = build_report("FAILED", {"capturedAt": yr.now_utc(), "method": args.engine, "leagueId": cfg["leagueId"], "teams": []},
                           {"blocking": [{"code": e.code, "detail": e.detail}]}, None, None, None, None, None, [], info)
        with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f:
            f.write(rep)
        write_outputs(os.environ.get("GITHUB_OUTPUT"), {"outcome": "FAILED", "report": os.path.join(args.out, "report.md")})
        print(f"FAILED: {e}")
        return 1
    try:
        res = run(cfg, fetcher, args.out, apply=args.apply, regenerate=args.apply, delay=None, run_info=info)
    finally:
        fetcher.close()
    write_outputs(os.environ.get("GITHUB_OUTPUT"), {"outcome": res["outcome"], "report": os.path.join(args.out, "report.md"),
                                                    "snapshot": res.get("snapshot", ""), "flags": res.get("flags", 0)})
    print(f"{res['outcome']}: report at {os.path.relpath(os.path.join(args.out, 'report.md'), ROOT)}")
    if res.get("flags"):
        print(f"::notice title=Compliance flags::{res['flags']} roster / IL / anti-tank finding(s) for the commissioner. See the report (job summary); nothing was changed.")
    if res["outcome"] == "CONFLICT":
        print("::warning::Yahoo differs from the official rosters in a way that needs a human decision. See the report; nothing was changed.")
    return res["exit"]


if __name__ == "__main__":
    sys.exit(main())
