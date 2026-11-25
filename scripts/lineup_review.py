#!/usr/bin/env python3
"""What a commissioner would hold against a manager, from the lineup log. Facts and an outcome, never a verdict, points or a view on intent.

    python3 scripts/lineup_review.py --log-dir lineup-log/ --feed live.json [--player-log player_log.json]     # adds "lineupReview" to the feed

Outcomes (the owner's case table, docs/LIVE_DATA.md "Lineup review"; case numbers are the table's rows):

    fault   the manager could have avoided it; counts toward the weekly misset rule
    il      an injured-list rule item (an Out player kept off an open IL slot); listed, not counted
    watch   shown, not counted: inside a grace period, an uncertain status, or no read of the lineup in time to judge
    cleared nothing the manager could have done (late news, no bench cover, no IL room, a sudden return); only counted

A status is judged as Yahoo showed it ONE HOUR before the player's tip (`noticeMinutes`); a slot as it stood when the game locked. The tip is taken
from the first read that shows the game on; a game first seen finished, or a silence in the log across the hour, makes the lineup unconfirmed.
Standard library only; pure functions apart from main()."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import live_lineups as lln  # noqa: E402
import season_state as ss  # noqa: E402

FAULT, IL, WATCH = "fault", "il", "watch"
IL_SLOTS = ("IL", "IL+")


def load_rules():
    roster = ss._load(ss.RULES_PATH)
    trade = ss._load(os.path.join(os.path.dirname(ss.RULES_PATH), "trade_rules.json"))
    return dict(roster["lineupReview"], slots=roster["lineupSlots"], il=roster["longTermInjured"], ilSlots=trade["yahoo"]["ilSlots"])


def _at(iso):
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")


def _date(iso):
    return datetime.date.fromisoformat(iso)


def _fill(players, slots):
    """Greedy-with-rearrangement assignment: players = [(pid, positions)] in priority order; -> the pids that all fit at once, taken in order (a
    later player never pushes an earlier one out)."""
    match, placed = {}, []
    pos_of = {p: set(pos) for p, pos in players}

    def place(pid, seen):
        for slot, takes in slots.items():
            if slot in seen or not (pos_of[pid] & set(takes)):
                continue
            seen.add(slot)
            if slot not in match or place(match[slot], seen):
                match[slot] = pid
                return True
        return False

    for pid, _pos in players:
        if place(pid, set()):
            placed.append(pid)
    return placed


class Day:
    """One log file replayed: what stood at any moment, and every lock."""

    def __init__(self, date, records):
        self.date = date
        self.start = next((r for r in records if r.get("kind") == "day_start"), None)
        self.changes = sorted((r for r in records if r.get("kind") == "state"), key=lambda r: r["capturedAt"])
        self.gaps = [r for r in records if r.get("kind") == "gap"]
        self.locks = {r["k"].split(".p.")[-1]: r for r in records if r.get("kind") == "lock" and r.get("k")}

    def at(self, when=None):
        """{pid: entry} as of `when` (None: the end of the log); None when the day has no history."""
        if not self.start or (when is not None and _at(self.start["capturedAt"]) > when):
            return None
        out = {e["p"]: e for e in self.start.get("players", [])}
        for c in self.changes:
            if when is not None and _at(c["capturedAt"]) > when:
                break
            if c.get("slot") is None:
                out.pop(c["p"], None)
            else:
                out[c["p"]] = c
        return out

    def cutoff(self, pid, notice):
        """The moment a status had to be known by for this player's game, or None when the log cannot say."""
        lock = self.locks.get(pid)
        if not self.start or not lock or lock.get("gs") != "live":
            return None
        tip = _at(lock["capturedAt"])
        cut = tip - datetime.timedelta(minutes=notice)
        if _at(self.start["capturedAt"]) > cut:
            return None
        for g in self.gaps:
            frm = _at(g["from"]) if g.get("from") else datetime.datetime.min
            to = _at(g["to"])
            if frm < cut < to or to == tip:
                return None
        return cut


class Review:
    def __init__(self, days, rules, ranks, il_map, positions, played):
        self.days = {d: Day(d, recs) for d, recs in sorted(days.items())}
        self.rules, self.ranks, self.il_map, self.positions, self.played = rules, ranks, il_map, positions, played
        self.items, self.cleared = [], []

    # ---- helpers -------------------------------------------------------
    def _out(self, st):
        return (st or "").upper() in self.rules["outStatuses"]

    def _healthy(self, st):
        return not st or st.upper() in self.rules["healthyStatuses"]

    def _star(self, pid):
        return self.ranks.get(pid) is not None and self.ranks[pid] <= lln.STAR_RANK

    def _pos(self, pid, row):
        pos = (row or {}).get("pos") or self.positions.get(pid) or []
        return [p.strip() for p in pos.replace("/", ",").split(",")] if isinstance(pos, str) else pos

    def _team_of(self, day, team):
        """Everyone the team had that day: the final history state, with each locked player's row as it stood at his lock."""
        final = day.at() or {}
        rows = {p: dict(e) for p, e in final.items() if e.get("team") == team}
        for pid, lock in day.locks.items():
            if lock.get("team") == team:
                rows[pid] = {"p": pid, "n": lock.get("n"), "team": team, "slot": lock.get("slot"), "st": lock.get("st"), "pos": lock.get("pos"), "locked": lock}
        return rows

    def _seen_before(self, date, pid):
        """The previous logged day, if it is yesterday-continuous: its end state (or lock) for this player."""
        prev = (_date(date) - datetime.timedelta(days=1)).isoformat()
        day = self.days.get(prev)
        if not day:
            return None
        return (day.at() or {}).get(pid) or day.locks.get(pid)

    def _out_since(self, date, pid):
        """The first day of the unbroken run of days, ending on `date`, on which Yahoo listed the player out."""
        start = date
        while True:
            row = self._seen_before(start, pid)
            if not row or not self._out(row.get("st")):
                return start
            start = (_date(start) - datetime.timedelta(days=1)).isoformat()

    def _returning(self, date, pid):
        """First game back: out the last day the log saw them before this one (yesterday, or their latest earlier game)."""
        row = self._seen_before(date, pid)
        if not row:
            earlier = [d for d in self.days if d < date and pid in self.days[d].locks]
            row = self.days[earlier[-1]].locks[pid] if earlier else None
        return bool(row) and self._out(row.get("st"))

    def _add(self, outcome, case, team, row, date, what, fact, at, unconfirmed=False):
        self.items.append({"o": WATCH if unconfirmed else outcome, "case": 19 if unconfirmed else case, "team": team, "p": row.get("p"),
                           "n": row.get("n"), "what": what, "fact": fact, "date": date, "at": at, "unconfirmed": unconfirmed})

    def _clear(self, case, team, date, name):
        self.cleared.append({"case": case, "team": team, "date": date, "n": name})

    # ---- one team on one day --------------------------------------------
    def team_day(self, date, team):
        day, rules = self.days[date], self.rules
        rows = self._team_of(day, team)
        slots = rules["slots"]
        judged = {}                                                  # pid -> (status that counts, confirmed?, read time)
        for pid, row in rows.items():
            lock = row.get("locked")
            cut = day.cutoff(pid, rules["noticeMinutes"]) if lock else None
            if lock and cut is not None:
                then = (day.at(cut) or {}).get(pid)
                if then is None or then.get("team") != team:          # picked up less than an hour before the tip
                    judged[pid] = (None, True, lock["capturedAt"], True)
                else:
                    judged[pid] = (then.get("st"), True, lock["capturedAt"], False)
            else:
                at = lock["capturedAt"] if lock else (day.changes[-1]["capturedAt"] if day.changes else day.start["capturedAt"] if day.start else None)
                judged[pid] = (row.get("st"), not lock, at, False)
        has_game = {pid for pid, row in rows.items() if row.get("locked")}
        status = {pid: j[0] for pid, j in judged.items()}

        starters = {pid: r for pid, r in rows.items() if r.get("slot") in slots}
        bench = {pid: r for pid, r in rows.items() if r.get("slot") == "BN"}
        # a start is wasted only when the player was out at the hour AND still out at the lock
        wasted = [pid for pid, r in starters.items() if pid in has_game and self._out(status[pid]) and self._out(r.get("st"))]
        for pid, r in starters.items():
            if pid in has_game and self._out(r.get("st")) and judged[pid][1] and not self._out(status[pid]):
                self._clear(2, team, date, r.get("n"))                                                        # listed out only after the hour
        filled = {r.get("slot") for r in starters.values()}
        empty = [s for s in slots if s not in filled] if day.start else []

        cover = [pid for pid, r in bench.items() if pid in has_game and self._healthy(status[pid]) and not judged[pid][3] and not self._returning(date, pid)]
        keep = [(pid, self._pos(pid, r)) for pid, r in starters.items() if pid not in wasted]
        fitted = _fill(keep + [(pid, self._pos(pid, bench[pid])) for pid in cover], slots)
        covering = [pid for pid in fitted if pid in cover]

        open_gaps = [(pid, starters[pid].get("slot")) for pid in wasted] + [(None, s) for s in empty]
        for b in covering:
            if not open_gaps:
                break
            fit = next((g for g in open_gaps if set(self._pos(b, bench[b])) & set(slots[g[1]])), open_gaps[0])
            open_gaps.remove(fit)
            pid, slot = fit
            sure = judged[b][1] and (pid is None or judged[pid][1])
            name = bench[b].get("n")
            if pid is None:
                self._add(FAULT, 7, team, {"p": slot, "n": slot + " slot"}, date, "left empty", name + " on bench", judged[b][2], not sure)
            else:
                self._add(FAULT, 3, team, starters[pid], date, "started while out", f"{slot}, {name} on bench", judged[pid][2], not sure)
        for pid, slot in open_gaps:
            if pid is None:
                self._clear(8, team, date, slot + " slot")

        # benched stars: fault only if they fit beside every other star who started with a game
        stars_in = [(pid, self._pos(pid, r)) for pid, r in starters.items() if pid in has_game and self._star(pid) and pid not in wasted]
        for pid, r in sorted(bench.items(), key=lambda x: self.ranks.get(x[0]) or 999):
            if pid not in has_game or not self._star(pid):
                continue
            if self._out(r.get("st")):
                continue                                                                                   # an out bench player is the IL check's business
            if not self._healthy(status[pid]) or judged[pid][3] or self._returning(date, pid):
                self._clear(11, team, date, r.get("n"))
                continue
            if pid in _fill(stars_in + [(pid, self._pos(pid, r))], slots):
                stars_in.append((pid, self._pos(pid, r)))
                self._add(FAULT, 9, team, r, date, "top-50 benched", "rank %s" % self.ranks[pid], judged[pid][2], not judged[pid][1])
            else:
                self._clear(10, team, date, r.get("n"))

        # out players outside the injured list while a slot there was open
        free = rules["ilSlots"] - sum(1 for r in rows.values() if r.get("slot") in IL_SLOTS)
        faulted = {i["p"] for i in self.items if i["date"] == date and i["team"] == team and i["case"] in (3, 19)}
        idle = []
        for pid, r in rows.items():
            if r.get("slot") in IL_SLOTS or pid in faulted or not self._out(status[pid]) or not self._out(r.get("st")):
                continue
            can_move = (status[pid] or "").upper() in rules["il"]["outStatuses"]                           # NA / SUSP cannot go to IL
            wasted_start = pid in wasted
            if not can_move or free <= 0 or not day.start:
                if wasted_start and judged[pid][1]:
                    self._clear(6, team, date, r.get("n"))
                elif wasted_start:
                    self._add(WATCH, 19, team, r, date, "started while out", r.get("slot"), judged[pid][2], True)
                continue
            idle.append((self._out_since(date, pid), pid, r))
        for since, pid, r in sorted(idle, key=lambda x: (x[0], x[1]))[:max(free, 0)]:
            days = (_date(date) - _date(since)).days
            where = r.get("slot") if r.get("slot") != "BN" else "bench"
            late = days > rules["ilMoveGraceDays"]
            outcome, case = (IL, 4 if pid in wasted else 12) if late else (WATCH, 5 if pid in wasted else 13)
            self._add(outcome, case, team, r, date, "out, IL slot free", f"{where}, out since {since}", judged[pid][2], not judged[pid][1])

    # ---- the injured list, in date order -------------------------------
    def injured_list(self, team_of_day):
        cleared_games = {}                                           # (team, pid) -> games played by the club since clearance, while still on IL
        for date, day in self.days.items():
            for team in team_of_day[date]:
                for pid, r in self._team_of(day, team).items():
                    key = (team, pid)
                    if r.get("slot") not in IL_SLOTS:
                        cleared_games.pop(key, None)
                        continue
                    lock = r.get("locked")
                    st = (r.get("st") or "").upper() or None
                    ie = (lock or {}).get("ie")
                    ie = self.il_map.get(pid) if ie is None else bool(ie)
                    played = date in self.played.get(pid, ())
                    state = ss.il_state(r["slot"], st, ie, self.rules["il"])
                    at = lock["capturedAt"] if lock else (day.changes[-1]["capturedAt"] if day.changes else day.start["capturedAt"] if day.start else None)
                    if st and (st in self.rules["outStatuses"]) and st not in self.rules["il"]["outStatuses"]:
                        self._add(WATCH, 18, team, r, date, "on IL, " + st, "Yahoo's IL setting does not list it", at)
                        continue
                    if state == "injured" and not (played and not st):
                        cleared_games.pop(key, None)
                        continue
                    if st in self.rules["uncertainStatuses"] and not played and key not in cleared_games:
                        self._add(WATCH, 15, team, r, date, "on IL, " + st, "not yet cleared", at)
                        continue
                    if state == "unverified" and not played and key not in cleared_games:
                        self._add(WATCH, 18, team, r, date, "on IL, eligibility unknown", st or "no status", at)
                        continue
                    seen = cleared_games.get(key, 0)
                    fact = ("status " + st if st else "no status") + (", played" if played else "")
                    if seen >= self.rules["ilActivateGraceGames"]:
                        self._add(FAULT, 17, team, r, date, "on IL, not eligible", fact, at)
                    else:
                        self._add(WATCH, 16, team, r, date, "on IL, first game since cleared" if lock else "on IL, cleared", fact, at)
                    if lock or played:
                        cleared_games[key] = seen + 1
                    else:
                        cleared_games.setdefault(key, seen)

    def run(self):
        team_of_day = {}
        for date, day in self.days.items():
            teams = {r.get("team") for r in day.locks.values()} | {e.get("team") for e in (day.at() or {}).values()}
            team_of_day[date] = sorted(t for t in teams if t)
            for team in team_of_day[date]:
                self.team_day(date, team)
        self.injured_list(team_of_day)
        return self.items, self.cleared


def merge(items):
    """One item per team, player, wording and outcome, with every date; the newest date's fact and read time."""
    out = {}
    for i in sorted(items, key=lambda x: x["date"]):
        key = (i["team"], i["p"], i["what"], i["o"], i["unconfirmed"])
        have = out.get(key)
        if have:
            have["dates"].append(i["date"])
            have.update(fact=i["fact"], at=i["at"], case=i["case"])
        else:
            out[key] = dict({k: v for k, v in i.items() if k != "date"}, dates=[i["date"]])
    return sorted(out.values(), key=lambda x: (x["team"], (FAULT, IL, WATCH).index(x["o"]), x["n"] or ""))


def unlogged(feed, logged, week_dates):
    """Closed days of the week the log never saw: the after-the-fact check, shown as unconfirmed."""
    checks = (feed.get("lineupChecks") or {})
    ids = {}
    for t in checks.get("teams", []):
        ids[str(t.get("yahooId"))] = t.get("team")
    out = []
    words = {"out_starter": "started while out", "empty_slot": "left empty", "star_benched": "top-50 benched"}
    for date, teams in (checks.get("byDate") or {}).items():
        if date in logged or date not in week_dates:
            continue
        for tid, issues in teams.items():
            for i in issues:
                if ids.get(tid):
                    name = i.get("p") or (i.get("s", "") + " slot")
                    out.append({"o": WATCH, "case": 19, "team": ids[tid], "p": i.get("id") or name, "n": name, "what": words.get(i["k"], i["k"]),
                                "fact": (i.get("r") + " on bench") if i.get("r") else (i.get("s") or ""), "date": date, "at": None, "unconfirmed": True})
    return out


def build(feed, days, season_start, rules, ranks, il_map, positions, played):
    """The "lineupReview" block for the feed."""
    week = feed.get("week")
    first = _date(season_start) + datetime.timedelta(days=7 * (week - 1))
    week_dates = {(first + datetime.timedelta(days=i)).isoformat() for i in range(7)}
    items, cleared = Review(days, rules, ranks, il_map, positions, played).run()
    items += unlogged(feed, set(days), week_dates)
    teams = {}
    for m in feed.get("matchups", []):
        pair = [t.get("team") for t in m.get("teams", [])]
        for i, team in enumerate(pair):
            teams[team] = {"opponent": pair[1 - i] if len(pair) == 2 else None}
    for team in {i["team"] for i in items} | {c["team"] for c in cleared}:
        teams.setdefault(team, {})
    for team, out in teams.items():
        mine = [i for i in items if i["team"] == team]
        faults = [i for i in mine if i["o"] == FAULT and i["date"] in week_dates]
        n_days, players = len({i["date"] for i in faults}), len({i["p"] for i in faults})
        stars = len({i["p"] for i in faults if ranks.get(i["p"]) is not None and ranks[i["p"]] <= lln.STAR_RANK})
        out.update(items=merge(mine), days=n_days, players=players, stars=stars,
                   meets=n_days >= lln.RULE["days"] or players >= lln.RULE["players"] or stars >= lln.RULE["stars"])
    return {"week": week, "rule": lln.RULE, "since": min(days) if days else None, "cleared": len(cleared), "teams": teams}


def read_logs(log_dir, keep=14):
    out = {}
    names = sorted(n for n in os.listdir(log_dir) if n.endswith(".jsonl"))[-keep:] if os.path.isdir(log_dir) else []
    for n in names:
        with open(os.path.join(log_dir, n), encoding="utf-8") as f:
            out[n[:-6]] = [json.loads(line) for line in f if line.strip()]
    return out


def registry_maps(registry):
    il, pos = {}, {}
    for p in (registry or {}).get("players", []):
        pid, elig = str(p.get("playerId")), p.get("eligiblePositions") or []
        if elig:
            il[pid] = "IL" in elig
            pos[pid] = [e for e in elig if e in ("PG", "SG", "SF", "PF", "C")]
    return il, pos


def played_dates(player_log):
    return {pid: {row[0] for row in rows} for pid, rows in ((player_log or {}).get("p") or {}).items()}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--feed", required=True, help="live.json; the review is written into it")
    ap.add_argument("--player-log", help="player_log.json: who actually played (an IL player who played is cleared)")
    ap.add_argument("--registry", default=os.path.join(HERE, "..", "data", "yahoo", "player_registry.json"))
    ap.add_argument("--season-start", help="the season's first Monday (default: the matchups config)")
    a = ap.parse_args(argv)
    feed = _read(a.feed)
    start = a.season_start
    if not start:
        import yahoo_matchups as ym
        start = ym.load_config()["seasonStartMonday"]
    try:
        log = _read(a.player_log) if a.player_log else None
    except (OSError, ValueError):
        log = None
    il_map, positions = registry_maps(_read(a.registry))
    feed["lineupReview"] = build(feed, read_logs(a.log_dir), start, load_rules(), lln.load_ranks(a.registry), il_map, positions, played_dates(log))
    tmp = a.feed + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, a.feed)
    teams = feed["lineupReview"]["teams"].values()
    print("lineup review: %d fault item(s), %d cleared" % (sum(1 for t in teams for i in t["items"] if i["o"] == FAULT), feed["lineupReview"]["cleared"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
