#!/usr/bin/env python3
"""Lineup-lock EVIDENCE: who sat in which slot, with which Yahoo status, at the moment each game locked. Append-only, never a verdict.

    python3 scripts/lineup_log.py --feed live.json [--previous prev.json] --log-dir lineup-log/

Run by the live-feed loop after every build (scripts/live_feed_loop.sh, every 4 minutes in game hours). A Yahoo lineup locks per player at his game's
tip-off, so a status that changes later (a healthy player taken off IL after the fact, a scratch, a corrected injury) used to erase the proof of what
the lineup looked like when it counted. For every player whose game turns live or final it appends ONE lock record to <log-dir>/<Pacific game date>.jsonl:

  {"kind": "lock", "date", "capturedAt", "team": franchise, "teamName", "k": "478.p.<id>", "n", "slot", "st", "ie", "il", "game", "gs", "flags": [...]}

plus one {"kind": "first_tip", ...} whole-league snapshot of every team's lineup the first time any game of the day is live. Flags are facts the rules
already define, computed from what was on the page at that moment:

  healthy_on_il  in an IL slot but Yahoo says he is not IL-eligible (season_state.il_state), the evidence the commissioner needs for a violation
  out_starter    a starting slot held by a player Yahoo lists as out, with a game today
  star_benched   a top-50 (preseason O-Rank) healthy player on the bench with a game today

The record is as precise as the polling interval (a game that tipped up to 4 minutes before the capture shows what the page showed then). Records are
append-only: an existing line is never rewritten, a player is recorded once per day, and a day before the capture's own date is never touched. Tank
intent, AFK verdicts and points stay the commissioner's; this only keeps what the page showed. Standard library only."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import live_lineups as lln  # noqa: E402
import live_schedule as lsch  # noqa: E402
import season_state as ss  # noqa: E402

LOCKED = ("live", "final")
RULES = None


def _rules():
    global RULES
    if RULES is None:
        RULES = ss._load(ss.RULES_PATH)["longTermInjured"]
    return RULES


def game_date(feed):
    """The Yahoo day the games belong to: the US Pacific date of the capture (Yahoo's day rolls at 12:00 am Pacific). NOT feed['dayDate'], which is
    the last day with stats (yesterday while today's games are still ahead)."""
    at = feed.get("asOf")
    if not isinstance(at, str):
        raise ValueError("feed has no asOf")
    import datetime
    import zoneinfo
    dt = datetime.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(zoneinfo.ZoneInfo("America/Los_Angeles")).date().isoformat()


def registry_il(registry):
    """{playerId: True/False} from the registry's IL token; players it does not list are absent (unknown)."""
    out = {}
    for p in (registry or {}).get("players", []):
        elig = p.get("eligiblePositions") or []
        if elig and p.get("playerId") is not None:
            out[str(p["playerId"])] = "IL" in elig
    return out


def _flags(row, il_ok, ranks):
    slot, st = row.get("s"), (row.get("st") or "").upper() or None
    flags = []
    il = ss.il_state(slot, st, il_ok, _rules())
    if il == "healthy_on_il":
        flags.append("healthy_on_il")
    if slot in lln.STARTING and st in lsch.OUT:
        flags.append("out_starter")
    rank = ranks.get(str(row.get("p")))
    if slot == "BN" and rank is not None and rank <= lln.STAR_RANK and st not in lsch.OUT:
        flags.append("star_benched")
    return il, flags


def records(feed, seen_players, il_map, ranks, first_tip_done, captured_at):
    """-> [new records] for this feed. seen_players = playerIds already recorded for that day."""
    date = game_date(feed)
    out, any_live = [], False
    teams = [t for m in feed.get("matchups", []) for t in m.get("teams", [])]
    for t in teams:
        for r in t.get("roster", []):
            if r.get("gs") in LOCKED and r.get("n"):
                any_live = True
    for t in teams:
        for r in t.get("roster", []):
            if r.get("gs") not in LOCKED or not r.get("n") or str(r.get("p")) in seen_players:
                continue
            il, flags = _flags(r, il_map.get(str(r.get("p"))), ranks)
            rec = {"kind": "lock", "date": date, "capturedAt": captured_at, "team": t.get("team"), "teamName": t.get("name"),
                   "k": f"478.p.{r['p']}" if r.get("p") else None, "n": r.get("n"), "slot": r.get("s"), "st": r.get("st") or None,
                   "il": il, "game": r.get("g"), "gs": r.get("gs"), "flags": flags}
            if str(r.get("p")) in il_map:
                rec["ie"] = 1 if il_map[str(r["p"])] else 0
            out.append(rec)
    if any_live and not first_tip_done:
        snap = {t.get("team"): [{"p": r.get("p"), "n": r.get("n"), "slot": r.get("s"), "st": r.get("st") or None, "gs": r.get("gs")}
                                for r in t.get("roster", []) if r.get("n")] for t in teams}
        out.insert(0, {"kind": "first_tip", "date": date, "capturedAt": captured_at, "teams": snap})
    return out


def read_day(path):
    seen, first = set(), False
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("kind") == "first_tip":
                    first = True
                elif rec.get("kind") == "lock" and rec.get("k"):
                    seen.add(rec["k"].split(".p.")[-1])
    return seen, first


def append(log_dir, feed, il_map, ranks, captured_at):
    """Append this feed's new lock records to <log_dir>/<Pacific game date>.jsonl. Returns the number of records written."""
    date = game_date(feed)
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, date + ".jsonl")
    seen, first = read_day(path)
    new = records(feed, seen, il_map, ranks, first, captured_at)
    if new:
        with open(path, "a", encoding="utf-8") as f:                      # append mode: an existing line can never be changed
            for rec in new:
                f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(new)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed", required=True)
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--registry", default=os.path.join(HERE, "..", "data", "yahoo", "player_registry.json"))
    a = ap.parse_args(argv)
    with open(a.feed, encoding="utf-8") as f:
        feed = json.load(f)
    with open(a.registry, encoding="utf-8") as f:
        il_map = registry_il(json.load(f))
    n = append(a.log_dir, feed, il_map, lln.load_ranks(), feed.get("asOf"))
    print(f"lineup log: {n} new record(s) for {game_date(feed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
