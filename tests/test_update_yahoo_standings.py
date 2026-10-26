"""Yahoo standings importer: the real Oct 26 page, strict validation, outcomes, snapshots and the published order.

Fixtures (tests/fixtures/yahoo/): `yahoo_standings_2026-10-26_real_sanitized.html` is the REAL page's #standingstable markup and
Yahoo's update time (scripts, ads, cookies and unrelated page material removed by the owner); `NBA_Talk_Dynasty_Standings_2026-10-26.json`
is the normalized capture of the same page. Every malformed variant below is a MUTATION of that real HTML, made in the test, and is
named as such. Expectations are keyed on Yahoo team ids, names and ranks; nothing pins today's published standings."""
import copy
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_league_state as bls  # noqa: E402
import import_rosters as ir  # noqa: E402
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402
import update_yahoo_standings as uys  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
import yahoo_standings as ys  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "yahoo")
REAL_HTML = os.path.join(FIX, "yahoo_standings_2026-10-26_real_sanitized.html")
REAL_JSON = os.path.join(FIX, "NBA_Talk_Dynasty_Standings_2026-10-26.json")
PRESEASON_HTML = os.path.join(FIX, "standings_2026-10-19.html")
CFG = yr.load_config()
SEEN = "2026-10-26T14:30:00Z"
LOGIN = '<html><body><form id="login-signin"><input id="login-username"></form></body></html>'


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


HTML = read(REAL_HTML)
CAPTURE = json.loads(read(REAL_JSON))


# ---- mutation helpers: they edit the REAL html text
def row_span(html, tid):
    m = re.search(r'<tr class="Linkable[^"]*" data-target="/nba/85092/%d">.*?</tr>' % tid, html, re.S)
    return m.span()


def drop_team(html, tid):
    a, b = row_span(html, tid)
    return html[:a] + html[b:]


def duplicate_team(html, tid):
    a, b = row_span(html, tid)
    return html[:b] + html[a:b] + html[b:]


def set_cell(html, tid, col, value):
    """Replace the whole content of the col-th <td> (0 = rank ... 8 = moves) of one team's row."""
    a, b = row_span(html, tid)
    row = html[a:b]
    tds = list(re.finditer(r"(<td[^>]*>).*?(</td>)", row, re.S))
    m = tds[col]
    return html[:a] + row[:m.start()] + m.group(1) + value + m.group(2) + row[m.end():] + html[b:]


def set_footer(html, text):
    return re.sub(r"Last standings update:[^<]*", "Last standings update: " + text if text else "", html)


def team_info(rows):
    return {r["teamId"]: r for r in rows}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.team_map, _ = ir.load_maps(ss.DATA_DIR)
        cls.fo = staticmethod(lambda tid: yr.franchise_for(CFG, cls.team_map, tid))

    def parse(self, html=HTML):
        return ys.parse_standings_html(html, CFG)

    def blocking(self, html):
        rows = self.parse(html)["rows"]
        return ys.validate(rows, CFG, self.fo)[0]


class TestRealPage(Base):
    def test_parses_the_real_page_and_matches_the_normalized_capture(self):
        page = self.parse()
        rows = page["rows"]
        self.assertEqual(len(rows), 16)
        self.assertEqual(sorted(r["teamId"] for r in rows), CFG["teamIds"])           # not contiguous: 10 does not exist
        capture = ys.rows_from_capture_json(CAPTURE, CFG)
        by_html, by_json = team_info(rows), team_info(capture["rows"])
        self.assertEqual(set(by_html), set(by_json))
        for tid, r in by_html.items():                                                 # field by field, the real HTML == the JSON
            for k in r:
                if k != "yahooName":
                    self.assertEqual(r[k], by_json[tid][k], (tid, k))
            self.assertEqual(r["yahooName"], next(t["team_name"] for t in CAPTURE["teams"] if t["yahoo_team_id"] == tid))
        self.assertEqual(ys.resolve_source_time(page["sourceUpdatedText"], "2026-27"), capture["sourceUpdatedAt"])

    def test_known_teams_and_ranks_from_the_real_page(self):
        by = team_info(self.parse()["rows"])
        self.assertEqual((by[8]["rank"], by[8]["yahooName"], (by[8]["w"], by[8]["l"], by[8]["t"])), (1, "Hai | Bulls Dynasty", (7, 1, 1)))
        self.assertEqual((by[17]["rank"], by[17]["yahooName"], (by[17]["w"], by[17]["l"], by[17]["t"])), (2, "TuLy | No country for Old Men", (7, 1, 1)))
        self.assertEqual((by[3]["rank"], by[3]["yahooName"], (by[3]["w"], by[3]["l"], by[3]["t"])), (12, "Bz | Putin the tank driver", (3, 6, 0)))
        self.assertEqual((by[8]["division"], by[17]["division"], by[3]["division"]), ("West", "East", "East"))
        self.assertEqual((by[12]["rank"], by[13]["rank"]), (15, 16))                   # 1-7-1 each: Yahoo's tie order is kept
        self.assertEqual((by[12]["pct"], by[13]["pct"]), (by[13]["pct"], 0.167))

    def test_yahoo_team_ids_map_to_franchises_through_team_map_not_position_or_name(self):
        fo = self.fo
        self.assertEqual(len({fo(t) for t in CFG["teamIds"]}), 16)
        self.assertIsNone(fo(10))                                                       # there is no Yahoo team 10
        tuly = fo(17)
        self.assertIn("tuly", {a.lower() for a in self.team_map["teams"][tuly]["aliases"]})   # id 17 is TuLy, found via the map
        self.assertNotEqual(int(tuly.split("-")[1]), 17)                                # and is not the 17th franchise

    def test_source_values_are_preserved_not_invented(self):
        by = team_info(self.parse()["rows"])
        self.assertIsNone(by[8]["gb"])                                                  # leaders print "-"
        self.assertIsNone(by[17]["gb"])
        self.assertEqual(by[5]["gb"], 0.5)
        self.assertIsNone(by[9]["moves"])                                               # HCMC's moves is "-"
        self.assertEqual(by[7]["divRecord"], "0-0-0")                                   # Dũng's division record really is 0-0-0
        self.assertEqual(by[7]["lastWeek"], "3-5-1")
        self.assertGreaterEqual(min(r["w"] + r["l"] + r["t"] for r in by.values()), 9)  # totals are read, never assumed to be nine

    def test_the_real_page_is_valid_with_no_warnings(self):
        rows = self.parse()["rows"]
        bad, warn = ys.validate(rows, CFG, self.fo)
        self.assertEqual((bad, warn), ([], []))
        self.assertEqual(sum(r["w"] for r in rows), sum(r["l"] for r in rows))
        self.assertEqual([sum(r["division"] == d for r in rows) for d in ys.DIVISIONS], [8, 8])

    def test_rows_may_come_in_any_order_and_columns_by_header_not_position(self):
        """MUTATION: swap the Pct and GB columns (header + every cell). The header names, not positions, pick the data."""
        # build the swapped table with a clearer, cell-wise approach
        swapped = HTML
        for tid in CFG["teamIds"]:
            a, b = row_span(swapped, tid)
            tds = list(re.finditer(r"<td[^>]*>(.*?)</td>", swapped[a:b], re.S))
            pct_val, gb_val = tds[3].group(1), tds[5].group(1)
            swapped = set_cell(set_cell(swapped, tid, 3, gb_val), tid, 5, pct_val)
        swapped = swapped.replace("<span>Pct</span>", "@@").replace("<span>GB</span>", "<span>Pct</span>").replace("@@", "<span>GB</span>")
        got = team_info(self.parse(swapped)["rows"])
        want = team_info(self.parse()["rows"])
        for tid in want:
            self.assertEqual((got[tid]["pct"], got[tid]["gb"]), (want[tid]["pct"], want[tid]["gb"]), tid)
        # (the real page lists East then West, each in rank order: row order is already not the overall rank order)
        order = [r["teamId"] for r in self.parse()["rows"]]
        self.assertNotEqual(order, [r["teamId"] for r in sorted(self.parse()["rows"], key=lambda r: r["rank"])])

    def test_an_extra_column_is_ignored_but_a_renamed_or_missing_one_fails(self):
        """MUTATIONS of the real header row."""
        extra = HTML.replace('<th class="last Ta-c Px-sm">Moves</th>', '<th class="Ta-c">Moves</th><th>Streak</th>')
        for tid in CFG["teamIds"]:
            a, b = row_span(extra, tid)
            extra = extra[:b - len("</tr>")] + "<td>W3</td>" + extra[b - len("</tr>"):]
        self.assertEqual(len(self.parse(extra)["rows"]), 16)
        for old, new in (("<span>Pct</span>", "<span>Percent</span>"), ("<span>GB</span>", "<span>Games Back</span>"),
                         ("<span>Waiver</span>", "<span>Priority</span>"), ("<span>W-L-T</span>", "<span>Record</span>")):
            with self.assertRaises(ys.StandingsError) as cm:
                self.parse(HTML.replace(old, new))
            self.assertEqual(cm.exception.code, "COLUMNS_CHANGED")

    def test_script_in_the_page_is_never_executed_or_read_as_data(self):
        """MUTATION: a script that would break the parser if anything ran it, plus a script that looks like a standings row."""
        hostile = HTML.replace("</body>", '<script>throw new Error("executed"); document.title="x";</script>'
                               '<script>"<tr data-target=\'/nba/85092/1\'><td>1</td></tr>"</script></body>')
        self.assertEqual(self.parse(hostile)["rows"], self.parse()["rows"])

    def test_page_with_other_markup_around_the_table_still_reads(self):
        """MUTATION: navigation, ads and a second table around the real one."""
        wrapped = HTML.replace("<body>", '<body><nav>Home Fantasy Mail</nav><table id="other"><tr><td>1</td></tr></table>').replace(
            "</body>", "<footer>ads</footer></body>")
        self.assertEqual(self.parse(wrapped)["rows"], self.parse()["rows"])


class TestTimestamps(Base):
    def test_the_year_comes_from_the_fantasy_season_and_the_weekday_must_agree(self):
        text = self.parse()["sourceUpdatedText"]
        self.assertEqual(text, "Mon Oct 26 03:00pm +07")
        self.assertEqual(ys.resolve_source_time(text, "2026-27"), "2026-10-26T08:00:00Z")      # 15:00 +07 = 08:00 UTC
        self.assertEqual(ys.resolve_source_time("Mon Jan 04 12:15am +07", "2026-27"), "2027-01-03T17:15:00Z")   # Jan is 2027
        with self.assertRaises(ys.StandingsError) as cm:                                      # same text in 2027-28 is a Tuesday
            ys.resolve_source_time(text, "2027-28")
        self.assertEqual(cm.exception.code, "TIMESTAMP_INVALID")
        self.assertIn("Tue", cm.exception.detail)

    def test_wrong_weekday_impossible_date_and_garbage_are_rejected(self):
        for bad in ("Tue Oct 26 03:00pm +07", "Mon Oct 26 13:00pm +07", "Mon Feb 30 03:00pm +07", "Mon Oct 26 03:00pm", "yesterday", ""):
            with self.assertRaises(ys.StandingsError, msg=bad):
                ys.resolve_source_time(bad, "2026-27")

    def test_a_page_without_an_update_time_is_rejected_by_the_importer(self):
        for html in (set_footer(HTML, ""), set_footer(HTML, "sometime last week")):
            with fresh_data() as d:
                res = uys.run(CFG, {"kind": "html", "text": html, "name": "x.html"}, d.out, data_dir=d.dir, captured_at=SEEN)
                self.assertEqual(res["outcome"], "FAILED")

    def test_source_time_and_capture_time_are_different_fields(self):
        with fresh_data() as d:
            res = uys.run(CFG, real_source(), d.out, data_dir=d.dir, apply=True, captured_at="2026-10-27T01:02:03Z")
            snap = ys.current_snapshot(d.standings)
            self.assertEqual((snap["sourceUpdatedAt"], snap["capturedAt"]), ("2026-10-26T08:00:00Z", "2026-10-27T01:02:03Z"))
            self.assertEqual(res["outcome"], "READY")


class TestValidation(Base):
    """Each case MUTATES the real page and must reject the whole snapshot."""

    def test_missing_duplicated_or_unknown_teams(self):
        self.assertTrue(any("15 teams" in b for b in self.blocking(drop_team(HTML, 17))))
        dup = self.blocking(duplicate_team(HTML, 17))
        self.assertTrue(any("more than once" in b for b in dup) and any("17 teams" in b for b in dup))
        other = HTML.replace('data-target="/nba/85092/17"', 'data-target="/nba/85092/18"').replace('href="/nba/85092/17"', 'href="/nba/85092/18"').replace(
            'nba/85092/17">TuLy', 'nba/85092/18">TuLy')
        self.assertTrue(any("not the league's" in b for b in self.blocking(other)))

    def test_ranks_must_be_one_to_sixteen_exactly_once(self):
        self.assertTrue(any("ranks" in b for b in self.blocking(set_cell(HTML, 17, 0, "<span>1</span>"))))      # duplicate rank
        self.assertTrue(any("no rank" in b for b in self.blocking(set_cell(HTML, 17, 0, "<span></span>"))))     # missing rank
        self.assertTrue(any("ranks" in b for b in self.blocking(set_cell(HTML, 17, 0, "<span>17</span>"))))     # out of range

    def test_records_must_be_valid_and_pct_must_match_them(self):
        for bad in ("7-1", "a-b-c", "-7-1-1", "7-1-1-0", ""):
            with self.assertRaises(ys.StandingsError, msg=bad) as cm:
                self.parse(set_cell(HTML, 17, 2, bad))
            self.assertEqual(cm.exception.code, "BAD_RECORD")
        self.assertTrue(any("pct" in b for b in self.blocking(set_cell(HTML, 17, 3, ".999"))))
        self.assertTrue(any("pct is missing" in b for b in self.blocking(set_cell(HTML, 17, 3, "-"))))

    def test_league_wide_results_must_balance(self):
        """MUTATION: one extra win (the pct is fixed up so only the league-wide check can notice)."""
        m = set_cell(set_cell(HTML, 17, 2, "8-1-1"), 17, 3, ".850")
        bad = self.blocking(m)
        self.assertTrue(any("wins do not equal losses" in b for b in bad), bad)

    def test_divisions_must_be_east_and_west_with_eight_teams_each(self):
        """MUTATION: move the East team 17 under the West heading, then rename a heading."""
        a, b = row_span(HTML, 17)
        row = HTML[a:b]
        moved = HTML[:a] + HTML[b:]
        moved = moved.replace("</tbody>", row + "</tbody>")
        self.assertTrue(any("East has 7" in b_ or "West has 9" in b_ for b_ in self.blocking(moved)))
        self.assertTrue(any("divisions must be" in b_ for b_ in self.blocking(HTML.replace(">East<", ">Atlantic<"))))

    def test_short_rows_login_consent_empty_and_preseason_pages_fail(self):
        a, b = row_span(HTML, 17)
        with self.assertRaises(ys.StandingsError) as cm:
            self.parse(HTML[:a] + "<tr data-target=\"/nba/85092/17\"><td>2</td></tr>" + HTML[b:])
        self.assertEqual(cm.exception.code, "SHORT_ROW")
        with self.assertRaises(ys.StandingsError) as cm:
            self.parse(LOGIN)
        self.assertEqual(cm.exception.code, "AUTH_REQUIRED")
        with self.assertRaises(ys.StandingsError) as cm:
            self.parse("<html><body>no table</body></html>")
        self.assertEqual(cm.exception.code, "NO_TABLE")
        pre = self.parse(read(PRESEASON_HTML))                                           # the real pre-season page (all 0-0-0, no ranks)
        self.assertTrue(any("season has not started" in b for b in ys.validate(pre["rows"], CFG, self.fo)[0]))

    def test_a_row_from_another_league_is_rejected(self):
        with self.assertRaises(ys.StandingsError) as cm:
            self.parse(HTML.replace('data-target="/nba/85092/17"', 'data-target="/nba/99999/17"'))
        self.assertEqual(cm.exception.code, "WRONG_LEAGUE")

    def test_capture_json_must_have_every_field_and_the_right_league(self):
        broken = copy.deepcopy(CAPTURE)
        del broken["teams"][0]["wins"]
        with self.assertRaises(ys.StandingsError) as cm:
            ys.rows_from_capture_json(broken, CFG)
        self.assertEqual(cm.exception.code, "MISSING_FIELD")
        other = dict(CAPTURE, league_id="1")
        with self.assertRaises(ys.StandingsError):
            ys.rows_from_capture_json(other, CFG)
        naive = dict(CAPTURE, source_last_updated="2026-10-26T15:00:00")                   # no UTC offset: ambiguous, rejected
        with self.assertRaises(ys.StandingsError):
            ys.rows_from_capture_json(naive, CFG)


# ------------------------------------------------------------------ workflow
class fresh_data:
    """A private copy of data/2026-27 with NO standings published, plus an artifacts folder."""

    def __init__(self, seed=None):
        self.seed = seed

    def __enter__(self):
        self.root = tempfile.mkdtemp()
        self.dir = os.path.join(self.root, "2026-27")
        shutil.copytree(ls.DATA_DIR, self.dir)
        self.standings = os.path.join(self.dir, "standings")
        shutil.rmtree(self.standings, ignore_errors=True)
        self.out = os.path.join(self.root, "out")
        return self

    def __exit__(self, *a):
        shutil.rmtree(self.root, ignore_errors=True)


def real_source():
    return {"kind": "html", "text": HTML, "name": "real.html"}


def capture_source(doc):
    return {"kind": "json", "text": json.dumps(doc), "name": "capture.json"}


def variant(source_last_updated=None, swap=None):
    """A VALID capture derived from the real one: optionally a new Yahoo time, and one category result moved between two teams
    (the first loses a win and gains a loss, the second the reverse), so league-wide wins still equal losses."""
    doc = copy.deepcopy(CAPTURE)
    if source_last_updated:
        doc["source_last_updated"] = source_last_updated
    if swap:
        a, b = (next(t for t in doc["teams"] if t["yahoo_team_id"] == i) for i in swap)
        for t, d in ((a, -1), (b, 1)):
            t["wins"] += d
            t["losses"] -= d
            games = t["wins"] + t["losses"] + t["ties"]
            t["yahoo_pct"] = ("%.3f" % ((t["wins"] + t["ties"] / 2) / games)).lstrip("0")
    return doc


class TestOutcomes(Base):
    def run_(self, d, source, **kw):
        kw.setdefault("captured_at", SEEN)
        return uys.run(CFG, source, d.out, data_dir=d.dir, **kw)

    def test_a_dry_run_changes_nothing_authoritative(self):
        with fresh_data() as d:
            before = uys.tree_digest(d.dir, exclude=())
            res = self.run_(d, real_source())
            self.assertEqual(res["outcome"], "READY")
            self.assertEqual(uys.tree_digest(d.dir, exclude=()), before)            # not even the standings folder
            self.assertFalse(os.path.exists(d.standings))
            report = read(res["report"])                                              # only the disposable report was written
            self.assertIn("READY", report)
            self.assertIn("Dry run: nothing was written", report)
            self.assertIn("Hai \\| Bulls Dynasty", report)                           # table-safe team names

    def test_apply_writes_a_snapshot_keeps_the_previous_and_touches_nothing_else(self):
        with fresh_data() as d:
            others = uys.tree_digest(d.dir)
            first = self.run_(d, capture_source(variant()), apply=True)
            self.assertEqual(first["outcome"], "READY")
            idx = ys.load_index(d.standings)
            self.assertEqual([h["action"] for h in idx["history"]], ["IMPORT"])
            second = self.run_(d, capture_source(variant("2026-10-27T15:00:00+07:00", swap=(17, 3))), apply=True, captured_at="2026-10-27T09:00:00Z")
            self.assertEqual(second["outcome"], "READY")
            idx = ys.load_index(d.standings)
            self.assertEqual(len(idx["history"]), 2)
            self.assertEqual(idx["history"][1]["previous"], idx["history"][0]["file"])
            first_snap = os.path.join(d.standings, idx["history"][0]["file"])
            self.assertTrue(os.path.exists(first_snap))                               # the previous snapshot is preserved
            with open(first_snap, "rb") as f:
                self.assertEqual(json.load(io.TextIOWrapper(io.BytesIO(f.read())))["digest"], idx["history"][0]["digest"])
            self.assertEqual(uys.tree_digest(d.dir), others)                          # rosters, salaries, trades, draft, ledger: identical
            self.assertEqual(ys.current_snapshot(d.standings)["sourceUpdatedAt"], "2026-10-27T08:00:00Z")
            self.assertIn("record 3-6-0 → 4-5-0", read(second["report"]))                # the diff names the change
            self.assertIn("record 7-1-1 → 6-2-1", read(second["report"]))

    def test_the_same_source_on_a_different_day_is_no_change_and_writes_nothing(self):
        with fresh_data() as d:
            self.run_(d, real_source(), apply=True, captured_at="2026-10-26T14:30:00Z")
            before = uys.tree_digest(d.dir, exclude=())
            again = self.run_(d, real_source(), apply=True, captured_at="2026-11-03T09:00:00Z")      # a week later
            self.assertEqual(again["outcome"], "NO_CHANGE")
            self.assertEqual(again["exit"], 0)
            self.assertEqual(uys.tree_digest(d.dir, exclude=()), before)
            via_json = self.run_(d, capture_source(variant()), apply=True)                          # the JSON of the same page is the same content
            self.assertEqual(via_json["outcome"], "NO_CHANGE")
            self.assertEqual(len(ys.load_index(d.standings)["history"]), 1)

    def test_the_digest_ignores_capture_time_names_and_franchise_ids_but_not_content(self):
        rows = self.parse()["rows"]
        fo = self.fo
        mk = lambda rows_, cap, at="2026-10-26T08:00:00Z": ys.build_snapshot(rows_, CFG, fo, at, "t", cap, "html", "2026-27")["digest"]  # noqa: E731
        base = mk(rows, "2026-10-26T14:30:00Z")
        self.assertEqual(base, mk(rows, "2027-01-01T00:00:00Z"))
        renamed = [dict(r, yahooName="Something else") for r in rows]
        self.assertEqual(base, mk(renamed, SEEN))
        edited = copy.deepcopy(rows)
        edited[0]["moves"] += 1
        self.assertNotEqual(base, mk(edited, SEEN))
        self.assertNotEqual(base, mk(rows, SEEN, at="2026-10-26T08:01:00Z"))

    def test_same_yahoo_time_with_different_content_is_a_conflict_never_an_overwrite(self):
        with fresh_data() as d:
            self.run_(d, capture_source(variant()), apply=True)
            before = uys.tree_digest(d.dir, exclude=())
            res = self.run_(d, capture_source(variant(swap=(17, 3))), apply=True)               # same source time, different records
            self.assertEqual((res["outcome"], res["exit"]), ("CONFLICT", 1))
            self.assertEqual(uys.tree_digest(d.dir, exclude=()), before)
            self.assertIn("needs a commissioner's review", read(res["report"]))

    def test_an_older_yahoo_update_is_stale_unless_a_restore_is_authorised(self):
        with fresh_data() as d:
            self.run_(d, capture_source(variant("2026-10-27T15:00:00+07:00", swap=(17, 3))), apply=True)
            before = uys.tree_digest(d.dir, exclude=())
            stale = self.run_(d, real_source(), apply=True)                                      # Oct 26 is older than Oct 27
            self.assertEqual((stale["outcome"], stale["exit"]), ("STALE", 1))
            self.assertEqual(uys.tree_digest(d.dir, exclude=()), before)
            nore = self.run_(d, real_source(), apply=True, allow_restore=True)                    # a restore must say why
            self.assertEqual(nore["outcome"], "FAILED")
            self.assertEqual(uys.tree_digest(d.dir, exclude=()), before)
            ok = self.run_(d, real_source(), apply=True, allow_restore=True, reason="owner restored the Oct 26 capture")
            self.assertEqual(ok["outcome"], "READY")
            hist = ys.load_index(d.standings)["history"]
            self.assertEqual((hist[-1]["action"], hist[-1]["reason"]), ("RESTORE", "owner restored the Oct 26 capture"))
            self.assertEqual(len(hist), 2)                                                        # nothing was deleted

    def test_a_rejected_snapshot_leaves_the_published_standings_untouched(self):
        with fresh_data() as d:
            self.run_(d, real_source(), apply=True)
            published = read(os.path.join(d.standings, "index.json"))
            before = uys.tree_digest(d.dir, exclude=())
            for html in (drop_team(HTML, 17), set_cell(HTML, 17, 3, ".999"), LOGIN, set_footer(HTML, "")):
                res = self.run_(d, {"kind": "html", "text": html, "name": "bad.html"}, apply=True)
                self.assertEqual((res["outcome"], res["exit"]), ("FAILED", 1))
                self.assertIn("published standings were not changed", read(res["report"]))
            self.assertEqual(uys.tree_digest(d.dir, exclude=()), before)
            self.assertEqual(read(os.path.join(d.standings, "index.json")), published)

    def test_division_changes_are_reported_as_warnings_not_hidden(self):
        with fresh_data() as d:
            self.run_(d, real_source(), apply=True)
            moved = variant("2026-10-27T15:00:00+07:00")
            moved["teams"][0]["division"] = "East"
            moved["teams"][1]["division"] = "West"                                                 # still 8/8, but two teams switched
            res = self.run_(d, capture_source(moved))
            self.assertEqual(res["outcome"], "READY")
            self.assertIn("moved from the", read(res["report"]))

    def test_a_malformed_json_file_is_rejected(self):
        with fresh_data() as d:
            res = self.run_(d, {"kind": "json", "text": "{not json", "name": "x.json"})
            self.assertEqual(res["outcome"], "FAILED")


class TestCommandLine(Base):
    def test_main_dry_run_on_the_real_page_writes_only_its_report(self):
        out = tempfile.mkdtemp()
        try:
            before = uys.tree_digest(ss.DATA_DIR, exclude=())
            with redirect_stdout(io.StringIO()) as buf:
                rc = uys.main(["--input", REAL_HTML, "--out", out, "--captured-at", SEEN])
            self.assertIn(rc, (0,))
            self.assertEqual(uys.tree_digest(ss.DATA_DIR, exclude=()), before)               # the repository's own data: untouched
            self.assertTrue(os.path.exists(os.path.join(out, "report.md")))
            self.assertRegex(buf.getvalue(), r"(READY|NO_CHANGE): report at")
        finally:
            shutil.rmtree(out)

    def test_apply_and_dry_run_contradict_and_a_missing_file_fails_visibly(self):
        out = tempfile.mkdtemp()
        try:
            with self.assertRaises(SystemExit):
                with redirect_stdout(io.StringIO()):
                    uys.main(["--input", REAL_HTML, "--apply", "--dry-run", "--out", out])
            with redirect_stdout(io.StringIO()) as buf:
                rc = uys.main(["--input", os.path.join(out, "missing.html"), "--out", out])
            self.assertEqual(rc, 1)
            self.assertIn("FAILED", buf.getvalue())
            self.assertIn("FAILED", read(os.path.join(out, "report.md")))
        finally:
            shutil.rmtree(out)

    def test_github_output_gets_the_outcome(self):
        out, tmp = tempfile.mkdtemp(), tempfile.mkdtemp()
        gh = os.path.join(tmp, "gh_output")
        try:
            os.environ["GITHUB_OUTPUT"] = gh
            with redirect_stdout(io.StringIO()):
                uys.main(["--input", REAL_HTML, "--out", out])
            self.assertRegex(read(gh), r"outcome=(READY|NO_CHANGE)\n")
        finally:
            os.environ.pop("GITHUB_OUTPUT", None)
            shutil.rmtree(out)
            shutil.rmtree(tmp)

    def test_the_old_roster_script_command_delegates_and_does_not_write_without_a_flag(self):
        out, root = tempfile.mkdtemp(), tempfile.mkdtemp()

        class Fake:
            def get(self, url):
                return 200, url, HTML

            def close(self):
                pass
        old = uys.DEFAULT_OUT
        uys.DEFAULT_OUT = out
        try:
            before = uys.tree_digest(ss.DATA_DIR, exclude=())
            with redirect_stdout(io.StringIO()):
                rc = yr.main(["standings"], fetcher=Fake(), out_dir=out)
            self.assertEqual(rc, 0)
            self.assertEqual(uys.tree_digest(ss.DATA_DIR, exclude=()), before)
        finally:
            uys.DEFAULT_OUT = old
            shutil.rmtree(out)
            shutil.rmtree(root)


class TestPublishedOrder(Base):
    """B, the provisional reverse-standings order, is derived from A, Yahoo's official order. It is a display order, never a draft order."""

    def view(self, d):
        return bls.standings_view({"dataDir": d.dir})

    def test_worst_record_first_with_yahoo_ranks_and_tie_order_kept(self):
        with fresh_data() as d:
            uys.run(CFG, real_source(), d.out, data_dir=d.dir, apply=True, captured_at=SEEN)
            v = self.view(d)
            rank = {t["franchiseId"]: t["rank"] for t in ys.current_snapshot(d.standings)["teams"]}
            self.assertEqual([rank[f] for f in v["worstFirst"]], list(range(16, 0, -1)))        # 16 first ... 1 last
            self.assertEqual(self.fo(13), v["worstFirst"][0])                                    # MeloBB: rank 16 (1-7-1, tied with Maxfixe at 15)
            self.assertEqual(self.fo(12), v["worstFirst"][1])                                    # Yahoo's tie order, not a recomputed one
            self.assertEqual(self.fo(8), v["worstFirst"][-1])                                    # Hai | Bulls Dynasty: rank 1
            self.assertEqual({v["teams"][f]["place"] for f in v["teams"]}, set(range(1, 17)))
            self.assertEqual((v["sourceUpdatedAt"], v["sourceUpdatedText"]), ("2026-10-26T08:00:00Z", "Mon Oct 26 03:00pm +07"))

    def test_the_view_falls_back_to_win_percentage_only_when_a_snapshot_has_no_ranks(self):
        with fresh_data() as d:
            uys.run(CFG, real_source(), d.out, data_dir=d.dir, apply=True, captured_at=SEEN)
            path = os.path.join(d.standings, ys.load_index(d.standings)["current"])
            snap = ss._load(path)
            for t in snap["teams"]:
                t["rank"] = None
            ss._write(path, snap)
            v = self.view(d)
            pct = {f: v["teams"][f]["pct"] for f in v["teams"]}
            self.assertEqual([pct[f] for f in v["worstFirst"]], sorted(pct.values()))

    def test_nothing_published_means_no_view(self):
        with fresh_data() as d:
            self.assertIsNone(self.view(d))

    def test_the_embedded_page_data_is_the_published_view_and_the_ui_is_intact(self):
        html = read(os.path.join(os.path.dirname(__file__), "..", "index.html"))
        data = json.loads(re.search(r'id="league-data">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual(data["standings"], bls.standings_view(ss.load_season(ls.load_inputs())))
        self.assertIn("function renderStandings()", html)
        self.assertIn('"STANDINGS 16–9":"TEAMS 1–8"', html)

    def test_the_published_snapshot_is_valid_and_its_pointer_resolves(self):
        idx = ys.load_index()
        snap = ys.current_snapshot()
        self.assertIsNotNone(snap)
        self.assertEqual(idx["history"][-1]["file"], idx["current"])
        self.assertEqual(snap["digest"], idx["history"][-1]["digest"])
        self.assertEqual(snap["digest"], ys._digest(snap))                                       # the content still hashes to its digest
        for h in idx["history"]:
            self.assertTrue(os.path.exists(os.path.join(ys.STANDINGS_DIR, h["file"])), h["file"])
        if snap["started"]:
            bad, _ = ys.validate([{"teamId": t["teamId"], "division": t["division"], "rank": t["rank"], "w": t["w"], "l": t["l"], "t": t["t"],
                                   "pct": t["pct"], "divRecord": t["divRecord"], "gb": t["gb"], "lastWeek": t["lastWeek"],
                                   "waiver": t["waiver"], "moves": t["moves"]} for t in snap["teams"]], CFG, self.fo)
            self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
