#!/usr/bin/env python3
"""Read-only Yahoo roster acquisition -> staged observation -> reviewed import (scripts/import_rosters.py).

    python3 scripts/yahoo_rosters.py fetch                    # all 16 teams: fetch, validate, save, report differences
    python3 scripts/yahoo_rosters.py fetch --team 8           # one team (a partial observation; never importable)
    python3 scripts/yahoo_rosters.py fetch --engine browser   # through the logged-in Playwright profile
    python3 scripts/yahoo_rosters.py login                    # one-time interactive Yahoo login (browser profile)
    python3 scripts/yahoo_rosters.py import-json FILE         # JSON captured by the Chrome DevTools script
    python3 scripts/yahoo_rosters.py validate OBS.json
    python3 scripts/yahoo_rosters.py diff OBS.json            # vs the current season state and the previous observation
    python3 scripts/yahoo_rosters.py standings [--write]      # league standings (read-only); --write records them for the site

Nothing here writes canonical league data. An observation is evidence: it is saved under local_data/ (gitignored)
and becomes official only through the existing reviewed import, which it feeds unchanged:

    python3 scripts/import_rosters.py diff   OBS.json --verified-at <capturedAt> --source "<observation source>"
    python3 scripts/import_rosters.py commit OBS.json --verified-at ... --source ... --reviewed

Every request is a GET of https://basketball.fantasysports.yahoo.com/nba/<league>/<team>. The default `http` engine
sends no cookies (the league's team pages are publicly viewable); `browser` uses an isolated Playwright profile
outside the repository. A login page, consent wall or wrong team fails the fetch: authentication is never worked
around. Payroll stays the existing top-9 frozen-salary rule (league_state.counted_cap), IL included.
Standard library only, except the optional `browser` engine (Playwright).
"""
from __future__ import annotations

import argparse
import datetime
import glob
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_rosters as ir  # noqa: E402
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "yahoo_league.json")
OBS_DIR = os.path.join(ROOT, "local_data", "yahoo_observations")  # gitignored
PROFILE_DIR = os.environ.get("NBA_TALK_YAHOO_PROFILE",
                             os.path.join(os.path.expanduser("~"), ".config", "nba-talk-vn-dynasty", "yahoo-browser-profile"))
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0 Safari/537.36")
SCHEMA = 1


class FetchError(RuntimeError):
    """A page that is not a readable roster: code is AUTH_REQUIRED, CONSENT_REQUIRED, WRONG_TEAM, NO_ROSTER_TABLE,
    HTTP_<status> or NETWORK."""

    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def load_config(path=CONFIG_PATH) -> dict:
    cfg = ss._load(path)
    cfg["teamIds"] = [int(t) for t in cfg["teamIds"]]
    return cfg


def team_key(cfg, team_id) -> str:
    return f"{cfg['gameKey']}.l.{cfg['leagueId']}.t.{int(team_id)}"


def check_game_key(si, cfg) -> None:
    """The game prefix comes from repository data, not an assumption: every frozen Yahoo key must carry it."""
    prefixes = {k.split(".p.")[0] for k in si["salaries"] if ".p." in k}
    if prefixes != {cfg["gameKey"]} or ir.GAME_KEY != cfg["gameKey"]:
        raise ValueError(f"game key mismatch: config {cfg['gameKey']}, importer {ir.GAME_KEY}, frozen salaries {sorted(prefixes)}")


# ------------------------------------------------------------------ parsing
class _RosterTable(HTMLParser):
    """Rows of table#statTable0 on a Yahoo team page. Empty lineup slots (no player link) are skipped."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # table nesting inside statTable0
        self.found = False
        self.rows, self.row = [], None
        self.capture = None     # which text is being collected
        self.title, self.in_title, self.canonical = "", False, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "title":
            self.in_title = True
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        if tag == "table":
            if self.depth:
                self.depth += 1
            elif a.get("id") == "statTable0":
                self.depth, self.found = 1, True
            return
        if not self.depth:
            return
        if tag == "tr":
            self.row = {"slot": None, "playerId": None, "name": "", "injury": None, "injuryTitle": None,
                        "meta": "", "keeperSalary": None}
        elif self.row is None:
            return
        elif tag == "span" and "pos-label" in cls:
            self.row["slot"] = a.get("data-pos")
            self.capture = "slot" if not a.get("data-pos") else None
        elif tag == "a" and "name" in cls and self.row["playerId"] is None:
            m = re.search(r"/nba/players/(\d+)", a.get("href") or "")
            if m:
                self.row["playerId"] = m.group(1)
                self.capture = "name"
        elif tag == "span" and "F-injury" in cls:
            self.capture = "injury"
            self.row["injury"] = ""
        elif tag == "span" and self.capture == "injury" and a.get("title"):
            self.row["injuryTitle"] = a.get("title")
        elif tag == "span" and "Fz-xxs" in cls and not self.row["meta"] and self.capture is None:
            self.capture = "meta"
        elif tag == "span" and (a.get("title") or "").startswith("Keeper Salary"):
            m = re.search(r"(\d+(?:\.\d+)?)", a["title"])
            self.row["keeperSalary"] = float(m.group(1)) if m else None

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if not self.depth:
            return
        if tag == "table":
            self.depth -= 1
        elif tag == "tr" and self.row is not None:
            if self.row["playerId"]:
                self.rows.append(self.row)
            self.row, self.capture = None, None
        elif tag in ("a", "span"):
            if self.capture in ("name", "injury", "meta", "slot"):
                self.capture = None

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.row is None or not self.capture:
            return
        if self.capture == "slot":
            self.row["slot"] = (self.row["slot"] or "") + data.strip()
        else:
            self.row[self.capture] = (self.row[self.capture] or "") + data


def classify_unreadable(html: str, url: str = "") -> FetchError:
    low = html.lower()
    if "login.yahoo.com" in (url or "") or re.search(r'id="login-username"|name="username"|id="login-signin"', html):
        return FetchError("AUTH_REQUIRED", "Yahoo returned a sign-in page; run `yahoo_rosters.py login` (browser engine)")
    if "guce.yahoo.com" in (url or "") or ("consent" in low and "collectconsent" in low):
        return FetchError("CONSENT_REQUIRED", "Yahoo returned a consent page; open the league once in the browser profile")
    return FetchError("NO_ROSTER_TABLE", "no table#statTable0 on the page (layout changed or not a team page)")


def parse_team_page(html: str, team_id=None, league_id=None, url: str = "") -> dict:
    """-> {teamId, teamName, players:[{playerId, name, slot, injury?, nbaTeam?, positions?, keeperSalary?}]}"""
    p = _RosterTable()
    p.feed(html)
    if not p.found:
        raise classify_unreadable(html, url)
    m = re.search(r"/nba/(\d+)/(\d+)/?$", (p.canonical or "").split("?")[0])
    if team_id is not None and m and (int(m.group(2)) != int(team_id) or (league_id and m.group(1) != str(league_id))):
        raise FetchError("WRONG_TEAM", f"asked for team {team_id}, page is {m.group(1)}/{m.group(2)}")
    title = htmllib.unescape(p.title).strip()
    name = re.sub(r"\s*\|\s*Fantasy Basketball.*$", "", title)
    name = re.sub(r"^.*? - Dynasty - ", "", name) if " - Dynasty - " in name else name
    players = []
    for r in p.rows:
        meta = " ".join(r["meta"].split())
        nba, _, pos = meta.partition(" - ")
        q = {"playerId": r["playerId"], "name": " ".join(r["name"].split()), "slot": r["slot"]}
        if r["injury"]:
            q["injury"] = r["injury"].strip()
            if r["injuryTitle"]:
                q["injuryTitle"] = r["injuryTitle"]
        if pos:
            q["nbaTeam"], q["positions"] = nba.strip(), pos.strip()
        if r["keeperSalary"] is not None:
            q["keeperSalary"] = r["keeperSalary"]
        players.append(q)
    tid = int(team_id) if team_id is not None else (int(m.group(2)) if m else None)
    return {"teamId": tid, "teamName": name, "players": players}


# -------------------------------------------------------------- standings
STANDINGS_PATH = os.path.join(ss.DATA_DIR, "standings.json")


def _cell_text(html_fragment: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", html_fragment)).split())


def parse_standings(html: str, league_id) -> list:
    """table#standingstable on the league home page -> [{teamId, teamName, division, rank, w, l, t, pct, divRecord,
    gb, lastWeek, waiver, moves}]. Division header rows (East / West) set the division of the rows below them."""
    i = html.find('id="standingstable"')
    if i < 0:
        raise classify_unreadable(html)
    table = html[i:html.index("</table>", i)]
    rows, division = [], None
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", table, re.S):
        h4 = re.search(r"<h4[^>]*>(.*?)</h4>", tr, re.S)
        if h4:
            division = _cell_text(h4.group(1))
            continue
        m = re.search(r'data-target="/nba/(\d+)/(\d+)"', tr)
        if not m:
            continue
        if str(m.group(1)) != str(league_id):
            raise FetchError("WRONG_TEAM", f"standings row for league {m.group(1)}")
        cells = [_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) < 9:
            raise FetchError("NO_ROSTER_TABLE", f"standings row for team {m.group(2)} has {len(cells)} cells")
        w, l, t = (int(x) for x in re.fullmatch(r"(\d+)-(\d+)-(\d+)", cells[2]).groups())
        num = lambda s: int(s) if re.fullmatch(r"\d+", s or "") else None  # noqa: E731
        rows.append({"teamId": int(m.group(2)), "teamName": cells[1], "division": division, "rank": num(cells[0]),
                     "w": w, "l": l, "t": t, "pct": float(cells[3]) if re.fullmatch(r"[\d.]+", cells[3]) else None,
                     "divRecord": cells[4], "gb": cells[5], "lastWeek": cells[6], "waiver": num(cells[7]), "moves": num(cells[8])})
    return rows


def validate_standings(rows, cfg) -> list:
    problems = []
    ids = [r["teamId"] for r in rows]
    if sorted(ids) != sorted(cfg["teamIds"]):
        problems.append(f"teams {sorted(ids)} are not the league's {cfg['teamIds']}")
    if len(ids) != len(set(ids)):
        problems.append("a team appears twice")
    ranks = [r["rank"] for r in rows if r["rank"] is not None]
    if len(ranks) != len(set(ranks)):
        problems.append("duplicate ranks")
    return problems


def standings_doc(cfg, rows, captured_at, data_dir=ss.DATA_DIR) -> dict:
    """The site's standings record: Yahoo's table as observed, mapped to franchises (display data, never governance)."""
    team_map, _ = ir.load_maps(data_dir)
    out = []
    for r in sorted(rows, key=lambda r: r["teamId"]):
        fid = franchise_for(cfg, team_map, r["teamId"])
        if fid is None:
            raise FetchError("UNMAPPED_TEAM", f"Yahoo team {r['teamId']} has no yahooTeamKey in rosters/team_map.json")
        out.append({"franchiseId": fid, **{k: v for k, v in r.items() if k != "teamName"}})
    started = any(r["w"] + r["l"] + r["t"] for r in rows) or any(r["rank"] for r in rows)
    return {"season": "2026-27", "capturedAt": ss.ts(captured_at), "started": started,
            "source": f"Yahoo Fantasy league {cfg['leagueId']} standings table (league home page), read-only GET",
            "note": "Head-to-head category record (W-L-T) as Yahoo shows it. Display only: it orders the team cards once the season starts.",
            "teams": out}


# ----------------------------------------------------------- observations
def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_observation(cfg, teams, captured_at, method, errors=(), requested=None) -> dict:
    """Staged evidence in the importer's JSON input shape (teams[].teamKey / players[].playerKey,name,slot)."""
    out = []
    for t in sorted(teams, key=lambda t: int(t["teamId"])):
        ps = []
        for p in t["players"]:
            pid = str(p.get("playerId") or "").strip()
            q = {"playerId": pid, "playerKey": f"{cfg['gameKey']}.p.{pid}" if pid.isdigit() else None,
                 "name": p.get("name"), "slot": p.get("slot")}
            q.update({k: p[k] for k in ("injury", "injuryTitle", "nbaTeam", "positions", "keeperSalary") if p.get(k) is not None})
            ps.append(q)
        out.append({"teamId": int(t["teamId"]), "teamKey": team_key(cfg, t["teamId"]), "teamName": t.get("teamName"), "players": ps})
    requested = sorted(int(x) for x in (requested or [t["teamId"] for t in teams]))
    full = requested == sorted(cfg["teamIds"])
    obs = {"kind": "YAHOO_ROSTER_OBSERVATION", "schema": SCHEMA, "leagueId": str(cfg["leagueId"]), "gameKey": cfg["gameKey"],
           "capturedAt": ss.ts(captured_at), "method": method, "scope": "FULL" if full else "PARTIAL",
           "requestedTeamIds": requested, "teams": out, "errors": list(errors)}
    obs["source"] = (f"Yahoo Fantasy league {cfg['leagueId']} team pages, read-only {method} capture at {obs['capturedAt']}")
    obs["digest"] = ls._digest({t["teamId"]: sorted((p["playerId"], p.get("slot")) for p in t["players"]) for t in out})
    return obs


def normalize_manual(doc, cfg) -> dict:
    """Accept the DevTools capture in its usual shapes: {teams:[...]}, [{teamId, players}], {"<teamId>": [...]} or
    a flat list of players carrying teamId. Player fields: playerId|id|player_id, name, slot|position|pos."""
    captured = None
    if isinstance(doc, dict):
        captured = doc.get("capturedAt") or doc.get("extractedAt") or doc.get("timestamp")
        if doc.get("leagueId") and str(doc["leagueId"]) != str(cfg["leagueId"]):
            raise ValueError(f"capture is for league {doc['leagueId']}, not {cfg['leagueId']}")
        body = doc.get("teams") if "teams" in doc else doc.get("rosters", {k: v for k, v in doc.items() if str(k).isdigit()})
    else:
        body = doc
    teams = {}

    def add(tid, name, players):
        t = teams.setdefault(int(tid), {"teamId": int(tid), "teamName": name, "players": []})
        t["teamName"] = t["teamName"] or name
        for p in players:
            t["players"].append({"playerId": str(p.get("playerId") or p.get("id") or p.get("player_id") or "").strip(),
                                 "name": p.get("name") or p.get("playerName"),
                                 "slot": p.get("slot") or p.get("position") or p.get("pos") or p.get("selectedPosition"),
                                 **{k: p[k] for k in ("injury", "nbaTeam", "positions", "keeperSalary") if p.get(k) is not None}})

    if isinstance(body, dict):
        for tid, v in body.items():
            add(tid, v.get("teamName") if isinstance(v, dict) else None, v.get("players", []) if isinstance(v, dict) else v)
    else:
        for t in body:
            if "players" in t or "roster" in t:
                add(t.get("teamId") or t.get("id") or t.get("team_id"), t.get("teamName") or t.get("name"), t.get("players") or t.get("roster"))
            else:
                add(t.get("teamId") or t.get("team_id"), t.get("teamName"), [t])
    return {"teams": list(teams.values()), "capturedAt": captured}


def validate_observation(obs, cfg, require_full=True) -> dict:
    """-> {"blocking": [...], "warnings": [...]}. Roster size is NOT fixed in-season, so it is never checked."""
    blocking, warnings = [], []
    valid = set(cfg["teamIds"])
    seen_team, seen_player = set(), {}
    for e in obs.get("errors", []):
        blocking.append({"code": "FETCH_" + e.get("code", "ERROR"), "detail": f"team {e.get('teamId')}: {e.get('detail')}"})
    for t in obs["teams"]:
        tid = t["teamId"]
        if tid not in valid:
            blocking.append({"code": "INVALID_TEAM_ID", "detail": f"team {tid} is not a team of league {cfg['leagueId']}"})
        if tid in seen_team:
            blocking.append({"code": "DUPLICATE_TEAM", "detail": f"team {tid} appears twice"})
        seen_team.add(tid)
        if not t["players"]:
            blocking.append({"code": "EMPTY_ROSTER", "detail": f"team {tid} has no players (a parse or auth failure, never a real roster)"})
        for p in t["players"]:
            if not re.fullmatch(r"\d+", p.get("playerId") or ""):
                blocking.append({"code": "BAD_PLAYER_ID", "detail": f"team {tid}: {p.get('name')!r} has id {p.get('playerId')!r}"})
                continue
            if not (p.get("name") or "").strip():
                blocking.append({"code": "MISSING_NAME", "detail": f"team {tid}: player {p['playerId']}"})
            s = ir.norm_slot(p.get("slot"))
            if s is None:
                warnings.append({"code": "NO_SLOT", "detail": f"team {tid}: {p.get('name')}"})
            elif s.startswith("!"):
                blocking.append({"code": "UNKNOWN_SLOT", "detail": f"team {tid}: {p.get('name')} slot {s[1:]!r}"})
            if p["playerId"] in seen_player:
                blocking.append({"code": "DUPLICATE_OWNERSHIP",
                                 "detail": f"{p.get('name')} ({p['playerId']}) on teams {seen_player[p['playerId']]} and {tid}"})
            seen_player[p["playerId"]] = tid
    if require_full:
        missing = sorted(valid - seen_team)
        if missing or obs.get("scope") != "FULL":
            blocking.append({"code": "INCOMPLETE_CAPTURE", "detail": f"missing teams {missing or '(partial scope)'}: a full capture needs all {len(valid)}"})
    return {"blocking": blocking, "warnings": warnings}


def save_observation(obs, out_dir=None) -> str:
    out_dir = out_dir or OBS_DIR
    os.makedirs(out_dir, exist_ok=True)
    stamp = obs["capturedAt"].replace(":", "").replace("-", "")
    path = os.path.join(out_dir, f"OBS-{stamp}-{obs['scope'].lower()}-{obs['digest'][:8]}.json")
    ss._write(path, obs)
    return path


def previous_observation(out_dir=None, before=None):
    """The latest saved FULL observation without errors (captured before `before`, if given)."""
    best = None
    for path in glob.glob(os.path.join(out_dir or OBS_DIR, "OBS-*.json")):
        try:
            o = ss._load(path)
        except (OSError, ValueError):
            continue
        if o.get("scope") != "FULL" or o.get("errors") or (before and o["capturedAt"] >= before):
            continue
        if best is None or o["capturedAt"] > best[1]["capturedAt"]:
            best = (path, o)
    return best


# --------------------------------------------------------------- reconciling
def franchise_for(cfg, team_map, tid):
    key = team_key(cfg, tid)
    return next((f for f, t in team_map["teams"].items() if t.get("yahooTeamKey") == key), None)


def observation_diff(old, new) -> dict:
    """Yahoo vs Yahoo, by Yahoo id: what moved between two captures (no interpretation)."""
    def index(o):
        return {p["playerId"]: (t["teamId"], p.get("slot"), p.get("name")) for t in o["teams"] for p in t["players"]}
    a, b = index(old), index(new)
    out = {"added": [], "removed": [], "changedTeam": [], "slotChanged": []}
    for pid, (tid, slot, name) in sorted(b.items(), key=lambda x: (x[1][0], x[1][2] or "")):
        if pid not in a:
            out["added"].append({"player": name, "playerId": pid, "teamId": tid, "slot": slot})
        elif a[pid][0] != tid:
            out["changedTeam"].append({"player": name, "playerId": pid, "fromTeamId": a[pid][0], "toTeamId": tid})
        elif a[pid][1] != slot:
            out["slotChanged"].append({"player": name, "playerId": pid, "teamId": tid, "from": a[pid][1], "to": slot})
    for pid, (tid, slot, name) in sorted(a.items(), key=lambda x: (x[1][0], x[1][2] or "")):
        if pid not in b:
            out["removed"].append({"player": name, "playerId": pid, "teamId": tid})
    return out


def reconcile(si, obs, data_dir=ss.DATA_DIR) -> dict:
    """Observation vs the CURRENT season state (verified snapshot + completed in-season trades). Runs the existing
    importer (build_snapshot + diff) in memory and writes nothing. Differences are observations, not transactions."""
    team_map, _ = ir.load_maps(data_dir)
    cfg = {"gameKey": obs["gameKey"], "leagueId": obs["leagueId"]}
    rows, unmapped = [], []
    for t in obs["teams"]:
        fid = franchise_for(cfg, team_map, t["teamId"])
        if fid is None:
            unmapped.append(t["teamId"])
        for p in t["players"]:
            rows.append({"team": fid or t.get("teamName") or str(t["teamId"]), "playerKey": p.get("playerKey"),
                         "playerId": p.get("playerId"), "name": p.get("name"), "slot": p.get("slot"), "status": p.get("injury"),
                         "nbaTeam": p.get("nbaTeam"), "positions": p.get("positions")})
    snap, report = ir.build_snapshot(si, rows, obs["capturedAt"], obs["source"], data_dir)
    hard = {"UNMATCHED_TEAM", "DUPLICATE_OWNERSHIP"}
    d = ir.diff(si, snap) if not any(b["code"] in hard for b in report["blocking"]) else None
    out = {"snapshot": snap, "report": report, "diff": d, "unmappedTeams": unmapped, "notes": [], "payroll": [],
           "salaryEvidence": []}
    if d is None:
        return out
    cur = ss.season_state(si)
    # differences that line up with a recorded but not-completed transaction are labelled, never applied
    open_moves = {}
    for t in si["seasonTxns"]:
        if t["status"] != "COMPLETED":
            for a in t["assets"]:
                if a["type"] == "player":
                    open_moves[(a["playerKey"], a["to"])] = (t["txnId"], t["status"])
    rev = {v: k for k, v in si["shorts"].items()}
    for x in d["changedTeam"]:
        hit = open_moves.get((x["key"], rev.get(x["to"])))
        x["note"] = (f"matches {hit[0]} ({hit[1]}), which is not recorded as completed" if hit
                     else "not explained by any recorded transaction")
    for x in d["added"]:
        x["note"] = "on Yahoo, not on our roster"
    for x in d["dropped"]:
        x["note"] = ("provisional identity: Yahoo may list this player under its own id (see PROVISIONAL_LINK_CANDIDATE)"
                     if x["key"] in si["extraPlayers"] else "on our roster, not on Yahoo")
    # payroll preview: the existing top-9 rule over frozen salaries, IL included; unlisted players at the league-rule 0
    new_owner = ss.snapshot_owner(snap)
    si_new = ir.with_unlisted(si, report)
    for fid in si["franchises"]:
        before = ls.team_cap(si, cur, fid)
        keys = [k for k, f in new_owner.items() if f == fid]
        out["payroll"].append({"team": si["shorts"][fid], "count": len(keys), "capNow": before,
                               "capIfImported": ls.counted_cap(si_new, keys),
                               "il": sum(1 for r in snap["teams"][fid] if r.get("slot") in ss.SLOTS_IL)})
    if report.get("unlisted"):
        out["notes"].append(f"{len(report['unlisted'])} player(s) are not in the frozen 2026-27 salary table: salary 0 by league "
                            "rule, recorded in unlisted_players.json only when the import is committed")
    for t in obs["teams"]:
        for p in t["players"]:
            k = p.get("playerKey")
            if k in si["salaries"] and p.get("keeperSalary") is not None and float(p["keeperSalary"]) != float(si["salaries"][k]):
                out["salaryEvidence"].append({"player": p["name"], "frozen": si["salaries"][k], "yahooKeeperSalary": p["keeperSalary"]})
    return out


def render_report(obs, check, rec, prev_diff=None, prev_path=None) -> str:
    L = [f"observation {obs['capturedAt']} · {obs['method']} · scope {obs['scope']} · "
         f"{len(obs['teams'])} teams · {sum(len(t['players']) for t in obs['teams'])} players"]
    for b in check["blocking"]:
        L.append(f"  BLOCKING {b['code']}: {b['detail']}")
    for w in check["warnings"]:
        L.append(f"  WARNING  {w['code']}: {w['detail']}")
    if rec:
        if rec["unmappedTeams"]:
            L.append(f"  WARNING  UNMAPPED_TEAMS: Yahoo teams {rec['unmappedTeams']} have no yahooTeamKey in rosters/team_map.json")
        for b in rec["report"]["blocking"]:
            L.append(f"  IMPORT-BLOCKING {b['code']}: {b.get('team', '')} {b.get('detail')}")
        for w in rec["report"]["warnings"]:
            L.append(f"  IMPORT-WARNING  {w['code']}: {w.get('team', '')} {w.get('detail')}")
        d = rec["diff"]
        if d:
            L.append("vs current season state (observed differences; none is applied):")
            for k, title in (("added", "ON YAHOO ONLY"), ("dropped", "OURS ONLY"), ("changedTeam", "OTHER TEAM"),
                             ("ilMoves", "IL MOVE"), ("lineupOnly", "LINEUP ONLY")):
                for x in d[k]:
                    if k == "changedTeam":
                        L.append(f"  {title:13} {x['player']}: ours {x['from']}, Yahoo {x['to']} — {x['note']}")
                    elif k in ("added", "dropped"):
                        L.append(f"  {title:13} {x['player']} ({x['team']}) — {x['note']}")
                    else:
                        L.append(f"  {title:13} {x['player']} ({x['team']}) {x['from']} → {x['to']}")
            for t in d["transactions"]:
                L.append(f"  RECORDED     {t['txnId']} {t.get('label') or ''}: {'reflected on Yahoo' if t['reflected'] else 'NOT reflected on Yahoo'}")
            L.append(f"  unchanged: {d['unchanged']}")
        if rec["payroll"]:
            L.append("payroll preview (top 9 frozen salaries, IL included; unlisted players at 0 by league rule):")
            for p in rec["payroll"]:
                delta = p["capIfImported"] - p["capNow"]
                L.append(f"  {p['team']:9} {p['count']:2} players ({p['il']} IL)  {p['capNow']:g} → {p['capIfImported']:g}"
                         + (f"  ({delta:+g})" if delta else ""))
        if rec["salaryEvidence"]:
            for x in rec["salaryEvidence"]:
                L.append(f"  note: Yahoo keeper-salary label for {x['player']} is {x['yahooKeeperSalary']:g}, frozen salary "
                         f"{x['frozen']:g} (frozen wins; nothing changed)")
        for n in rec["notes"]:
            L.append(f"  note: {n}")
    if prev_diff is not None:
        L.append(f"vs previous observation {os.path.basename(prev_path)}:")
        n = 0
        for k in ("added", "removed", "changedTeam", "slotChanged"):
            for x in prev_diff[k]:
                n += 1
                L.append(f"  {k:11} {json.dumps(x, ensure_ascii=False)}")
        if not n:
            L.append("  no change")
    return "\n".join(L)


# ------------------------------------------------------------------ fetching
def page_url(cfg, team_id) -> str:
    return cfg["pageUrl"].format(leagueId=cfg["leagueId"], teamId=int(team_id))


class HttpFetcher:
    """Plain GET without cookies or credentials."""
    method = "http"

    def __init__(self, timeout=30):
        self.timeout = timeout

    def get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, url, ""
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise FetchError("NETWORK", str(e))

    def close(self):
        pass


class BrowserFetcher:
    """GET through a persistent Playwright profile (cookies from `login`). Uses the context's request API: no page
    scripts run and nothing is clicked or submitted."""
    method = "browser"

    def __init__(self, profile=PROFILE_DIR, headless=True):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise FetchError("NO_PLAYWRIGHT", "pip install playwright && python3 -m playwright install chromium")
        if not os.path.isdir(profile):
            raise FetchError("AUTH_REQUIRED", f"no browser profile at {profile}; run `yahoo_rosters.py login` first")
        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(profile, headless=headless, user_agent=USER_AGENT)

    def get(self, url):
        r = self.ctx.request.get(url, timeout=30000)
        return r.status, r.url, r.text()

    def close(self):
        self.ctx.close()
        self._pw.stop()


RETRYABLE = ("NETWORK", "HTTP_429", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504")


def fetch_teams(cfg, team_ids, fetcher, delay=None, sleep=time.sleep, attempts=2):
    """-> (teams, errors). Every requested team is attempted; one failure never hides the others. A timeout or a
    server error is retried once after a pause; a sign-in page, consent wall or wrong team is not retried."""
    teams, errors = [], []
    delay = cfg.get("requestDelaySeconds", 1.5) if delay is None else delay
    for i, tid in enumerate(team_ids):
        if i:
            sleep(delay)
        url = page_url(cfg, tid)
        for attempt in range(1, attempts + 1):
            try:
                status, final_url, body = fetcher.get(url)
                if status != 200:
                    raise FetchError(f"HTTP_{status}", url)
                teams.append(parse_team_page(body, tid, cfg["leagueId"], final_url))
                break
            except FetchError as e:
                if e.code in RETRYABLE and attempt < attempts:
                    sleep(delay * 3)
                    continue
                errors.append({"teamId": tid, "code": e.code, "detail": e.detail, "attempts": attempt})
                break
    return teams, errors


def login(cfg, profile=PROFILE_DIR):
    """Open a visible browser on an isolated profile; the user signs in to Yahoo by hand, then closes the window."""
    from playwright.sync_api import sync_playwright
    os.makedirs(profile, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(profile, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(page_url(cfg, cfg["teamIds"][0]))
        print(f"Sign in to Yahoo in the opened window, then close it. Profile: {profile}")
        page.wait_for_event("close", timeout=0)
        ctx.close()


# ----------------------------------------------------------------------- cli
def _analyse(obs, cfg, require_full, out_dir=None):
    si = ss.load_season(ls.load_inputs())
    check_game_key(si, cfg)
    check = validate_observation(obs, cfg, require_full)
    rec = reconcile(si, obs) if not any(b["code"] in ("DUPLICATE_OWNERSHIP", "INVALID_TEAM_ID") for b in check["blocking"]) else None
    prev = previous_observation(out_dir, before=obs["capturedAt"])
    pd = observation_diff(prev[1], obs) if prev else None
    return check, rec, render_report(obs, check, rec, pd, prev[0] if prev else None)


def _finish(obs, cfg, save, require_full, out_dir=None):
    check, rec, text = _analyse(obs, cfg, require_full, out_dir)
    if save and not obs["errors"] and obs["teams"]:  # only a successful acquisition is kept
        text += f"\nsaved observation: {os.path.relpath(save_observation(obs, out_dir), ROOT)}"
    importable = obs["scope"] == "FULL" and not check["blocking"] and rec and not rec["report"]["blocking"]
    text += ("\nnext (review first): python3 scripts/import_rosters.py diff <observation> --verified-at "
             f"{obs['capturedAt']} --source \"{obs['source']}\"" if importable else
             "\nnot importable as-is: resolve the BLOCKING / IMPORT-BLOCKING items (official data was not changed)")
    print(text)
    return 0 if not check["blocking"] else 1


def main(argv=None, fetcher=None, out_dir=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch")
    p.add_argument("--team", type=int, action="append", help="one team id (repeatable); default all")
    p.add_argument("--engine", choices=("http", "browser"), default="http")
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--headed", action="store_true")
    sub.add_parser("login")
    p = sub.add_parser("standings")
    p.add_argument("--write", action="store_true", help="record them in data/2026-27/standings.json for the site")
    p = sub.add_parser("import-json")
    p.add_argument("file")
    p.add_argument("--captured-at", help="when the capture was taken, if the file does not say")
    p.add_argument("--no-save", action="store_true")
    for name in ("validate", "diff"):
        p = sub.add_parser(name)
        p.add_argument("file")
    args = ap.parse_args(argv)
    cfg = load_config()
    if args.cmd == "login":
        login(cfg)
        return 0
    if args.cmd == "fetch":
        ids = args.team or cfg["teamIds"]
        bad = [t for t in ids if t not in cfg["teamIds"]]
        if bad:
            print(f"BLOCKED: team id(s) {bad} are not in league {cfg['leagueId']} (valid: {cfg['teamIds']})")
            return 2
        injected = fetcher is not None  # tests pass a fake fetcher: no network, no politeness delay
        try:
            fetcher = fetcher or (HttpFetcher() if args.engine == "http" else BrowserFetcher(headless=not args.headed))
        except FetchError as e:
            print("BLOCKED:", e)
            return 2
        try:
            started = now_utc()
            teams, errors = fetch_teams(cfg, ids, fetcher, delay=0 if injected else None)
        finally:
            fetcher.close()
        obs = make_observation(cfg, teams, started, args.engine, errors, requested=ids)
        return _finish(obs, cfg, not args.no_save, require_full=not args.team, out_dir=out_dir)
    if args.cmd == "standings":
        f = fetcher or HttpFetcher()
        started = now_utc()
        url = cfg["leagueUrl"].format(leagueId=cfg["leagueId"])
        status, final_url, body = f.get(url)
        if status != 200:
            print(f"BLOCKED: HTTP_{status} {url}")
            return 2
        try:
            rows = parse_standings(body, cfg["leagueId"])
        except FetchError as e:
            print("BLOCKED:", e)
            return 2
        problems = validate_standings(rows, cfg)
        doc = standings_doc(cfg, rows, started)
        os.makedirs(out_dir or OBS_DIR, exist_ok=True)
        ss._write(os.path.join(out_dir or OBS_DIR, f"STANDINGS-{doc['capturedAt'].replace(':', '').replace('-', '')}.json"), doc)
        print(f"standings {doc['capturedAt']} · {'started' if doc['started'] else 'not started (all 0-0-0)'}")
        for r in sorted(rows, key=lambda r: (r["rank"] or 99, -(r["pct"] or 0))):
            print(f"  {r['rank'] or '-':>2}  {r['teamName'][:32]:32} {r['w']}-{r['l']}-{r['t']}  {r['division']:5} GB {r['gb']}")
        for p_ in problems:
            print("  BLOCKING", p_)
        if args.write and not problems:
            ss._write(STANDINGS_PATH, doc)
            print(f"wrote {os.path.relpath(STANDINGS_PATH, ROOT)}; run build_league_state.py embed to publish")
        return 1 if problems else 0
    if args.cmd == "import-json":
        raw = normalize_manual(ss._load(args.file), cfg)
        when = args.captured_at or raw["capturedAt"]
        if not when:
            print("BLOCKED: the capture has no timestamp; pass --captured-at YYYY-MM-DDTHH:MM:SSZ")
            return 2
        obs = make_observation(cfg, raw["teams"], when, "manual-devtools")
        return _finish(obs, cfg, not args.no_save, require_full=True, out_dir=out_dir)
    obs = ss._load(args.file)
    if obs.get("kind") != "YAHOO_ROSTER_OBSERVATION":
        print("BLOCKED: not a Yahoo roster observation (use import-json for a DevTools capture)")
        return 2
    check, rec, text = _analyse(obs, cfg, obs.get("scope") == "FULL", out_dir)
    if args.cmd == "validate":
        text = "\n".join(text.splitlines()[:1 + len(check["blocking"]) + len(check["warnings"])]) + (
            "\nVALID" if not check["blocking"] else "\nINVALID")
    print(text)
    return 0 if not check["blocking"] else 1


if __name__ == "__main__":
    sys.exit(main())
