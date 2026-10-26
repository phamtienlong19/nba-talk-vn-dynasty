#!/usr/bin/env python3
"""Update the published Yahoo standings from a saved standings page (or the browser helper's JSON), without Fantasy API access.

    python3 scripts/update_yahoo_standings.py --input ~/Downloads/standings.html              # dry run: parse, validate, compare, report
    python3 scripts/update_yahoo_standings.py --input ~/Downloads/standings.html --apply      # commit the snapshot and refresh the site
    python3 scripts/update_yahoo_standings.py --input capture.json                            # the browser helper's file works the same way
    python3 scripts/update_yahoo_standings.py --engine http                                   # a plain, cookie-less GET of the league page

Outcomes (the report is written to --out, default artifacts/yahoo-standings-update/report.md):

  FAILED     the page or file is not a complete, valid standings table. The whole snapshot is rejected and nothing is changed.
  STALE      Yahoo's own "Last standings update" is OLDER than the published snapshot's. Rejected, unless --allow-historical-restore
             (with --reason) is given for a deliberate restore.
  NO_CHANGE  the same standings content as the published snapshot (the capture time is ignored). Nothing is written.
  CONFLICT   the same Yahoo update time but different content: a revision that needs a human. Nothing is written.
  READY      newer, valid standings. With --apply the snapshot is committed (the previous one is kept) and the site regenerated.

A dry run only writes its disposable report under --out. Standings never change rosters, salaries, trades, the draft or the ledger:
before and after --apply every other file under data/2026-27/ is hashed and must be identical.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_rosters as ir  # noqa: E402
import season_state as ss  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
import yahoo_standings as ys  # noqa: E402
from update_yahoo_rosters import write_outputs  # noqa: E402

ROOT = ys.ROOT
DEFAULT_OUT = os.path.join(ROOT, "artifacts", "yahoo-standings-update")
EXIT = {"READY": 0, "NO_CHANGE": 0, "FAILED": 1, "STALE": 1, "CONFLICT": 1}


def tree_digest(data_dir: str, exclude=("standings",)) -> str:
    """One hash of every file under data_dir except the standings folder: proof that a standings import touched nothing else."""
    h = hashlib.sha256()
    for base, dirs, files in os.walk(data_dir):
        dirs[:] = sorted(d for d in dirs if not (base == data_dir and d in exclude))
        for f in sorted(files):
            p = os.path.join(base, f)
            h.update(os.path.relpath(p, data_dir).encode())
            with open(p, "rb") as fh:
                h.update(hashlib.sha256(fh.read()).digest())
    return h.hexdigest()


def _utc(dt=None) -> str:
    return (dt or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _table(snap) -> list:
    lines = ["| Rank | Team | W-L-T | Pct | GB | Last week |", "|---:|---|---|---:|---:|---|"]
    for t in snap["teams"]:
        name = (t["yahooName"] or "").replace("|", "\\|")        # team names contain pipes ("Hai | Bulls Dynasty")
        lines.append(f"| {t['rank']} | {name} | {t['w']}-{t['l']}-{t['t']} | {t['pct']:.3f} | {ys._gb(t['gb'])} | {t['lastWeek'] or '-'} |")
    return lines


def build_report(outcome, source_name, snap, current, bad, warn, moves, note="", error=None) -> str:
    out = [f"# Update Yahoo Standings — {outcome}", ""]
    if snap:
        out.append(f"Source `{source_name}` · Yahoo update **{snap['sourceUpdatedText'] or '?'}** = {snap['sourceUpdatedAt']} · captured {snap['capturedAt']}")
    else:
        out.append(f"Source `{source_name}`")
    out.append("")
    if error:
        out += ["## Why it was rejected", "", f"- {error}", "", "The published standings were not changed."]
    if bad:
        out += ["## Blocking problems", ""] + [f"- {b}" for b in bad] + ["", "The whole snapshot is rejected; the published standings were not changed."]
    if warn:
        out += ["", "## Warnings (not blocking)", ""] + [f"- {w}" for w in warn]
    if snap and not bad:
        out += ["", "## Validation", "", f"- 16 teams, ranks 1-16 once each, W-L-T and pct consistent, divisions 8/8, wins = losses: **valid**",
                f"- digest `{snap['digest'][:12]}…` (ignores the capture time)"]
        if current:
            out += ["", f"## Compared with the published snapshot (Yahoo update {current.get('sourceUpdatedText') or current.get('sourceUpdatedAt') or 'pre-season'})", ""]
            out += [f"- {m}" for m in moves] if moves else ["- no team changed"]
        else:
            out += ["", "## Compared with the published snapshot", "", "- nothing published yet"]
        out += ["", "## Standings (Yahoo's order)", ""] + _table(snap)
    if note:
        out += ["", note]
    return "\n".join(out) + "\n"


def run(cfg, source, out_dir, data_dir=ss.DATA_DIR, apply=False, allow_restore=False, reason=None, captured_at=None,
        regenerate=False) -> dict:
    """source = {"kind": "html"|"json", "text": str, "name": str}. -> {"outcome", "report", "snapshot"?, "problems"}."""
    standings_dir = os.path.join(data_dir, "standings")
    team_map, _ = ir.load_maps(data_dir)
    franchise_of = lambda tid: yr.franchise_for(cfg, team_map, tid)  # noqa: E731
    season = cfg["season"]
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "report.md")
    current = ys.current_snapshot(standings_dir)

    def finish(outcome, snap=None, bad=(), warn=(), moves=(), note="", error=None, sid=None):
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(build_report(outcome, source["name"], snap, current, list(bad), list(warn), list(moves), note, error))
        res = {"outcome": outcome, "report": report_path, "problems": list(bad) + ([error] if error else []), "exit": EXIT[outcome]}
        if sid:
            res["snapshot"] = sid
        return res

    try:
        if source["kind"] == "json":
            parsed = ys.rows_from_capture_json(json.loads(source["text"]), cfg)
            at, text = parsed["sourceUpdatedAt"], parsed["sourceUpdatedText"]
        else:
            parsed = ys.parse_standings_html(source["text"], cfg)
            text = parsed["sourceUpdatedText"]
            if not text:
                raise ys.StandingsError("NO_TIMESTAMP", 'the page has no "Last standings update" time')
            at = ys.resolve_source_time(text, season)
    except (ys.StandingsError, json.JSONDecodeError) as e:
        return finish("FAILED", error=str(e))
    bad, warn = ys.validate(parsed["rows"], cfg, franchise_of)
    if current and current.get("teams"):
        before = {t["teamId"]: t["division"] for t in current["teams"]}
        for r in parsed["rows"]:
            if r["teamId"] in before and before[r["teamId"]] and before[r["teamId"]] != r["division"]:
                warn.append(f"team {r['teamId']} moved from the {before[r['teamId']]} to the {r['division']} division")
    if bad:
        return finish("FAILED", bad=bad, warn=warn)
    snap = ys.build_snapshot(parsed["rows"], cfg, franchise_of, at, text, captured_at or _utc(), source["kind"], season)
    moves = ys.diff(current, snap)
    outcome = ys.classify(snap, current, allow_restore)
    if outcome == "NO_CHANGE":
        return finish(outcome, snap, warn=warn, moves=moves, note="Same standings as the published snapshot: nothing was written.")
    if outcome == "STALE":
        return finish(outcome, snap, warn=warn, moves=moves, error=(
            f"Yahoo's update time {snap['sourceUpdatedAt']} is older than the published snapshot's {current['sourceUpdatedAt']}. "
            "Use --allow-historical-restore with --reason only for a deliberate restore."))
    if outcome == "CONFLICT":
        return finish(outcome, snap, warn=warn, moves=moves, error=(
            f"Yahoo's update time {snap['sourceUpdatedAt']} is the same as the published snapshot's but the standings differ. "
            "This revision needs a commissioner's review; nothing was overwritten."))
    restore = bool(current and current.get("sourceUpdatedAt") and snap["sourceUpdatedAt"] < current["sourceUpdatedAt"])
    if restore and not reason:
        return finish("FAILED", snap, error="--allow-historical-restore needs --reason TEXT (it is recorded in the history)")
    if not apply:
        return finish(outcome, snap, warn=warn, moves=moves, note="Dry run: nothing was written (add --apply to commit this snapshot).")
    before_hash = tree_digest(data_dir)
    sid = ys.commit(snap, standings_dir, "RESTORE" if restore else "IMPORT", reason if restore else None)
    if tree_digest(data_dir) != before_hash:
        raise RuntimeError("a standings import changed data outside data/2026-27/standings/ (this must never happen)")
    if regenerate:
        for cmd in (["build_league_state.py", "embed"], ["what_if.py", "embed"]):
            subprocess.run([sys.executable, os.path.join(ROOT, "scripts", cmd[0])] + cmd[1:], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    return finish(outcome, snap, warn=warn, moves=moves, sid=sid,
                  note=f"Applied: `data/2026-27/standings/snapshots/{sid}.json` is now current; the previous snapshot is kept. Site regenerated: {bool(regenerate)}.")


def main(argv=None, fetcher=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", help="a saved Yahoo standings page (.html) or the browser helper's capture (.json)")
    ap.add_argument("--engine", choices=("file", "http"), default=None, help="http = a plain GET of the league page (default: file when --input is given)")
    ap.add_argument("--apply", action="store_true", help="commit a READY snapshot and regenerate the site (default is a dry run)")
    ap.add_argument("--dry-run", action="store_true", help="the default; accepted so scripts can say it out loud")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--captured-at", help="UTC ISO time of the capture (default: the file's modified time, or now for --engine http)")
    ap.add_argument("--allow-historical-restore", action="store_true")
    ap.add_argument("--reason", help="why an older snapshot is being restored (recorded in the history)")
    args = ap.parse_args(argv)
    if args.apply and args.dry_run:
        ap.error("--apply and --dry-run contradict each other")
    cfg = yr.load_config()
    engine = args.engine or ("file" if args.input else "http")
    try:
        if engine == "file":
            if not args.input:
                ap.error("--input is required unless --engine http")
            with open(args.input, encoding="utf-8", errors="replace") as f:
                text = f.read()
            kind = "json" if args.input.lower().endswith(".json") else "html"
            captured = args.captured_at or _utc(datetime.datetime.fromtimestamp(os.path.getmtime(args.input), datetime.timezone.utc))
            source = {"kind": kind, "text": text, "name": os.path.basename(args.input)}
        else:
            f = fetcher or yr.HttpFetcher()
            url = cfg["standingsUrl"].format(leagueId=cfg["leagueId"])
            status, _final, body = f.get(url)
            if status != 200:
                raise ys.StandingsError(f"HTTP_{status}", f"{url} answered {status}")
            source = {"kind": "html", "text": body, "name": url}
            captured = args.captured_at or _utc()
    except (ys.StandingsError, OSError) as e:
        os.makedirs(args.out, exist_ok=True)
        err = e if isinstance(e, ys.StandingsError) else ys.StandingsError("UNREADABLE", str(e))
        with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as fh:
            fh.write(build_report("FAILED", args.input or "league page", None, None, [], [], [], error=str(err)))
        write_outputs(os.environ.get("GITHUB_OUTPUT"), {"outcome": "FAILED", "report": os.path.join(args.out, "report.md")})
        print(f"FAILED: {err}")
        return 1
    res = run(cfg, source, args.out, apply=args.apply, allow_restore=args.allow_historical_restore, reason=args.reason,
              captured_at=captured, regenerate=args.apply)
    write_outputs(os.environ.get("GITHUB_OUTPUT"), {"outcome": res["outcome"], "report": res["report"], "snapshot": res.get("snapshot", "")})
    with open(res["report"], encoding="utf-8") as fh:
        print(fh.read())
    print(f"{res['outcome']}: report at {os.path.relpath(res['report'], ROOT)}")
    return res["exit"]


if __name__ == "__main__":
    sys.exit(main())
