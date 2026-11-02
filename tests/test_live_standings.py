"""Weekly results -> standings: the stored finished weeks reproduce Yahoo's published standings, ties are shown as ties, the playoff
picture follows the division-winner rule, and the capture script stores only finished, validated, never-overwritten weeks."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import live_standings as lst  # noqa: E402
import update_yahoo_matchups as um  # noqa: E402
import yahoo_matchups as ym  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "yahoo")
CFG = ym.load_config()


def yahoo_nov2():
    with open(os.path.join(FIX, "standings_2026-11-02_after_week2.json"), encoding="utf-8") as f:
        return json.load(f)["teams"]


class TestStoredWeeks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weeks = ym.load_weeks()

    def test_weeks_one_and_two_are_stored_final_and_cover_every_team_once(self):
        for w in (1, 2):
            d = self.weeks[w]
            self.assertEqual((d["status"], d["week"], len(d["matchups"])), ("FINAL", w, 8))
            ids = sorted(t["teamId"] for m in d["matchups"] for t in m["teams"])
            self.assertEqual(ids, sorted(CFG["teamIds"]))
            self.assertEqual(d["digest"], ym._digest(d))

    def test_every_stored_result_is_reproduced_from_its_own_totals(self):
        for w, d in self.weeks.items():
            for m in d["matchups"]:
                a, b = (t["stats"] for t in m["teams"])
                res = ym.category_results(a, b)
                self.assertEqual(m["result"], {"cats": res["cats"], "a": res["a"], "b": res["b"], "t": res["t"]}, (w, m["teams"][0]["teamId"]))
                self.assertEqual((m["teams"][0]["printedWins"], m["teams"][1]["printedWins"]), (res["a"], res["b"]))

    def test_summed_weeks_equal_yahoos_published_standings(self):
        rec = lst.tally({w: d for w, d in self.weeks.items() if w <= 2})
        for t in yahoo_nov2():
            self.assertEqual((rec[t["teamId"]]["w"], rec[t["teamId"]]["l"], rec[t["teamId"]]["t"]), (t["w"], t["l"], t["t"]), t["yahooName"])

    def test_our_order_agrees_with_yahoos_everywhere_except_inside_ties(self):
        rec = lst.tally({w: d for w, d in self.weeks.items() if w <= 2})
        div = {t["teamId"]: t["division"] for t in yahoo_nov2()}
        rows = {r["teamId"]: r for r in lst.table(rec, None, div)}
        for a in yahoo_nov2():
            for b in yahoo_nov2():
                if a["rank"] < b["rank"]:
                    self.assertGreaterEqual(rows[a["teamId"]]["pct"], rows[b["teamId"]]["pct"])    # Yahoo never ranks a lower pct higher
                    if rows[a["teamId"]]["pct"] > rows[b["teamId"]]["pct"]:
                        self.assertLess(rows[a["teamId"]]["rank"], rows[b["teamId"]]["rank"])
        for t in yahoo_nov2():
            self.assertEqual(rows[t["teamId"]]["gbDivision"], t["gb"] or 0.0, t["yahooName"])      # Yahoo's own figure is from the division leader
            top = max(rows.values(), key=lambda r: (r["pct"], -r["rank"]))
            self.assertEqual(rows[t["teamId"]]["gb"], ((top["w"] - rows[t["teamId"]]["w"]) + (rows[t["teamId"]]["l"] - top["l"])) / 2)   # ours: overall


class TestTable(unittest.TestCase):
    OFFICIAL = {1: {"w": 7, "l": 2, "t": 0}, 2: {"w": 6, "l": 3, "t": 0}, 3: {"w": 6, "l": 3, "t": 0}, 4: {"w": 2, "l": 7, "t": 0}}

    def test_equal_records_share_a_rank_and_are_marked_tied(self):
        rows = {r["teamId"]: r for r in lst.table(self.OFFICIAL)}
        self.assertEqual([rows[i]["rank"] for i in (1, 2, 3, 4)], [1, 2, 2, 4])
        self.assertEqual([rows[i]["tied"] for i in (1, 2, 3, 4)], [False, True, True, False])

    def test_a_tie_counts_half_in_the_percentage(self):
        self.assertAlmostEqual(lst.pct({"w": 7, "l": 1, "t": 1}), 0.8333, 3)
        self.assertIsNone(lst.pct({"w": 0, "l": 0, "t": 0}))

    def test_the_live_week_moves_teams_and_reports_the_movement(self):
        live = {3: {"w": 6, "l": 3, "t": 0}, 2: {"w": 1, "l": 8, "t": 0}, 1: {"w": 4, "l": 5, "t": 0}, 4: {"w": 5, "l": 4, "t": 0}}
        rows = {r["teamId"]: r for r in lst.table(self.OFFICIAL, live)}
        self.assertEqual(rows[3]["rank"], 1)                                                          # 12-6
        self.assertEqual(rows[3]["moved"], 1)                                                         # up from the shared 2nd
        self.assertEqual(rows[3]["officialRecord"], [6, 3, 0])
        self.assertTrue(all(r["label"].startswith("PROVISIONAL") for r in rows.values()))
        self.assertEqual({r["label"] for r in lst.table(self.OFFICIAL)}, {"official"})

    def test_a_week_with_nothing_decided_changes_nothing(self):
        live = {i: {"w": 0, "l": 0, "t": 0} for i in self.OFFICIAL}
        a, b = lst.table(self.OFFICIAL, live), lst.table(self.OFFICIAL)
        self.assertEqual([(r["teamId"], r["rank"]) for r in a], [(r["teamId"], r["rank"]) for r in b])


class TestPlayoffPicture(unittest.TestCase):
    def rows(self, spec):
        """spec: [(teamId, division, w, l)] -> table rows"""
        rec = {tid: {"w": w, "l": l, "t": 0} for tid, _d, w, l in spec}
        return lst.table(rec, None, {tid: d for tid, d, _w, _l in spec})

    def test_a_division_winner_advances_even_with_a_worse_record_than_the_next_teams(self):
        spec = [(i, "West", 15 - i, 3 + i) for i in range(1, 9)] + [(i, "East", 5, 13) if i == 9 else (i, "East", 3, 15) for i in range(9, 17)]
        pic = lst.playoff_picture(self.rows(spec), {"teams": 8})
        self.assertEqual(pic["status"][9], "in")                                                     # the East leader (5-13) is in
        self.assertEqual(sum(1 for s in pic["status"].values() if s == "in"), 8)
        self.assertEqual(pic["status"][8], "out")                                                    # a better record than 9 but out: 7 West teams + 9
        self.assertEqual(sorted(pic["seeds"].values()), list(range(1, 9)))

    def test_a_team_level_with_the_last_spot_is_a_bubble_not_in_or_out(self):
        spec = [(1, "West", 12, 6), (2, "West", 11, 7), (3, "West", 10, 8), (4, "West", 9, 9), (5, "West", 9, 9), (6, "West", 1, 17),
                (7, "East", 12, 6), (8, "East", 8, 10), (9, "East", 7, 11), (10, "East", 7, 11), (11, "East", 6, 12), (12, "East", 1, 17)]
        pic = lst.playoff_picture(self.rows(spec), {"teams": 5})
        self.assertEqual(pic["status"][4], "bubble")
        self.assertEqual(pic["status"][5], "bubble")
        self.assertEqual(pic["status"][1], "in")

    def test_games_back_is_from_the_overall_leader_and_the_line_is_the_last_playoff_team(self):
        spec = [(1, "West", 12, 6), (2, "West", 10, 8), (3, "West", 4, 14), (4, "East", 9, 9), (5, "East", 8, 10), (6, "East", 3, 15)]
        rows = {r["teamId"]: r for r in self.rows(spec)}
        self.assertEqual(rows[4]["gb"], 3.0)                                                          # (12-9 + 9-6)/2 from team 1, not from its East leader
        pic = lst.playoff_picture(list(rows.values()), {"teams": 4})
        self.assertEqual(pic["lineTeam"], 5)                                                          # the 4th team in
        self.assertEqual(pic["gbLine"][5], 0.0)
        self.assertEqual(pic["gbLine"][1], -4.0)                                                      # four games clear of the line
        self.assertEqual(pic["gbLine"][3], 4.0)                                                       # four games behind

    def test_tied_division_leaders_are_marked(self):
        spec = [(1, "West", 10, 8), (2, "West", 10, 8), (3, "West", 2, 16), (4, "East", 9, 9), (5, "East", 1, 17), (6, "East", 0, 18)]
        pic = lst.playoff_picture(self.rows(spec), {"teams": 3})
        self.assertEqual(pic["divisionTie"], [1, 2])


class TestProjection(unittest.TestCase):
    def test_projected_ranks_are_unique_with_ties_listed_and_ordered_by_the_official_order(self):
        rec = {1: {"w": 5, "l": 4, "t": 0}, 2: {"w": 5, "l": 4, "t": 0}, 3: {"w": 1, "l": 8, "t": 0}}
        snap = lst.projected_snapshot(lst.table(rec), official_order=[2, 1, 3])
        self.assertEqual([t["teamId"] for t in snap["teams"]], [2, 1, 3])
        self.assertEqual(sorted(t["rank"] for t in snap["teams"]), [1, 2, 3])
        self.assertEqual(snap["tiedRanks"], [1])


class FakeYahoo:
    """Serves the saved pages: the default page is week 3 (not started), week-1 pages by team id."""
    CURRENT = "week3_mid8_not_started_full.html"

    def __init__(self, tamper=None):
        self.tamper, self.urls = tamper, []

    def get(self, url):
        self.urls.append(url)
        if "week=" not in url:
            name = self.CURRENT
        else:
            import re
            w, mid = (int(x) for x in re.search(r"week=(\d+)&mid1=(\d+)", url).groups())
            name = "week%d_mid%d_header.html" % (w, mid)
            if w != 1 or not os.path.exists(os.path.join(FIX, "matchups", name)):
                return 404, url, ""
        with open(os.path.join(FIX, "matchups", name), encoding="utf-8") as f:
            body = f.read()
        if self.tamper and "week=1&mid1=%d" % self.tamper in url:
            body = body.replace(">528<", ">529<", 1)
        return 200, url, body


class TestCapture(unittest.TestCase):
    def go(self, fetcher, d, **k):
        lines = []
        rc = um.run(CFG, fetcher, apply=True, matchup_dir=d, sleep=lambda s: None, out=lines.append, **k)
        return rc, lines

    def test_a_finished_week_is_walked_validated_and_stored_once(self):
        with tempfile.TemporaryDirectory() as d:
            f = FakeYahoo()
            rc, lines = self.go(f, d, weeks=[1])
            self.assertEqual(rc, 0, lines)
            doc = ym.load_weeks(d)[1]
            self.assertEqual((doc["status"], len(doc["matchups"])), ("FINAL", 8))
            self.assertEqual(len([u for u in f.urls if "week=1" in u]), 8)                           # one request per pairing, not per team
            rc, lines = self.go(FakeYahoo(), d, weeks=[1])
            self.assertTrue(any("NO_CHANGE" in x for x in lines), lines)                            # same data: nothing rewritten

    def test_a_changed_finished_week_is_a_conflict_and_the_stored_week_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            self.go(FakeYahoo(), d, weeks=[1])
            before = ym.load_weeks(d)[1]["digest"]
            rc, lines = self.go(FakeYahoo(tamper=8), d, weeks=[1])
            self.assertEqual(rc, 1)
            self.assertTrue(any("FAILED" in x or "CONFLICT" in x for x in lines), lines)
            self.assertEqual(ym.load_weeks(d)[1]["digest"], before)

    def test_the_current_week_is_never_stored(self):
        with tempfile.TemporaryDirectory() as d:
            rc, lines = self.go(FakeYahoo(), d, weeks=[3])
            self.assertEqual(rc, 1)
            self.assertEqual(ym.load_weeks(d), {})

    def test_a_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            lines = []
            um.run(CFG, FakeYahoo(), weeks=[1], apply=False, matchup_dir=d, sleep=lambda s: None, out=lines.append)
            self.assertEqual(ym.load_weeks(d), {})


if __name__ == "__main__":
    unittest.main()
