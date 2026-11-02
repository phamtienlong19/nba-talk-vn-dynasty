"""Yahoo matchup pages: parsing, the category math, and the golden checks against Yahoo's own numbers.
The fixtures are trimmed copies of the real public pages of league 85092 (fetched 2026-11-02): all eight week-1 matchups (header
tables), one full finished matchup with its rosters, one full week-2 page for a single day, and one week that has not started."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import yahoo_matchups as ym  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "yahoo", "matchups")
CFG = ym.load_config()


def page(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return ym.parse_matchup_html(f.read(), CFG)


WEEK1 = ["week1_mid%d_header.html" % i for i in (1, 2, 4, 5, 7, 8, 11, 13)]


class TestCategoryMath(unittest.TestCase):
    def stats(self, **k):
        base = {"fg": [100, 200], "ft": [50, 100], "tpm": 10, "pts": 100, "reb": 50, "ast": 30, "st": 8, "blk": 5, "to": 20}
        base.update(k)
        return base

    def test_the_higher_value_wins_and_fewer_turnovers_win(self):
        r = ym.category_results(self.stats(pts=120, to=10), self.stats())
        self.assertEqual((r["cats"]["pts"], r["cats"]["to"]), ("a", "a"))
        self.assertEqual((r["a"], r["b"], r["t"]), (2, 0, 7))

    def test_percentages_come_from_made_over_attempted(self):
        r = ym.category_results(self.stats(fg=[90, 150]), self.stats(fg=[100, 200]))      # .600 vs .500 despite fewer makes
        self.assertEqual(r["cats"]["fgPct"], "a")

    def test_no_data_is_undecided_not_zero(self):
        empty = {"fg": None, "ft": None, "tpm": None, "pts": None, "reb": None, "ast": None, "st": None, "blk": None, "to": None}
        r = ym.category_results(empty, empty)
        self.assertFalse(r["decided"])
        self.assertEqual((r["a"], r["b"], r["t"]), (0, 0, 0))
        r = ym.category_results(self.stats(fg=[0, 0]), self.stats())                       # no attempts: no percentage
        self.assertIsNone(r["cats"]["fgPct"])


class TestFinishedWeek(unittest.TestCase):
    def test_every_week1_page_reproduces_yahoos_printed_scores_and_highlights(self):
        for name in WEEK1:
            p = page(name)
            bad, warn = ym.validate(p)
            self.assertEqual(bad, [], name)
            self.assertEqual([w for w in warn if "highlighted" in w], [], name)             # Yahoo's bold cells = our winners
            r = ym.matchup_result(p)
            self.assertTrue(r["decided"], name)
            self.assertEqual((r["a"], r["b"]), tuple(t["printedWins"] for t in p["teams"]), name)

    def test_the_eight_matchups_pair_all_sixteen_teams_once(self):
        ids = [t["teamId"] for n in WEEK1 for t in page(n)["teams"]]
        self.assertEqual(sorted(ids), sorted(CFG["teamIds"]))

    def test_summed_category_results_equal_the_published_standings(self):
        with open(os.path.join(HERE, "fixtures", "yahoo", "NBA_Talk_Dynasty_Standings_2026-10-26.json"), encoding="utf-8") as f:
            snap = {t["yahoo_team_id"]: (t["wins"], t["losses"], t["ties"]) for t in json.load(f)["teams"]}
        got = {}
        for n in WEEK1:
            r = ym.matchup_result(page(n))
            a, b = r["teams"]
            got[a] = (r["a"], r["b"], r["t"])
            got[b] = (r["b"], r["a"], r["t"])
        self.assertEqual(got, snap)                                                        # week 1 is the whole of the 10-26 standings

    def test_a_tampered_printed_score_blocks_the_capture(self):
        p = page("week1_mid8_header.html")
        p["teams"][0]["printedWins"] += 1
        bad, _ = ym.validate(p)
        self.assertTrue(any("printed category wins" in b for b in bad))


class TestRosters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = page("week2_mid16_mid4_date2026-11-01_full.html")

    def test_both_rosters_are_read_by_team_with_slot_status_and_game(self):
        self.assertEqual((self.p["week"], [t["teamId"] for t in self.p["teams"]]), (2, [16, 4]))
        self.assertEqual(sorted(self.p["rosters"]), [4, 16])
        by = {r["name"]: r for r in self.p["rosters"][4] if r["name"]}
        pod = by["Brandin Podziemski"]
        self.assertEqual((pod["slot"], pod["nba"], pod["positions"], pod["game"]), ("PG", "GSW", ["PG", "SG"], "W, 124-112 vs LAC"))
        self.assertEqual((pod["line"]["pts"], pod["line"]["reb"], pod["line"]["ast"]), (17, 8, 8))
        self.assertEqual(by["Zach LaVine"]["status"], "Q")
        out = {r["name"]: r for r in self.p["rosters"][16] if r["name"]}["Kingston Flemings"]
        self.assertEqual(out["status"], "O")

    def test_a_player_without_a_game_that_day_has_null_stats_not_zero(self):
        idle = {r["name"]: r for r in self.p["rosters"][16] if r["name"]}["Amen Thompson"]
        self.assertIsNone(idle["line"]["pts"])
        self.assertIsNone(idle["game"])

    def test_empty_slots_are_kept_without_a_player(self):
        empties = [r for ros in self.p["rosters"].values() for r in ros if r["name"] is None]
        self.assertTrue(empties)
        self.assertTrue(all(r["slot"] for r in empties))                                   # IL / BN slot with nobody in it

    def test_slots_cover_the_lineup_bench_and_il(self):
        slots = {r["slot"] for ros in self.p["rosters"].values() for r in ros}
        self.assertTrue({"PG", "SG", "Util", "BN", "IL"} <= slots, slots)


class TestWeekNotStarted(unittest.TestCase):
    def test_empty_stats_are_null_and_nothing_is_decided(self):
        p = page("week3_mid8_not_started_full.html")
        self.assertEqual(p["week"], 3)
        for t in p["teams"]:
            self.assertTrue(all(v is None for k, v in t["stats"].items()), t["stats"])
            self.assertEqual(t["printedWins"], 0)
        r = ym.matchup_result(p)
        self.assertFalse(r["decided"])
        self.assertEqual(ym.validate(p)[0], [])
        self.assertEqual(p["weeks"], list(range(1, 21)))

    def test_a_week_with_no_stats_that_prints_wins_is_rejected(self):
        p = page("week3_mid8_not_started_full.html")
        p["teams"][0]["printedWins"] = 3
        self.assertTrue(ym.validate(p)[0])


class TestUnreadablePages(unittest.TestCase):
    def test_a_page_without_the_matchup_table_is_refused_with_a_code(self):
        with self.assertRaises(ym.MatchupError) as c:
            ym.parse_matchup_html("<html><body>Sign in to continue</body></html>", CFG)
        self.assertEqual(c.exception.code, "NO_TABLE")

    def test_a_changed_roster_shape_is_refused(self):
        import re
        with open(os.path.join(FIX, "week2_mid16_mid4_date2026-11-01_full.html"), encoding="utf-8") as f:
            html = f.read()
        start = html.index("<tbody", html.index("<table", html.index("<table") + 1))     # the roster table's body
        row = html.index("<tr", start)
        broken = html[:row] + re.sub(r"<td[^>]*>.*?</td>", "", html[row:], count=1, flags=re.S)   # one cell fewer in the first row
        with self.assertRaises(ym.MatchupError) as c:
            ym.parse_matchup_html(broken, CFG)
        self.assertEqual(c.exception.code, "ROSTER_SHAPE")


if __name__ == "__main__":
    unittest.main()
