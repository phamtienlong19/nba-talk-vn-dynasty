"""Offline tests for yahoo_roto.py (no network): the page readers, the category plan, and the roto math."""
import os
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import yahoo_roto as yr  # noqa: E402

SETTINGS = ("<html><body>Scoring Type: Head-to-Head - Categories Max Acquisitions for Entire Season: No maximum "
            "Make League Publicly Viewable: Yes Stat Categories: Field Goal Percentage (FG%), Free Throw Percentage (FT%), "
            "3-point Shots Made (3PTM), Points Scored (PTS), Turnovers (TO) Stat Modifiers: none Roster Positions: PG</body></html>")


def matchup(week, rows, weeks=(1, 2, 3)):
    opts = "".join('<option value="x?module=matchup&week=%d"%s>%d</option>' % (w, " selected" if w == week else "", w) for w in weeks)
    body = "".join('<tr><td><a href="/nba/9/%d">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td></td></tr>' % ((t, n) + tuple(v))
                   for t, n, v in rows)
    return ("<select>%s</select><table><tr><th>Team</th><th>FGM/A*</th><th>FG%%</th><th>FTM/A*</th><th>FT%%</th><th>3PTM</th><th>PTS</th><th>TO</th><th></th></tr>%s</table>" % (opts, body))


class Settings(unittest.TestCase):
    def test_scoring_type_categories_and_public_flag(self):
        s = yr.parse_settings(SETTINGS)
        self.assertEqual(s["scoring"], "Head-to-Head - Categories")
        self.assertEqual(s["categories"], ["FG%", "FT%", "3PTM", "PTS", "TO"])
        self.assertTrue(s["public"])

    def test_teams_come_from_the_standings_rows(self):
        html = '<table><tr><th>Rank</th><th>Team</th></tr><tr><td>1</td><td><a href="/nba/9/4">Alpha</a></td></tr><tr><td>2</td><td><a href="/nba/9/7">Beta</a></td></tr></table>'
        self.assertEqual(yr.parse_teams(html, 9), {4: "Alpha", 7: "Beta"})


class Weekly(unittest.TestCase):
    def test_a_matchup_page_keeps_made_attempted_pairs_and_none_for_dashes(self):
        w = yr.parse_week(matchup(2, [(1, "A", ["5/10", ".500", "3/4", ".750", "4", "30", "2"]), (2, "B", ["-/-", "-", "-/-", "-", "-", "-", "-"])]), 9)
        self.assertEqual(w["week"], 2)
        self.assertEqual(w["weeks"], [1, 2, 3])
        self.assertEqual(w["teams"][1]["cols"]["FGM/A*"], (5, 10))
        self.assertEqual(w["teams"][1]["cols"]["PTS"], 30)
        self.assertIsNone(w["teams"][2]["cols"]["PTS"])
        self.assertIsNone(w["teams"][2]["cols"]["FGM/A*"])

    def test_a_page_without_a_matchup_table_is_refused(self):
        with self.assertRaises(yr.RotoError):
            yr.parse_week("<html><table><tr><th>Player</th></tr></table></html>", 9)


class Math(unittest.TestCase):
    HEADS = ["Team", "FGM/A*", "FG%", "FTM/A*", "FT%", "3PTM", "PTS", "TO"]

    def test_plan_pairs_a_percentage_with_the_makes_before_it_and_skips_what_it_cannot_compute(self):
        specs, skipped = yr.plan(["FG%", "PTS", "TO", "ERA", "XYZ"], self.HEADS)
        self.assertEqual([(s["cat"], s["kind"], s["col"], s["lower"]) for s in specs],
                         [("FG%", "pct", "FGM/A*", False), ("PTS", "count", "PTS", False), ("TO", "count", "TO", True)])
        self.assertEqual(skipped, ["ERA", "XYZ"])

    def test_places_average_ties_and_fewer_is_better(self):
        self.assertEqual(yr.places([Fraction(5), Fraction(5), Fraction(9)], False), {0: 1.5, 1: 1.5, 2: 3})
        self.assertEqual(yr.places([Fraction(10), Fraction(2), Fraction(5)], True), {0: 1, 2: 2, 1: 3})            # most turnovers = 1 point

    def test_season_totals_sum_makes_and_attempts_not_percentages(self):
        wk = [{"week": 1, "teams": {1: {"cols": {"FGM/A*": (1, 2), "PTS": 10}}}}, {"week": 2, "teams": {1: {"cols": {"FGM/A*": (9, 10), "PTS": 5}}}}]
        t = yr.totals(wk, [1])
        self.assertEqual(t[1]["FGM/A*"], (10, 12))
        self.assertEqual(yr.cat_value(t[1], {"kind": "pct", "col": "FGM/A*"}), Fraction(10, 12))                    # not (50% + 90%) / 2
        self.assertEqual(t[1]["PTS"], 15)

    def test_roto_ranks_with_ties_and_a_competition_rank(self):
        specs, _ = yr.plan(["PTS", "TO"], self.HEADS)
        stats = {1: {"PTS": Fraction(30), "TO": Fraction(5)}, 2: {"PTS": Fraction(20), "TO": Fraction(9)}, 3: {"PTS": Fraction(20), "TO": Fraction(1)}}
        res, ranked = yr.roto(stats, specs)
        self.assertEqual(res[1]["points"], {"PTS": 3, "TO": 2})
        self.assertEqual(res[2]["points"], {"PTS": 1.5, "TO": 1})
        self.assertEqual(res[3]["points"], {"PTS": 1.5, "TO": 3})
        self.assertEqual([res[t]["rank"] for t in (1, 2, 3)], [1, 3, 2])                                            # 5.0, 2.5, 4.5
        self.assertEqual(ranked, [1, 3, 2])

    def test_a_category_with_a_missing_value_scores_nobody(self):
        specs, _ = yr.plan(["PTS"], self.HEADS)
        res, _ = yr.roto({1: {"PTS": Fraction(3)}, 2: {}}, specs)
        self.assertIsNone(res[1]["points"]["PTS"])
        self.assertEqual(res[1]["total"], 0)


class Fake(yr.Fetcher):
    def __init__(self, pages):
        super().__init__(delay=0)
        self.pages, self.urls = pages, []

    def get(self, url, keep=False):
        self.urls.append(url)
        for k, v in self.pages.items():
            if k in url:
                return v
        raise yr.RotoError("unexpected " + url)


class Private(unittest.TestCase):
    def test_a_private_or_missing_league_gets_a_plain_message(self):
        fx = Fake({"settings": "<html><title>There was a problem | Fantasy Basketball</title><body>Sign in</body></html>"})
        orig = yr.Fetcher
        yr.Fetcher = lambda **k: fx
        try:
            with self.assertRaises(yr.RotoError) as cm:
                yr.run("1234")
        finally:
            yr.Fetcher = orig
        self.assertIn("not publicly viewable", str(cm.exception))


class EndToEnd(unittest.TestCase):
    def test_one_page_covers_two_teams_and_a_week_without_stats_is_left_out(self):
        pages = {"settings": SETTINGS.replace("(PTS), Turnovers (TO)", "(PTS), Turnovers (TO)"),
                 "lhst=stand": '<table><tr><th>Team</th></tr><tr><td><a href="/nba/9/1">A</a></td></tr><tr><td><a href="/nba/9/2">B</a></td></tr></table>',
                 "week=1": matchup(1, [(1, "A", ["5/10", ".5", "3/4", ".75", "4", "30", "2"]), (2, "B", ["4/10", ".4", "2/4", ".5", "6", "25", "5"])]),
                 "week=2": matchup(2, [(1, "A", ["-/-", "-", "-/-", "-", "-", "-", "-"]), (2, "B", ["-/-", "-", "-/-", "-", "-", "-", "-"])]),
                 "week=3": matchup(3, [(1, "A", ["-/-", "-", "-/-", "-", "-", "-", "-"]), (2, "B", ["-/-", "-", "-/-", "-", "-", "-", "-"])])}
        fx = Fake(pages)
        orig = yr.Fetcher
        yr.Fetcher = lambda **k: fx
        try:
            doc = yr.run("9")
        finally:
            yr.Fetcher = orig
        self.assertEqual(doc["weeks"], [1])
        self.assertEqual([t["teamId"] for t in doc["teams"]], [1, 2])                                               # A wins 4 categories, B has more 3PM
        self.assertEqual(doc["categories"], ["FG%", "FT%", "3PTM", "PTS", "TO"])
        self.assertEqual(sum(1 for u in fx.urls if "week=1" in u and "matchup" in u), 2)                          # once for the weeks list, once for week 1 (page covers both teams)


if __name__ == "__main__":
    unittest.main()
