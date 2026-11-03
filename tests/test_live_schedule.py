"""Games left this week: the schedule read from future-day roster pages, kept in a cache, and counted per player."""
import datetime
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import live_schedule as lsch  # noqa: E402
import update_yahoo_matchups as um  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

CFG = dict(yr.load_config(), requestDelaySeconds=0)
NOW = datetime.datetime(2026, 11, 3, 12, tzinfo=datetime.timezone.utc)          # Tue 04:00 Pacific: week 3 (Mon 11-02 .. Sun 11-08)
PAGES = [{"teams": [{"teamId": 1}, {"teamId": 2}]}, {"teams": [{"teamId": 3}, {"teamId": 4}]}]


def player(nba, game):
    return {"name": nba + " guy", "nba": nba, "game": game}


class TestSchedule(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self._orig = um.fetch_page

        def fake(cfg, fetcher, url, **kw):
            self.calls.append(url)
            day = url.split("date=")[1].split("&")[0]
            games = {"2026-11-04": {"LAC", "MEM"}}.get(day, set())
            return {"rosters": {1: [player("LAC", "7:00 pm vs MEM" if "LAC" in games else None), player("BOS", None)],
                                2: [player("MEM", "7:00 pm @ LAC" if "MEM" in games else None)]}}
        um.fetch_page = fake

    def tearDown(self):
        um.fetch_page = self._orig

    def test_only_the_days_after_today_are_listed(self):
        self.assertEqual([d.isoformat() for d in lsch.remaining_dates(CFG, 3, NOW)], ["2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08"])

    def test_teams_playing_a_day_come_from_the_game_text(self):
        s = lsch.schedule(CFG, 3, PAGES, None, NOW, sleep=lambda x: None)
        self.assertEqual(s["dates"]["2026-11-04"], {"LAC", "MEM"})
        self.assertEqual(s["dates"]["2026-11-05"], set())
        self.assertEqual(s["missing"], [])

    def test_games_left_counts_today_if_unfinished_plus_later_days(self):
        s = lsch.schedule(CFG, 3, PAGES, None, NOW, sleep=lambda x: None)
        self.assertEqual(lsch.games_left("LAC", "upcoming", s), 2)
        self.assertEqual(lsch.games_left("LAC", "final", s), 1)
        self.assertEqual(lsch.games_left("LAC", None, s), 1)
        self.assertEqual(lsch.games_left("BOS", "live", s), 1)

    def test_a_day_is_fetched_once_then_read_from_the_cache(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.json")
            lsch.schedule(CFG, 3, PAGES, None, NOW, path, lambda x: None)
            first = len(self.calls)
            lsch.schedule(CFG, 3, PAGES, None, NOW + datetime.timedelta(minutes=5), path, lambda x: None)
            self.assertEqual(len(self.calls), first)
            lsch.schedule(CFG, 3, PAGES, None, NOW + datetime.timedelta(hours=13), path, lambda x: None)      # too old: asked again
            self.assertGreater(len(self.calls), first)
            self.assertEqual(json.load(open(path))["week"], 3)

    def test_a_day_yahoo_cannot_serve_is_reported_missing_not_fatal(self):
        def boom(cfg, fetcher, url, **kw):
            raise lsch.ym.MatchupError("HTTP_404", url)
        um.fetch_page = boom
        s = lsch.schedule(CFG, 3, PAGES, None, NOW, sleep=lambda x: None)
        self.assertEqual(s["dates"], {})
        self.assertEqual(len(s["missing"]), 5)


if __name__ == "__main__":
    unittest.main()
