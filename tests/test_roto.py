"""Roto points, ranks and all-play: the reference math (scripts/roto.py) and the owner's week-2 report package."""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import roto  # noqa: E402

with open(os.path.join(HERE, "fixtures", "roto_week2_package.json"), encoding="utf-8") as _f:
    PKG = json.load(_f)
STATS = {t["id"]: t["stats"] for t in PKG["teams"]}


def team(**kw):
    s = {"fg": [40, 100], "ft": [20, 25], "tpm": 10, "pts": 100, "reb": 50, "ast": 30, "st": 8, "blk": 5, "to": 20}
    s.update(kw)
    return s


class TestAgainstThePackage(unittest.TestCase):
    def setUp(self):
        self.r, self.ap = roto.roto(STATS), roto.all_play(STATS)

    def test_points_totals_and_ranks_match_the_package_for_all_16_teams(self):
        for t in PKG["teams"]:
            e, got = t["expect"], self.r[t["id"]]
            for k, v in e["points"].items():
                self.assertAlmostEqual(got["points"][k], v, msg="%s %s" % (t["id"], k))
            self.assertAlmostEqual(got["total"], e["total"])
            self.assertEqual(got["rank"], e["rank"])

    def test_all_play_records_and_every_cell_match_the_package(self):
        for t in PKG["teams"]:
            self.assertEqual(self.ap["record"][t["id"]], t["expect"]["allPlay"])
            for o, v in t["expect"]["h2h"].items():
                c = self.ap["cells"][t["id"]][int(o)]
                self.assertEqual([c["w"], c["l"], c["t"], c["margin"]], v, (t["id"], o))

    def test_invariants(self):
        for key, _l, _lower in roto.CATS:
            self.assertAlmostEqual(sum(v["points"][key] for v in self.r.values()), 136)       # 1+2+...+16 however ties fall
        self.assertAlmostEqual(sum(v["total"] for v in self.r.values()), 9 * 136)


class TestRules(unittest.TestCase):
    def test_fewer_turnovers_score_higher(self):
        r = roto.roto({1: team(to=10), 2: team(to=30)})
        self.assertEqual((r[1]["points"]["to"], r[2]["points"]["to"]), (2, 1))

    def test_level_teams_share_the_average_place(self):
        r = roto.roto({1: team(pts=90), 2: team(pts=90), 3: team(pts=120), 4: team(pts=100)})
        self.assertEqual([r[i]["points"]["pts"] for i in (1, 2, 3, 4)], [1.5, 1.5, 4, 3])

    def test_equal_percentages_tie_exactly_not_by_float_noise(self):
        r = roto.roto({1: team(fg=[1, 3]), 2: team(fg=[2, 6]), 3: team(fg=[3, 7])})
        self.assertEqual((r[1]["points"]["fgPct"], r[2]["points"]["fgPct"], r[3]["points"]["fgPct"]), (1.5, 1.5, 3))

    def test_competition_rank_for_level_totals(self):
        r = roto.roto({1: team(), 2: team(), 3: team(pts=10)})
        self.assertEqual((r[1]["rank"], r[2]["rank"], r[3]["rank"]), (1, 1, 3))

    def test_nothing_is_scored_before_every_team_has_a_value(self):
        r = roto.roto({1: team(fg=[0, 0]), 2: team()})
        self.assertIsNone(r[1]["points"]["fgPct"])

    def test_head_to_head_counts_ties_and_margin(self):
        c = roto.head_to_head(team(pts=120, to=10), team(tpm=10, reb=50))
        self.assertEqual((c["w"], c["l"], c["t"], c["margin"]), (2, 0, 7, 2))


if __name__ == "__main__":
    unittest.main()
