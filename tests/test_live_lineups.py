"""Lineup-integrity evidence: out starters, empty slots and benched stars, read from closed days."""
import datetime
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import live_lineups as ll  # noqa: E402
import live_days as ldy  # noqa: E402
import yahoo_rosters as yr  # noqa: E402

CFG = dict(yr.load_config(), requestDelaySeconds=0)


def row(slot, name=None, pid=None, pos=("PG",), status="", game="W, 100-90 vs AAA", stats=True):
    line = {k: (5 if stats else None) for k in ("fgPct", "ftPct", "tpm", "pts", "reb", "ast", "st", "blk", "to")}
    return {"slot": slot, "name": name, "playerId": pid, "positions": list(pos), "status": status, "game": game if name else None, "line": line if name else {},
            "fg": [5, 5] if name and stats else None, "ft": [5, 5] if name and stats else None}


class TestMisses(unittest.TestCase):
    def test_an_out_starter_with_an_eligible_healthy_bench_player_is_a_misset(self):
        rows = [row("PG", "Out Guy", "1", status="O", stats=False), row("BN", "Bench Guy", "2", pos=("PG", "SG"))]
        got = ll.misses(rows, {})
        self.assertEqual([(i["k"], i["p"], i["r"]) for i in got], [("out_starter", "Out Guy", "Bench Guy")])

    def test_no_misset_without_a_healthy_eligible_replacement_with_a_game(self):
        wrong_position = [row("C", "Out Big", "1", pos=("C",), status="O", stats=False), row("BN", "Guard", "2", pos=("PG",))]
        replacement_also_out = [row("PG", "Out PG", "3", status="INJ", stats=False), row("BN", "Hurt", "4", status="O", stats=False)]
        replacement_idle = [row("SG", "Out SG", "5", pos=("SG",), status="O", stats=False), row("BN", "Idle", "6", pos=("SG",), game=None)]
        for rows in (wrong_position, replacement_also_out, replacement_idle):
            self.assertEqual(ll.misses(rows, {}), [])

    def test_an_out_player_who_recorded_stats_is_not_a_misset(self):
        rows = [row("PG", "Played", "1", status="O", stats=True), row("BN", "Bench Guy", "2")]
        self.assertEqual(ll.misses(rows, {}), [])

    def test_an_empty_starting_slot_with_a_bench_player_who_could_fill_it(self):
        rows = [row("Util"), row("BN", "Bench Guy", "2", pos=("PF",))]
        self.assertEqual([i["k"] for i in ll.misses(rows, {})], ["empty_slot"])

    def test_composite_slots_accept_their_positions_and_each_replacement_is_used_once(self):
        rows = [row("G", "Out A", "1", pos=("PG",), status="O", stats=False), row("F", "Out B", "2", pos=("SF",), status="O", stats=False),
                row("BN", "Only Wing", "3", pos=("SF",))]
        got = ll.misses(rows, {})
        self.assertEqual([i["p"] for i in got], ["Out B"])                           # the guard slot has no eligible replacement

    def test_a_healthy_star_on_the_bench_with_a_game_is_counted_by_rank(self):
        rows = [row("BN", "Star", "10", pos=("C",)), row("BN", "Role", "11", pos=("C",))]
        got = ll.misses(rows, {"10": 12, "11": 180})
        self.assertEqual([(i["k"], i["p"], i["rank"]) for i in got], [("star_benched", "Star", 12)])


class FakeDays:
    """Stands in for live_days.Days: counts the days asked for."""

    def __init__(self, rows):
        self.rows_by_team, self.asked = rows, []

    def rows(self, date, closed):
        self.asked.append(date.isoformat())
        return self.rows_by_team


class TestClosedDays(unittest.TestCase):
    NOW = datetime.datetime(2026, 11, 5, 12, tzinfo=datetime.timezone.utc)            # Thursday 04:00 Pacific: Mon 11-02, Tue 11-03 and Wed 11-04 are closed
    ROWS = {1: [row("PG", "Out Guy", "1", status="O", stats=False), row("BN", "Bench Guy", "2"), row("SG", "Plays", "9")], 2: [row("PG", "Fine", "3")]}

    def run_it(self, previous=None, days=None, now=None):
        days = days or FakeDays(self.ROWS)
        return days, ldy.closed_days(CFG, 3, now or self.NOW, {}, days, previous)

    def test_closed_days_are_summarised_per_team_against_the_rule(self):
        days, (lineup, week) = self.run_it()
        self.assertEqual(sorted(lineup["byDate"]), ["2026-11-02", "2026-11-03", "2026-11-04"])
        t = {x["yahooId"]: x for x in lineup["teams"]}
        self.assertEqual((t[1]["missetDays"], t[1]["players"], t[1]["meetsCount"]), (3, 1, True))      # 2+ days reaches the rule's count
        self.assertEqual((t[2]["missetDays"], t[2]["meetsCount"]), (0, False))
        self.assertEqual(week["through"], ["2026-11-02", "2026-11-03", "2026-11-04"])

    def test_week_made_attempted_adds_the_starters_of_every_closed_day(self):
        days, (lineup, week) = self.run_it()
        self.assertEqual(week["p"]["9"], [15, 15, 15, 15])                             # 5/5 and 5/5 a day (see row()), three days
        self.assertNotIn("2", week["p"])                                               # the bench does not count

    def test_days_already_in_the_previous_feed_are_not_captured_again(self):
        days, (lineup, week) = self.run_it()
        days2, (lineup2, week2) = self.run_it({"lineupChecks": lineup, "playerWeek": week}, now=self.NOW + datetime.timedelta(hours=1))
        self.assertEqual(days2.asked, [])
        days3, (lineup3, week3) = self.run_it({"lineupChecks": lineup, "playerWeek": week}, now=self.NOW + datetime.timedelta(days=1))
        self.assertEqual(days3.asked, ["2026-11-05"])                                  # only the newly closed day
        self.assertEqual(week3["p"]["9"], [20, 20, 20, 20])

    def test_a_day_yahoo_cannot_serve_is_reported_missing(self):
        class Boom:
            def rows(self, date, closed):
                raise ldy.ym.MatchupError("HTTP_404", "x")
        lineup, week = ldy.closed_days(CFG, 3, self.NOW, {}, Boom(), None)
        self.assertEqual(len(lineup["missing"]), 3)
        self.assertEqual(lineup["byDate"], {})


if __name__ == "__main__":
    unittest.main()
