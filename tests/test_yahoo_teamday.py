"""The team page for one day: slots, minutes and made/attempted (a trimmed real page of team 1, Mon 2026-11-02)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import yahoo_matchups as ym  # noqa: E402
import yahoo_teamday as ytd  # noqa: E402

PAGE = open(os.path.join(HERE, "fixtures", "yahoo", "team_day_2026-11-02_team1.html"), encoding="utf-8").read()


class TestTeamDay(unittest.TestCase):
    def setUp(self):
        self.rows = ytd.parse_team_day(PAGE)
        self.by = {r["name"]: r for r in self.rows}

    def test_every_filled_slot_is_read_with_its_slot(self):
        self.assertEqual(len(self.rows), 15)
        self.assertEqual([r["slot"] for r in self.rows][:9], ["PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util"])
        self.assertEqual([r["slot"] for r in self.rows].count("BN"), 3)
        self.assertEqual([r["slot"] for r in self.rows].count("IL"), 3)

    def test_a_player_has_minutes_and_made_over_attempted(self):
        g = self.by["Darius Garland"]
        self.assertEqual((g["min"], g["fg"], g["ft"]), ("36:07", [5, 14], [5, 6]))
        self.assertEqual(g["line"], {"fgPct": 0.357, "ftPct": 0.833, "tpm": 1, "pts": 16, "reb": 4, "ast": 8, "st": 0, "blk": 0, "to": 7})

    def test_the_percentages_agree_with_made_over_attempted(self):
        for r in self.rows:
            if r["fg"] and r["fg"][1]:
                self.assertAlmostEqual(r["line"]["fgPct"], r["fg"][0] / r["fg"][1], places=3, msg=r["name"])

    def test_a_player_who_did_not_play_has_no_stats_not_zeros(self):
        il = [r for r in self.rows if r["slot"] == "IL"][0]
        self.assertEqual((il["min"], il["fg"], il["ft"]), (None, None, None))
        self.assertTrue(all(v is None for v in il["line"].values()))
        self.assertTrue(il["status"])

    def test_a_page_without_the_stat_table_is_refused(self):
        with self.assertRaises(ym.MatchupError) as c:
            ytd.parse_team_day("<html><body><table><tr><th>Player</th></tr></table></body></html>")
        self.assertEqual(c.exception.code, "NO_TABLE")

    def test_changed_columns_are_refused(self):
        with self.assertRaises(ym.MatchupError) as c:
            ytd.parse_team_day(PAGE.replace("FTM/A*", "FTM/A*").replace(">PTS<", ">POINTS<"))
        self.assertEqual(c.exception.code, "TEAM_SHAPE")


if __name__ == "__main__":
    unittest.main()
