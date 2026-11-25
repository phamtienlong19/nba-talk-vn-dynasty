"""The season schedule: pairings kept as plain pairs of Yahoo ids, captured by walking matchup pages."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import update_yahoo_matchups as um  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
import yahoo_schedule as sched  # noqa: E402

CFG = dict(yr.load_config(), requestDelaySeconds=0)
IDS = CFG["teamIds"]
ROUND = [[IDS[i], IDS[i + 1]] for i in range(0, 16, 2)]


class FakePages:
    """Stands in for the walk: every unstored week pairs the teams as ROUND, and counts how many weeks were asked for."""
    def __init__(self):
        self.walked = []
        self._orig = um.walk_week
        um.walk_week = self

    def __call__(self, cfg, week, fetcher, delay=None, sleep=None):
        self.walked.append(week)
        return [{"teams": [{"teamId": a}, {"teamId": b}]} for a, b in ROUND]

    def close(self):
        um.walk_week = self._orig


class TestPairings(unittest.TestCase):
    def test_pairs_are_sorted_id_pairs_for_stored_and_parsed_weeks(self):
        doc = {"matchups": [{"teams": [{"teamId": 9}, {"teamId": 2}]}, {"teams": [{"teamId": 1}, {"teamId": 17}]}]}
        self.assertEqual(sched.pairs(doc), [[1, 17], [2, 9]])
        self.assertEqual(sched.pairs([{"teams": [{"teamId": 5}, {"teamId": 3}]}]), [[3, 5]])

    def test_check_rejects_a_missing_week_a_repeated_team_and_a_team_against_itself(self):
        full = {w: ROUND for w in range(1, 18)}
        self.assertEqual(sched.check(full, CFG), [])
        self.assertTrue(sched.check({w: ROUND for w in range(1, 17)}, CFG))
        self.assertTrue(sched.check({**full, 5: ROUND[:-1] + [[IDS[0], IDS[1]]]}, CFG))
        self.assertTrue(sched.check({**full, 5: [[IDS[0], IDS[0]]] + ROUND[1:]}, CFG))

    def test_the_real_pairing_page_of_a_future_week_is_readable(self):
        with open(os.path.join(HERE, "fixtures", "yahoo", "matchups", "week3_mid8_not_started_full.html"), encoding="utf-8") as f:
            p = ym.parse_matchup_html(f.read(), CFG)
        self.assertEqual(len(p["teams"]), 2)
        self.assertEqual(ym.validate(p, CFG), ([], []))

    def test_the_stored_schedule_covers_the_17_regular_weeks_and_agrees_with_the_finished_weeks(self):
        kept = sched.load()
        if not kept:
            self.skipTest("no schedule captured yet")
        self.assertEqual(sched.check(kept, CFG), [])
        for w, doc in ym.load_weeks().items():
            self.assertEqual(kept[w], sched.pairs(doc), "week %d" % w)


class TestCapture(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.path = os.path.join(self.d, "schedule.json")
        self.mdir = os.path.join(self.d, "matchups")
        self.fake = FakePages()
        self.out = []

    def tearDown(self):
        self.fake.close()

    def run_it(self, apply=True):
        return um.run_schedule(CFG, None, apply=apply, matchup_dir=self.mdir, path=self.path, sleep=lambda s: None, out=self.out.append)

    def test_every_week_is_walked_once_then_nothing_is_fetched_again(self):
        self.assertEqual(self.run_it(), 0)
        self.assertEqual(self.fake.walked, list(range(1, 18)))
        self.assertEqual(sorted(sched.load(self.path)), list(range(1, 18)))
        self.fake.walked.clear()
        self.assertEqual(self.run_it(), 0)
        self.assertEqual(self.fake.walked, [])
        self.assertIn("NO_CHANGE", self.out[-1])

    def test_a_dry_run_writes_nothing(self):
        self.run_it(apply=False)
        self.assertFalse(os.path.exists(self.path))

    def test_a_failed_walk_writes_nothing(self):
        def boom(*a, **k):
            raise ym.MatchupError("HTTP_404", "nope")
        um.walk_week = boom
        self.assertEqual(self.run_it(), 1)
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
