"""Roster changes of the week (adds and drops between days) and the players who left a roster but still count in the week totals."""
import datetime
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import build_live_feed as blf  # noqa: E402
import live_days as ldy  # noqa: E402
from test_live_lineups import CFG, row  # noqa: E402

NOW = datetime.datetime(2026, 11, 5, 12, tzinfo=datetime.timezone.utc)          # Mon 11-02, Tue 11-03, Wed 11-04 closed


class ByDay:
    """Day pages that differ: team 1 drops Bench Guy on Tuesday and adds New Guy; team 2 never changes."""
    def __init__(self):
        self.asked = []

    def rows(self, date, closed):
        d = date.isoformat()
        self.asked.append(d)
        t1 = [row("PG", "Star", "9"), row("BN", "Bench Guy", "2")] if d == "2026-11-02" else [row("PG", "Star", "9"), row("BN", "New Guy", "5")]
        return {1: t1, 2: [row("PG", "Fine", "3")]}


class TestMoves(unittest.TestCase):
    def run_it(self, previous=None, now=NOW):
        days = ByDay()
        return days, ldy.closed_days(CFG, 3, now, {}, days, previous)

    def test_adds_and_drops_are_found_between_consecutive_days_only(self):
        _d, (_l, week) = self.run_it()
        self.assertEqual(week["moves"], [{"date": "2026-11-03", "team": 1, "add": [["5", "New Guy"]], "drop": [["2", "Bench Guy"]]}])
        self.assertEqual(week["last"]["date"], "2026-11-04")

    def test_a_feed_without_moves_is_backfilled_once_then_only_new_days_are_asked_for(self):
        _d, (lineup, week) = self.run_it()
        old = {k: v for k, v in week.items() if k not in ("moves", "last")}
        days2, (_l2, week2) = self.run_it({"lineupChecks": lineup, "playerWeek": old})
        self.assertEqual(week2["moves"], week["moves"])                               # rebuilt from the day cache
        days3, (_l3, week3) = self.run_it({"lineupChecks": lineup, "playerWeek": week2})
        self.assertEqual(days3.asked, [])
        self.assertEqual(week3["moves"], week["moves"])

    def test_today_is_compared_with_the_last_closed_day_and_a_departed_player_is_not_a_roster_member(self):
        last = {"date": "2026-11-04", "teams": {"1": {"9": "Star", "5": "New Guy"}}}
        pages = [{"rosters": {1: [row("PG", "Star", "9"), row("--", "Gone Guy", "7"), row("BN", "Claimed", "8")]}}]
        got = ldy.today_moves(last, pages, "2026-11-05")
        self.assertEqual(got, [{"date": "2026-11-05", "team": 1, "add": [["8", "Claimed"]], "drop": [["5", "New Guy"]]}])
        self.assertEqual(ldy.today_moves(last, pages, "2026-11-04"), [])             # nothing before a day has passed
        self.assertEqual(ldy.today_moves(None, pages, "2026-11-05"), [])

    def test_the_feed_carries_the_moves_by_franchise_with_names(self):
        week = {"moves": [{"date": "2026-11-03", "team": 1, "add": [["5", "New Guy"]], "drop": [["2", "Bench Guy"]]}], "last": None}
        out = blf._moves_out(week, [], None, lambda t: "F%d" % t)
        self.assertEqual(out, [{"date": "2026-11-03", "team": "F1", "yahooId": 1, "add": ["New Guy"], "drop": ["Bench Guy"], "addIds": ["5"], "dropIds": ["2"]}])


if __name__ == "__main__":
    unittest.main()
