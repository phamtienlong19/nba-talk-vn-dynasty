"""Filling the game log from Yahoo's one-day player list: the page parser, the day check against the team pages, and the capped, resumable run."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import backfill_player_log as bf  # noqa: E402
import player_log as pl  # noqa: E402
import yahoo_matchups as ym  # noqa: E402
import yahoo_player_days as ypd  # noqa: E402

HEAD = ["", "Players", "Opp", "Roster Status", "GP*", "Pre-Season", "Current", "% Ros", "MIN*", "FGM/A*", "FG%", "FTM/A*", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO", ""]


def row(pid, pts=None, minutes="30", gp="1"):
    """One player row of the list; pts None = no game that day."""
    stats = ["-", "-/-", "-", "-/-", "-", "-", "-", "-", "-", "-", "-", "-"] if pts is None else \
            ["0", "0/0", "-", "0/0", "-", "0", "0", "0", "0", "0", "0", "0"] if minutes == "0" else \
            [minutes, "5/9", ".556", "1/2", ".500", "1", str(pts), "4", "3", "2", "1", "0"]
    name = '<div><a class="name" data-ys-playerid="%s" title="P%s">P%s</a> <span>BOS - PG</span> <span>%s</span></div>' % (pid, pid, pid, "" if pts is None else "L, 99-101 vs TOR")
    cells = ["", name, "MIA", "FA", "-" if pts is None else gp, "5", "-", "1%"] + stats + [""]
    return "<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in cells)


def page(rows, head=HEAD):
    return "<html><body><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></body></html>" % ("".join("<th>%s</th>" % h for h in head), "".join(rows))


class TestParser(unittest.TestCase):
    def test_a_line_carries_the_stats_and_the_opponent_and_no_lineup_slot(self):
        r = ypd.parse_page(page([row("7", pts=12)]))[0]
        self.assertEqual((r["playerId"], r["slot"], r["min"], r["fg"], r["ft"], r["line"]["pts"], r["line"]["to"]), ("7", None, "30", [5, 9], [1, 2], 12, 0))
        self.assertEqual(pl.opponent(r["game"]), "vs TOR")
        self.assertTrue(pl.played(r))

    def test_no_game_and_zero_minutes_are_not_games_played(self):
        none, dnp = ypd.parse_page(page([row("7"), row("8", pts=0, minutes="0")]))
        self.assertFalse(pl.played(none))
        self.assertFalse(pl.played(dnp))

    def test_a_season_view_is_refused_because_it_would_publish_wrong_numbers(self):
        with self.assertRaises(ym.MatchupError):
            ypd.parse_page(page([row("7", pts=12, gp="16")]))
        with self.assertRaises(ym.MatchupError):
            ypd.parse_page(page([row("7", pts=12)], head=[h.replace("MIN*", "MPG") for h in HEAD]))

    def test_the_address_asks_for_every_player_on_one_day(self):
        u = ypd.url_for({"leagueId": "85092"}, "2026-11-03", 50)
        for part in ("status=ALL", "stat1=S_D", "date=2026-11-03", "count=50"):
            self.assertIn(part, u)


class Fake:
    """`players` ids spread over pages; player 1 scores `pts[date]`."""
    def __init__(self, pts, players=510, broken=()):
        self.pts, self.players, self.broken, self.urls = pts, players, set(broken), []

    def get(self, url):
        self.urls.append(url)
        date, offset = url.split("date=")[1][:10], int(url.split("count=")[1])
        if date in self.broken:
            return 503, url, ""
        ids = range(1, self.players + 1)[offset:offset + 25]
        return 200, url, page([row(str(i), pts=self.pts[date] if i <= 12 else None) for i in ids])


def team_log(dates, pts):
    doc = pl.empty()
    doc["days"] = list(dates)
    for i in range(1, 13):                                       # twelve team-page lines a day to check against
        doc["p"][str(i)] = [[d, "PG", "vs TOR", "30:00", 5, 9, 1, 2, 1, pts[d], 4, 3, 2, 1, 0, 8] for d in dates if not (i == 1 and d == dates[0])]
    return doc


class TestRun(unittest.TestCase):
    DATES = ["2026-11-02", "2026-11-03", "2026-11-04"]
    PTS = {"2026-11-02": 10, "2026-11-03": 20, "2026-11-04": 30}

    def run_in(self, d, fetcher, **kw):
        out = []
        rc = bf.run({"leagueId": "85092", "requestDelaySeconds": 0}, fetcher, d + "/days.json", d + "/log.json", {"1", "400"},
                    sleep=lambda s: None, out=out.append, **kw)
        return rc, out

    def setup_dir(self, d, pts=None):
        with open(d + "/log.json", "w") as f:
            json.dump(team_log(self.DATES, pts or self.PTS), f)

    def read(self, d, name):
        with open(os.path.join(d, name)) as f:
            return json.load(f)

    def test_each_day_is_fetched_once_capped_per_run_and_the_holes_are_filled(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_dir(d)
            yahoo = Fake(self.PTS)
            rc, out = self.run_in(d, yahoo, max_days=2)
            self.assertEqual(rc, 0, out)
            self.assertEqual(self.read(d, "days.json")["days"], self.DATES[:2])
            first = self.read(d, "log.json")["p"]["1"]
            self.assertEqual([(r[0], r[1]) for r in first], [(self.DATES[0], None), (self.DATES[1], "PG"), (self.DATES[2], "PG")])   # the hole is filled, team lines stay
            self.assertIn("1 day(s) still to fetch", out[-1])
            again = Fake(self.PTS)
            self.run_in(d, again, max_days=2)
            self.assertEqual({u.split("date=")[1][:10] for u in again.urls}, {self.DATES[2]})

    def test_a_day_that_disagrees_with_the_team_pages_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_dir(d)
            rc, out = self.run_in(d, Fake(dict(self.PTS, **{self.DATES[1]: 99})))
            self.assertEqual(rc, 1)
            self.assertEqual(self.read(d, "days.json")["days"], [self.DATES[0], self.DATES[2]])
            self.assertTrue(any("refused" in x for x in out), out)

    def test_a_short_list_or_a_failed_day_is_retried_next_time_never_invented(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_dir(d)
            rc, out = self.run_in(d, Fake(self.PTS, players=100))
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(d + "/days.json"))
            rc, out = self.run_in(d, Fake(self.PTS, broken=[self.DATES[0]]))
            self.assertEqual((rc, self.read(d, "days.json")["days"]), (1, self.DATES[1:]))

    def test_without_the_team_log_nothing_happens(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_in(d, Fake(self.PTS))[0], 1)
            self.assertEqual(os.listdir(d), [])

    def test_the_rostered_players_come_from_the_current_snapshot(self):
        ids = bf.rostered()
        self.assertGreater(len(ids), 150)
        self.assertTrue(all(i.isdigit() for i in ids))

    def test_the_workflow_keeps_both_files_and_runs_after_the_team_log(self):
        with open(os.path.join(HERE, "..", ".github", "workflows", "update-player-stats.yml"), encoding="utf-8") as f:
            wf = f.read()
        self.assertLess(wf.index("update_player_log.py"), wf.index("backfill_player_log.py --days out/player_days.json --log out/player_log.json"))
        self.assertIn("player_stats.json player_log.json player_days.json", wf)
        self.assertNotIn("origin main", wf)


if __name__ == "__main__":
    unittest.main()
