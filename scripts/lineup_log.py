#!/usr/bin/env python3
"""Lineup-lock EVIDENCE: who sat in which slot, with which Yahoo status, at the moment each game locked. Append-only, never a verdict.

    python3 scripts/lineup_log.py --feed live.json [--previous prev.json] --log-dir lineup-log/

Run by the live-feed loop after every build (scripts/live_feed_loop.sh, every 4 minutes in game hours). A Yahoo lineup locks per player at his game's
tip-off, so a status that changes later (a healthy player taken off IL after the fact, a scratch, a corrected injury) used to erase the proof of what
the lineup looked like when it counted. For every player whose game turns live or final it appends ONE lock record to <log-dir>/<Pacific game date>.jsonl:

  {"kind": "lock", "date", "capturedAt", "team": franchise, "teamName", "k": "478.p.<id>", "n", "slot", "st", "ie", "il", "game", "gs", "pos", "flags": [...],
   "pre": {"st", "at"}}      (pre: only when the read before, at most 30 minutes older, still showed the game ahead)

plus one {"kind": "first_tip", ...} whole-league snapshot of every team's lineup the first time any game of the day is live, and the day's history:
{"kind": "day_start", players: [...]} at the first read, {"kind": "state", ...} for every later change of team / slot / status / having a game (slot
null: left the roster) and {"kind": "gap", from, to} where more than 30 minutes passed unread. scripts/lineup_review.py judges lineups from these. Flags are facts the rules
already define, computed from what was on the page at that moment:

  healthy_on_il  in an IL slot but Yahoo says he is not IL-eligible (season_state.il_state), the evidence the commissioner needs for a violation
  out_starter    a starting slot held by a player Yahoo lists as out, with a game today
  star_benched   a top-50 (preseason O-Rank) healthy player on the bench with a game today

The record is as precise as the polling interval (a game that tipped up to 4 minutes before the capture shows what the page showed then). Records are
append-only: an existing line is never rewritten, a player is recorded once per day, and a day before the capture's own date is never touched. Tank
intent, AFK verdicts and points stay the commissioner's; this only keeps what the page showed. Standard library only."""
import argparse
import datetime
import json
import os
import sys
import zoneinfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import live_lineups as lln  # noqa: E402
import live_schedule as lsch  # noqa: E402
import season_state as ss  # noqa: E402

LOCKED = ("live", "final")
PRE_MAX_MINUTES = 30
RULES = None


def _rules():
    global RULES
    if RULES is None:
        RULES = ss._load(ss.RULES_PATH)["longTermInjured"]
    return RULES


def _at(iso):
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def game_date(feed):
    """The Yahoo day the games belong to: the US Pacific date of the capture (Yahoo's day rolls at 12:00 am Pacific). NOT feed['dayDate'], which is
    the last day with stats (yesterday while today's games are still ahead)."""
    at = feed.get("asOf")
    if not isinstance(at, str):
        raise ValueError("feed has no asOf")
    dt = _at(at)
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


def before_tip(feed, previous):
    """{playerId: {"st", "at"}} for the players the previous read still showed ahead of their game: the status that stood when the lineup locked. A
    read older than PRE_MAX_MINUTES (or of another game day) says nothing about the lock, so it is ignored."""
    try:
        if not previous or game_date(previous) != game_date(feed):
            return {}
        gap = _at(feed["asOf"]) - _at(previous["asOf"])
    except (ValueError, KeyError, TypeError):
        return {}
    if not datetime.timedelta(0) <= gap <= datetime.timedelta(minutes=PRE_MAX_MINUTES):
        return {}
    return {str(r.get("p")): {"st": r.get("st") or None, "at": previous["asOf"]}
            for m in previous.get("matchups", []) for t in m.get("teams", []) for r in t.get("roster", []) if r.get("gs") == "upcoming" and r.get("p")}


def records(feed, seen_players, il_map, ranks, first_tip_done, captured_at, previous=None):
    """-> [new records] for this feed. seen_players = playerIds already recorded for that day; previous = the read before this one."""
    pre = before_tip(feed, previous)
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
                   "il": il, "game": r.get("g"), "gs": r.get("gs"), "pos": r.get("pos"), "flags": flags}
            if str(r.get("p")) in pre:
                rec["pre"] = pre[str(r.get("p"))]
            if str(r.get("p")) in il_map:
                rec["ie"] = 1 if il_map[str(r["p"])] else 0
            out.append(rec)
    if any_live and not first_tip_done:
        snap = {t.get("team"): [{"p": r.get("p"), "n": r.get("n"), "slot": r.get("s"), "st": r.get("st") or None, "gs": r.get("gs")}
                                for r in t.get("roster", []) if r.get("n")] for t in teams}
        out.insert(0, {"kind": "first_tip", "date": date, "capturedAt": captured_at, "teams": snap})
    return out


def _entry(team, row):
    return {"p": str(row.get("p")), "n": row.get("n"), "team": team, "slot": row.get("s"), "st": row.get("st") or None, "g": row.get("g"), "pos": row.get("pos")}


def roster_now(feed):
    """({playerId: entry}, {teams in this read}) for every named player on every team."""
    out, teams = {}, set()
    for m in feed.get("matchups", []):
        for t in m.get("teams", []):
            teams.add(t.get("team"))
            for r in t.get("roster", []):
                if r.get("n") and r.get("p"):
                    out[str(r["p"])] = _entry(t.get("team"), r)
    return out, teams


def _mark(e):
    """What a change is: the team, the slot, the status, or gaining / losing a game today (the game's text changes with the score)."""
    return (e.get("team"), e.get("slot"), e.get("st"), bool(e.get("g")))


def state_records(feed, state, previous, captured_at):
    """The history the review needs to judge "what stood an hour before tip": one `day_start` with every rostered player, then a `state` record per
    change (slot None = no longer on the roster). A `gap` record says that nobody read the lineups for more than PRE_MAX_MINUTES, so what stood in
    between is unknown. `state` is the day file replayed (None before the day's first read), which is why a restarted loop carries on cleanly."""
    date = game_date(feed)
    now, teams = roster_now(feed)
    if not now:
        return []
    if state is None:
        return [{"kind": "day_start", "date": date, "capturedAt": captured_at, "players": list(now.values())}]
    out = []
    try:
        if _at(feed["asOf"]) - _at(previous["asOf"]) > datetime.timedelta(minutes=PRE_MAX_MINUTES):
            out.append({"kind": "gap", "date": date, "capturedAt": captured_at, "from": previous["asOf"], "to": feed["asOf"]})
    except (ValueError, KeyError, TypeError):
        out.append({"kind": "gap", "date": date, "capturedAt": captured_at, "from": None, "to": feed.get("asOf")})
    for pid, e in now.items():
        if pid not in state or _mark(state[pid]) != _mark(e):
            out.append(dict({"kind": "state", "date": date, "capturedAt": captured_at}, **e))
    for pid, e in state.items():
        if pid not in now and e.get("slot") is not None and e.get("team") in teams:        # a team missing from the read says nothing
            out.append(dict({"kind": "state", "date": date, "capturedAt": captured_at}, **dict(e, slot=None)))
    return out


def read_day(path):
    """-> (playerIds with a lock record, first_tip written?, the roster state the file ends in or None before its day_start)."""
    seen, first, state = set(), False, None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                kind = rec.get("kind")
                if kind == "first_tip":
                    first = True
                elif kind == "lock" and rec.get("k"):
                    seen.add(rec["k"].split(".p.")[-1])
                elif kind == "day_start":
                    state = {e["p"]: e for e in rec.get("players", [])}
                elif kind == "state" and state is not None:
                    state[rec["p"]] = rec
    return seen, first, state


def append(log_dir, feed, il_map, ranks, captured_at, previous=None):
    """Append this feed's new records (state changes, then locks) to <log_dir>/<Pacific game date>.jsonl. Returns the number written."""
    date = game_date(feed)
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, date + ".jsonl")
    seen, first, state = read_day(path)
    new = state_records(feed, state, previous, captured_at) + records(feed, seen, il_map, ranks, first, captured_at, previous)
    if new:
        with open(path, "a", encoding="utf-8") as f:                      # append mode: an existing line can never be changed
            for rec in new:
                f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(new)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed", required=True)
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--previous", help="the feed read before this one: gives each locked player's status from before the tip")
    ap.add_argument("--registry", default=os.path.join(HERE, "..", "data", "yahoo", "player_registry.json"))
    a = ap.parse_args(argv)
    with open(a.feed, encoding="utf-8") as f:
        feed = json.load(f)
    with open(a.registry, encoding="utf-8") as f:
        il_map = registry_il(json.load(f))
    previous = None
    if a.previous and os.path.exists(a.previous):
        try:
            with open(a.previous, encoding="utf-8") as f:
                previous = json.load(f)
        except ValueError:
            pass                                                              # a torn file only costs the before-tip status
    n = append(a.log_dir, feed, il_map, lln.load_ranks(), feed.get("asOf"), previous)
    print(f"lineup log: {n} new record(s) for {game_date(feed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
