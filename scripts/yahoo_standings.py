#!/usr/bin/env python3
"""Yahoo league standings: read a saved standings page (or the browser helper's JSON), validate it strictly, normalise it, and keep
snapshots with a history -- the same shape of workflow as the Yahoo roster snapshots, with its own files and state.

Nothing here executes anything from a saved page: HTML is read with `html.parser` only. Standings are display data: they never
touch rosters, salaries, the Trade Lab, the draft or the transaction ledger.

    parse_standings_html(html, cfg)        -> {"rows", "sourceUpdatedText", "headers"}
    rows_from_capture_json(doc, cfg)       -> {"rows", "sourceUpdatedAt", "sourceUpdatedText"}
    resolve_source_time(text, season)      -> UTC ISO of "Mon Oct 26 03:00pm +07" (year from the fantasy season, weekday checked)
    validate(rows, cfg, team_map)          -> (blocking, warnings)
    build_snapshot(...)                    -> the normalised standings document (with a content digest that ignores capturedAt)
    classify(candidate, index, restore)    -> NO_CHANGE | STALE | CONFLICT | READY
    commit(...)                            -> atomic write of the snapshot and the index; the previous snapshot is kept
"""
from __future__ import annotations

import datetime
import hashlib
import html as htmllib
import json
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import season_state as ss  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = "yahoo-standings/1"
STANDINGS_DIR = os.path.join(ss.DATA_DIR, "standings")
DIVISIONS = ("East", "West")
PCT_TOLERANCE = 0.00051          # Yahoo prints three decimals
# header text on the page -> field. Required: every one of these must be present exactly once; extra columns are ignored.
HEADER_FIELDS = {"rank": "rank", "team": "team", "w-l-t": "record", "pct": "pct", "div": "divRecord", "gb": "gb",
                 "last week": "lastWeek", "waiver": "waiver", "moves": "moves"}
DIGEST_FIELDS = ("teamId", "rank", "division", "w", "l", "t", "pct", "divRecord", "gb", "lastWeek")
# waiver priority and the moves counter change all week without a standings update (every add/drop), so they are stored but are
# not part of the identity of a standings update: the same Yahoo update read twice must be NO_CHANGE.
MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class StandingsError(RuntimeError):
    """A page or file that is not a readable standings table. `code` is stable (tests and reports key on it)."""

    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


# ------------------------------------------------------------------ parsing
class _Page(HTMLParser):
    """Collects table#standingstable (header texts, division headings, team rows) and the page's 'Last standings update' text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0            # >0 while inside the standings table
        self.headers, self.rows, self.division = [], [], None
        self._th = self._td = self._h4 = None
        self._row = None
        self._skip = 0            # inside <script>/<style>: never read, never run
        self.loose = []           # text outside the table (footer)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
            return
        if tag == "table":
            if self.depth:
                self.depth += 1
            elif a.get("id") == "standingstable":
                self.depth = 1
            return
        if not self.depth:
            return
        if tag == "tr":
            self._row = {"target": a.get("data-target"), "cells": [], "links": []}
        elif tag == "th":
            self._th = []
        elif tag == "td":
            self._td = []
        elif tag == "h4":
            self._h4 = []
        elif tag == "a" and self._row is not None and a.get("href"):
            self._row["links"].append(a["href"])

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
            return
        if tag == "table" and self.depth:
            self.depth -= 1
            return
        if not self.depth:
            return
        if tag == "th" and self._th is not None:
            self.headers.append(" ".join("".join(self._th).split()))
            self._th = None
        elif tag == "h4" and self._h4 is not None:
            self.division = " ".join("".join(self._h4).split())
            self._h4 = None
        elif tag == "td" and self._td is not None and self._row is not None:
            self._row["cells"].append(" ".join("".join(self._td).split()))
            self._td = None
        elif tag == "tr" and self._row is not None:
            if self._row["target"] or self._row["links"]:
                self._row["division"] = self.division
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._skip:
            return
        if self.depth:
            for buf in (self._th, self._td, self._h4):
                if buf is not None:
                    buf.append(data)
        else:
            self.loose.append(data)


def _int_or_none(s):
    s = (s or "").strip()
    return int(s) if re.fullmatch(r"\d+", s) else None


def _float_or_none(s):
    s = (s or "").strip()
    return float(s) if re.fullmatch(r"\d*\.?\d+", s) else None


def _record(s, what):
    m = re.fullmatch(r"(\d+)-(\d+)-(\d+)", (s or "").strip())
    if not m:
        raise StandingsError("BAD_RECORD", f"{what} {s!r} is not W-L-T")
    return tuple(int(x) for x in m.groups())


def _team_id(row, league_id):
    """Yahoo's id comes from the row's link, never from the name or the row's position."""
    for src in [row.get("target")] + row.get("links", []):
        m = re.search(r"/nba/(\d+)/(\d+)/?$", src or "")
        if m:
            if m.group(1) != str(league_id):
                raise StandingsError("WRONG_LEAGUE", f"a row belongs to league {m.group(1)}, not {league_id}")
            return int(m.group(2))
    raise StandingsError("NO_TEAM_ID", "a standings row has no team link")


def classify_page(html: str) -> StandingsError:
    low = html.lower()
    if re.search(r'id="login-username"|name="username"|id="login-signin"|login\.yahoo\.com', html):
        return StandingsError("AUTH_REQUIRED", "this is Yahoo's sign-in page, not the standings table")
    if "collectconsent" in low or "guce.yahoo.com" in low:
        return StandingsError("CONSENT_REQUIRED", "this is Yahoo's consent page, not the standings table")
    return StandingsError("NO_TABLE", 'no table with id="standingstable" (layout changed, or not the standings page)')


def parse_standings_html(html: str, cfg: dict) -> dict:
    """-> {rows: [raw row dicts], sourceUpdatedText: str|None, headers: [...]} or StandingsError."""
    if 'id="standingstable"' not in html:
        raise classify_page(html)
    p = _Page()
    p.feed(html)
    p.close()
    heads = [h.strip().lower() for h in p.headers]
    cols, seen = {}, {}
    for i, h in enumerate(heads):
        if h in HEADER_FIELDS:
            seen[HEADER_FIELDS[h]] = seen.get(HEADER_FIELDS[h], 0) + 1
            cols.setdefault(HEADER_FIELDS[h], i)
    missing = sorted(set(HEADER_FIELDS.values()) - set(cols))
    dup = sorted(k for k, n in seen.items() if n > 1)
    if missing or dup:
        raise StandingsError("COLUMNS_CHANGED", "the table columns are not the ones this importer reads "
                             f"(missing {missing or 'none'}, repeated {dup or 'none'}; found {p.headers})")
    rows = []
    for r in p.rows:
        if len(r["cells"]) < len(heads):
            raise StandingsError("SHORT_ROW", f"a standings row has {len(r['cells'])} cells for {len(heads)} columns")
        c = {f: r["cells"][i] for f, i in cols.items()}
        w, l, t = _record(c["record"], "W-L-T")
        rows.append({"teamId": _team_id(r, cfg["leagueId"]), "yahooName": c["team"], "division": r.get("division"),
                     "rank": _int_or_none(c["rank"]), "w": w, "l": l, "t": t, "pct": _float_or_none(c["pct"]),
                     "divRecord": c["divRecord"] if re.fullmatch(r"\d+-\d+-\d+", c["divRecord"] or "") else None,
                     "gb": _float_or_none(c["gb"]), "lastWeek": c["lastWeek"] if re.fullmatch(r"\d+-\d+-\d+", c["lastWeek"] or "") else None,
                     "waiver": _int_or_none(c["waiver"]), "moves": _int_or_none(c["moves"])})
    page = " ".join(" ".join(p.loose).split())
    m = re.search(r"Last standings update:\s*((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+\w{3}\s+\d{1,2}\s+\d{1,2}:\d{2}\s*[ap]m\s+(?:[+-]\d{2}(?::?\d{2})?|[A-Z]{3,4}))", page)
    if m:
        text = m.group(1)
    else:                                  # the label is there but the time is in a shape we do not read: say so, do not guess
        tail = re.search(r"Last standings update:\s*(.{0,40})", page)
        text = tail.group(1) if tail else None
    return {"rows": rows, "sourceUpdatedText": text, "headers": p.headers}


ZONES = {"UTC": 0, "GMT": 0, "EDT": -4, "EST": -5, "CDT": -5, "CST": -6, "MDT": -6, "MST": -7, "PDT": -7, "PST": -8}


def resolve_source_time(text: str, season: str) -> str:
    """'Mon Oct 26 03:00pm +07' -> '2026-10-26T08:00:00Z'. Yahoo prints no year: it comes from the configured fantasy season
    (2026-27: Aug-Dec is 2026, Jan-Jul is 2027) and the weekday must agree with the date, so a wrong guess is rejected."""
    m = re.fullmatch(r"(\w{3})\s+(\w{3})\s+(\d{1,2})\s+(\d{1,2}):(\d{2})\s*([ap]m)\s+(?:([+-])(\d{2}):?(\d{2})?|([A-Z]{3,4}))", (text or "").strip(), re.I)
    if not m:
        raise StandingsError("TIMESTAMP_INVALID", f"cannot read the update time {text!r}")
    wd, mon, day, hh, mm, ampm, sign, oh, om, zone = m.groups()
    if mon.lower() not in MONTHS or wd.lower() not in WEEKDAYS:
        raise StandingsError("TIMESTAMP_INVALID", f"unknown weekday or month in {text!r}")
    start = int(season.split("-")[0])
    month = MONTHS[mon.lower()]
    year = start if month >= 8 else start + 1
    hour = int(hh) % 12 + (12 if ampm.lower() == "pm" else 0)
    if not (1 <= int(hh) <= 12 and int(mm) < 60):
        raise StandingsError("TIMESTAMP_INVALID", f"impossible clock time in {text!r}")
    if zone:                               # the logged-out page prints the league's zone by name, e.g. 'EDT'
        if zone.upper() not in ZONES:
            raise StandingsError("TIMESTAMP_INVALID", f"unknown time zone {zone!r} in {text!r}")
        tz = datetime.timezone(datetime.timedelta(hours=ZONES[zone.upper()]))
    else:
        tz = datetime.timezone(datetime.timedelta(hours=int(oh), minutes=int(om or 0)) * (1 if sign == "+" else -1))
    try:
        when = datetime.datetime(year, month, int(day), hour, int(mm), tzinfo=tz)
    except ValueError as e:
        raise StandingsError("TIMESTAMP_INVALID", f"{text!r} is not a calendar date in {year}: {e}") from None
    if WEEKDAYS[when.weekday()] != wd.lower():
        raise StandingsError("TIMESTAMP_INVALID", f"{text!r}: {mon} {day} {year} is a {WEEKDAYS[when.weekday()].title()}, not {wd}")
    return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


CAPTURE_REQUIRED = ("rank", "yahoo_team_id", "team_name", "division", "wins", "losses", "ties", "yahoo_pct", "division_record",
                    "games_behind", "last_week_record", "waiver_priority", "moves")


def rows_from_capture_json(doc: dict, cfg: dict) -> dict:
    """The normalized capture JSON (schema_version 1: what the browser helper downloads) -> the same raw rows as the HTML path."""
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise StandingsError("BAD_JSON", "not a standings capture (schema_version 1)")
    if str(doc.get("league_id")) != str(cfg["leagueId"]):
        raise StandingsError("WRONG_LEAGUE", f"capture is for league {doc.get('league_id')}, not {cfg['leagueId']}")
    when = doc.get("source_last_updated")
    try:
        stamp = datetime.datetime.fromisoformat(str(when).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("no UTC offset")
        updated = stamp.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError as e:
        raise StandingsError("TIMESTAMP_INVALID", f"source_last_updated {when!r}: {e}") from None
    rows = []
    for t in doc.get("teams") or []:
        gone = [k for k in CAPTURE_REQUIRED if k not in t]
        if gone:
            raise StandingsError("MISSING_FIELD", f"team {t.get('yahoo_team_id')} lacks {gone}")
        pct = t["yahoo_pct"]
        rows.append({"teamId": int(t["yahoo_team_id"]), "yahooName": t["team_name"], "division": t["division"], "rank": t["rank"],
                     "w": t["wins"], "l": t["losses"], "t": t["ties"], "pct": float(pct) if pct not in (None, "", "-") else None,
                     "divRecord": t["division_record"], "gb": None if t["games_behind"] in (None, "-") else float(t["games_behind"]),
                     "lastWeek": t["last_week_record"], "waiver": t["waiver_priority"], "moves": t["moves"]})
    return {"rows": rows, "sourceUpdatedAt": updated, "sourceUpdatedText": doc.get("source_last_updated_text")}


# --------------------------------------------------------------- validation
def validate(rows, cfg, franchise_of) -> tuple:
    """-> (blocking, warnings). `franchise_of(teamId)` -> franchise id or None (from rosters/team_map.json).
    Yahoo's own rank and tie order are never recomputed or reordered."""
    bad, warn = [], []
    want = sorted(cfg["teamIds"])
    ids = [r["teamId"] for r in rows]
    if len(rows) != len(want):
        bad.append(f"{len(rows)} teams found, the league has {len(want)}")
    if len(ids) != len(set(ids)):
        bad.append("a Yahoo team id appears more than once")
    if sorted(set(ids)) != want:
        bad.append(f"team ids {sorted(set(ids))} are not the league's {want}")
    for tid in sorted(set(ids)):
        if franchise_of(tid) is None:
            bad.append(f"Yahoo team {tid} is not mapped to a franchise in rosters/team_map.json")
    ranks = [r["rank"] for r in rows]
    if all(x is None for x in ranks):
        bad.append("Yahoo shows no ranks yet (the season has not started)")
    elif any(x is None for x in ranks):
        bad.append("a team has no rank")
    elif sorted(ranks) != list(range(1, len(want) + 1)):
        bad.append(f"ranks are not 1..{len(want)} exactly once each (got {sorted(ranks)})")
    for r in rows:
        who = f"team {r['teamId']}"
        for k in ("w", "l", "t"):
            if not isinstance(r[k], int) or r[k] < 0:
                bad.append(f"{who}: {k} is not a non-negative integer")
        for k in ("division", "divRecord"):
            if not r.get(k):
                bad.append(f"{who}: {k} is missing")
        games = (r["w"] or 0) + (r["l"] or 0) + (r["t"] or 0)
        if games:
            if r["pct"] is None:
                bad.append(f"{who}: pct is missing")
            elif abs(r["pct"] - (r["w"] + r["t"] / 2) / games) > PCT_TOLERANCE:
                bad.append(f"{who}: pct {r['pct']} does not match {r['w']}-{r['l']}-{r['t']}")
    divs = [r.get("division") for r in rows]
    if any(d not in DIVISIONS for d in divs):
        bad.append(f"divisions must be {' / '.join(DIVISIONS)}, got {sorted(set(map(str, divs)))}")
    else:
        for d in DIVISIONS:
            if divs.count(d) != len(want) // 2:
                bad.append(f"{d} has {divs.count(d)} teams, expected {len(want) // 2}")
    if sum(r["w"] for r in rows) != sum(r["l"] for r in rows):
        bad.append("league-wide wins do not equal losses (every category result has a winner and a loser)")
    if sum(r["t"] for r in rows) % 2:
        bad.append("league-wide ties are odd (a tie is shared by two teams)")
    # warnings: unusual but not impossible
    totals = {r["w"] + r["l"] + r["t"] for r in rows}
    if len(totals) > 1:
        warn.append(f"teams have played different numbers of category results {sorted(totals)}")
    ordered = sorted((r for r in rows if r["rank"]), key=lambda r: r["rank"])
    for a, b in zip(ordered, ordered[1:]):
        if a["pct"] is not None and b["pct"] is not None and a["pct"] + 0.0006 < b["pct"]:
            warn.append(f"rank {a['rank']} has a lower pct than rank {b['rank']} (Yahoo's order is kept as printed)")
    if ordered:
        top = ordered[0]
        for r in ordered:
            expect = ((top["w"] - r["w"]) + (r["l"] - top["l"])) / 2
            got = r["gb"] if r["gb"] is not None else 0.0
            if abs(expect - got) > 0.01:
                warn.append(f"team {r['teamId']}: GB {r['gb']} differs from the formula value {expect:g}")
    return bad, warn


# ----------------------------------------------------------------- snapshot
def _digest(snap: dict) -> str:
    """A hash of the standings content only: it ignores capturedAt, team names and franchise ids, so the same Yahoo page imported on
    two different days is the same snapshot."""
    body = {"schema": SCHEMA, "leagueId": snap["leagueId"], "sourceUpdatedAt": snap["sourceUpdatedAt"],
            "teams": [{k: t.get(k) for k in DIGEST_FIELDS} for t in sorted(snap["teams"], key=lambda t: (t["rank"] is None, t["rank"] or 0, t["teamId"]))]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def build_snapshot(rows, cfg, franchise_of, source_updated_at, source_updated_text, captured_at, source_kind, season) -> dict:
    teams = []
    for r in sorted(rows, key=lambda r: (r["rank"] is None, r["rank"] or 0, r["teamId"])):
        teams.append({"franchiseId": franchise_of(r["teamId"]), "teamId": r["teamId"], "yahooName": r.get("yahooName"),
                      "division": r["division"], "rank": r["rank"], "w": r["w"], "l": r["l"], "t": r["t"], "pct": r["pct"],
                      "divRecord": r["divRecord"], "gb": r["gb"], "lastWeek": r["lastWeek"], "waiver": r["waiver"], "moves": r["moves"]})
    snap = {"schema": SCHEMA, "season": season, "leagueId": str(cfg["leagueId"]),
            "started": any(t["rank"] for t in teams) and any(t["w"] + t["l"] + t["t"] for t in teams),
            "sourceUpdatedAt": source_updated_at, "sourceUpdatedText": source_updated_text, "capturedAt": captured_at,
            "source": f"Yahoo Fantasy league {cfg['leagueId']} standings table ({source_kind})",
            "note": "Head-to-head category record (W-L-T) as Yahoo prints it; Yahoo's rank and tie order are kept as printed. "
                    "Display data only: it never changes rosters, salaries, trades, the draft or the ledger.",
            "teams": teams}
    snap["digest"] = _digest(snap)
    return snap


def snapshot_id(snap: dict) -> str:
    stamp = (snap["sourceUpdatedAt"] or snap["capturedAt"]).replace("-", "").replace(":", "")
    return f"ST-{stamp}-{snap['digest'][:8]}"


def load_index(standings_dir=STANDINGS_DIR):
    path = os.path.join(standings_dir, "index.json")
    return ss._load(path) if os.path.exists(path) else None


def current_snapshot(standings_dir=STANDINGS_DIR):
    idx = load_index(standings_dir)
    if not idx or not idx.get("current"):
        return None
    return ss._load(os.path.join(standings_dir, idx["current"]))


def classify(candidate: dict, current, allow_restore=False) -> str:
    """NO_CHANGE: same content. STALE: Yahoo's own update time is older than the published one. CONFLICT: the same update time
    with different content (a revision that needs a human, never an overwrite). READY: newer (or an authorised restore)."""
    if current is None:
        return "READY"
    if candidate["digest"] == current["digest"]:
        return "NO_CHANGE"
    cur_t, new_t = current.get("sourceUpdatedAt"), candidate["sourceUpdatedAt"]
    if cur_t is None:
        return "READY"
    if new_t == cur_t:
        return "CONFLICT"
    if new_t < cur_t and not allow_restore:
        return "STALE"
    return "READY"


def commit(snap: dict, standings_dir=STANDINGS_DIR, action="IMPORT", reason=None) -> str:
    """Write the snapshot and move the pointer. Both files go through a temp file and an atomic rename; the previous snapshot stays."""
    idx = load_index(standings_dir) or {"note": "Yahoo standings snapshots. `current` is the one the site shows; every earlier snapshot is kept.",
                                        "current": None, "history": []}
    sid = snapshot_id(snap)
    rel = os.path.join("snapshots", sid + ".json")
    path = os.path.join(standings_dir, rel)
    if os.path.exists(path):
        raise StandingsError("SNAPSHOT_EXISTS", f"{rel} already exists")
    entry = {"snapshotId": sid, "file": rel, "sourceUpdatedAt": snap["sourceUpdatedAt"], "capturedAt": snap["capturedAt"],
             "digest": snap["digest"], "action": action, "previous": idx["current"]}
    if reason:
        entry["reason"] = reason
    new_idx = {**idx, "current": rel, "history": idx["history"] + [entry]}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_snap, tmp_idx = path + ".tmp", os.path.join(standings_dir, "index.json.tmp")
    try:
        ss._write(tmp_snap, {**snap, "snapshotId": sid})
        ss._write(tmp_idx, new_idx)
        os.replace(tmp_snap, path)
        os.replace(tmp_idx, os.path.join(standings_dir, "index.json"))
    finally:
        for p in (tmp_snap, tmp_idx):
            if os.path.exists(p):
                os.remove(p)
    return sid


# --------------------------------------------------------------------- diff
def _gb(x) -> str:
    return "-" if x is None else f"{x:g}"


def diff(current, cand) -> list:
    """Human lines: what moved between the published snapshot and the candidate (by Yahoo team id; names are only labels)."""
    lines = []
    old = {t["teamId"]: t for t in (current or {}).get("teams", [])}
    for t in sorted(cand["teams"], key=lambda t: t["rank"] or 99):
        o = old.get(t["teamId"])
        rec = f"{t['w']}-{t['l']}-{t['t']}"
        if o is None or o["rank"] is None:
            lines.append(f"{t['rank']:>2}  {t['yahooName']}  {rec}  (first in-season capture)")
            continue
        parts = []
        if o["rank"] != t["rank"]:
            parts.append(f"rank {o['rank']} → {t['rank']} ({'↑' if t['rank'] < o['rank'] else '↓'}{abs(t['rank'] - o['rank'])})")
        if (o["w"], o["l"], o["t"]) != (t["w"], t["l"], t["t"]):
            parts.append(f"record {o['w']}-{o['l']}-{o['t']} → {rec}")
        if o["division"] != t["division"]:
            parts.append(f"division {o['division']} → {t['division']}")
        if o["gb"] != t["gb"]:
            parts.append(f"GB {_gb(o['gb'])} → {_gb(t['gb'])}")
        if parts:
            lines.append(f"{t['rank']:>2}  {t['yahooName']}  {rec}  " + "; ".join(parts))
    return lines
