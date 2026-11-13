"""The day-by-day game log: built from Yahoo's team-day page, one closed day at a time, kept once, never invented."""
import datetime
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import player_log as pl  # noqa: E402
import update_player_log as upl  # noqa: E402
import yahoo_teamday as ytd  # noqa: E402

PAGE = open(os.path.join(HERE, "fixtures", "yahoo", "team_day_2026-11-02_team1.html"), encoding="utf-8").read()
CFG = {"seasonStartMonday": "2026-11-01", "teamIds": [1, 2], "requestDelaySeconds": 0, "pageUrl": "https://x/{leagueId}/{teamId}", "leagueId": 1}


class Fake:
    def __init__(self, fail_on=()):
        self.urls, self.fail_on = [], fail_on

    def get(self, url):
        self.urls.append(url)
        return (500, url, "") if any(d in url for d in self.fail_on) else (200, url, PAGE)


class TestBuild(unittest.TestCase):
    def test_only_games_he_played_become_lines_with_the_opponent_and_the_slot(self):
        rows = ytd.parse_team_day(PAGE)
        doc = pl.empty()
        n = pl.add_day(doc, "2026-11-02", {1: rows})
        self.assertEqual(n, 12)                                                    # 12 played; the 3 IL rows with no game are left out
        g = doc["p"]["6167"][0]                                                    # Darius Garland
        self.assertEqual(dict(zip(pl.COLS, g)), {"date": "2026-11-02", "slot": "PG", "opp": "vs TOR", "min": "36:07", "fgm": 5, "fga": 14, "ftm": 5, "fta": 6,
                                                  "tpm": 1, "pts": 16, "reb": 4, "ast": 8, "st": 0, "blk": 0, "to": 7, "team": 1})
        self.assertNotIn("6692", doc["p"])                                         # Chet Holmgren sat on IL: no line
        self.assertEqual(doc["p"]["6170"][0][1], "BN")                             # a bench game is kept and says so

    def test_a_day_is_kept_once(self):
        rows = ytd.parse_team_day(PAGE)
        doc = pl.empty()
        pl.add_day(doc, "2026-11-02", {1: rows})
        self.assertEqual(pl.add_day(doc, "2026-11-02", {1: rows}), 0)
        self.assertEqual(len(doc["p"]["6167"]), 1)
        self.assertEqual(doc["days"], ["2026-11-02"])

    def test_no_dollar_signs_and_no_totals_in_the_file(self):
        doc = pl.empty()
        pl.add_day(doc, "2026-11-02", {1: ytd.parse_team_day(PAGE)})
        text = json.dumps(doc)
        self.assertNotIn("$", text)
        self.assertNotIn("total", text.lower())


class TestMinutes(unittest.TestCase):
    def test_minutes_are_kept_as_yahoo_shows_them(self):
        self.assertEqual(ytd._minutes("36:07"), "36:07")
        self.assertEqual(ytd._minutes("36"), "36")                                  # the live page gives a whole number
        self.assertIsNone(ytd._minutes("-"))


class TestRun(unittest.TestCase):
    def run_it(self, fetcher, path, today):
        out = []
        now = datetime.datetime.combine(today, datetime.time(17, 0), datetime.timezone.utc)     # 09:00 Pacific that day
        rc = upl.run(CFG, fetcher, path, sleep=lambda s: None, out=out.append, now=now)
        return rc, out

    def test_the_first_run_walks_every_closed_day_then_only_new_days_are_fetched(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "player_log.json")
            f1 = Fake()
            rc, _ = self.run_it(f1, path, datetime.date(2026, 11, 4))               # Nov 1, 2, 3 are closed
            self.assertEqual(rc, 0)
            self.assertEqual(len(f1.urls), 3 * 2)                                   # 3 days x 2 teams
            self.assertEqual(json.load(open(path))["days"], ["2026-11-01", "2026-11-02", "2026-11-03"])
            f2 = Fake()
            rc, _ = self.run_it(f2, path, datetime.date(2026, 11, 5))               # one new day
            self.assertEqual(len(f2.urls), 2)
            self.assertIn("date=2026-11-04", f2.urls[0])
            self.assertEqual(json.load(open(path))["days"][-1], "2026-11-04")
            f3 = Fake()
            rc, out = self.run_it(f3, path, datetime.date(2026, 11, 5))             # nothing new: nothing fetched, nothing rewritten
            self.assertEqual((rc, f3.urls), (0, []))
            self.assertIn("nothing new", out[-1])

    def test_a_failed_day_is_skipped_and_retried_never_invented(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "player_log.json")
            rc, out = self.run_it(Fake(fail_on=("date=2026-11-02",)), path, datetime.date(2026, 11, 4))
            days = json.load(open(path))["days"]
            self.assertEqual(days, ["2026-11-01", "2026-11-03"])
            self.assertTrue(any("2026-11-02 skipped" in x for x in out))
            f = Fake()
            self.run_it(f, path, datetime.date(2026, 11, 4))                        # the next run fetches just the missing day
            self.assertTrue(all("date=2026-11-02" in u for u in f.urls) and f.urls)
            self.assertEqual(json.load(open(path))["days"], ["2026-11-01", "2026-11-02", "2026-11-03"])

    def test_a_broken_file_starts_over_and_the_workflow_never_touches_main(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "player_log.json")
            open(path, "w").write("{not json")
            self.assertEqual(upl.load(path), pl.empty())
        wf = open(os.path.join(HERE, "..", ".github", "workflows", "update-player-stats.yml"), encoding="utf-8").read()
        self.assertIn("stats-data", wf)
        self.assertNotIn("gh pr", wf)
        self.assertNotIn("push origin main", wf)
        self.assertIn("update_player_log.py", wf)
        self.assertIn("update_yahoo_player_stats.py", wf)


if __name__ == "__main__":
    unittest.main()
